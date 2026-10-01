from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema

from app.api.dependencies import provide_embedding_provider
from app.config import settings
from app.embeddings.base import EMBEDDING_DIMENSIONS, EmbeddingVector
from app.main import app
from app.models import Base
from app.storage.local import LocalDocumentStorage
from app.workers import document_processing as document_processing_worker
from tests.conftest import FakeEmailVerificationSender
from tests.test_pdf_extraction import build_pdf_with_pages


class WorkflowEmbeddingProvider:
    """Two deterministic directions exercise real pgvector ranking, not AI quality."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def embed_texts(self, texts: tuple[str, ...]) -> tuple[EmbeddingVector, ...]:
        self.calls.append(texts)
        vectors = []
        for text in texts:
            vector = [0.0] * EMBEDDING_DIMENSIONS
            vector[0 if "cooling" in text.lower() else 1] = 1.0
            vectors.append(tuple(vector))
        return tuple(vectors)


@pytest.fixture(autouse=True)
def isolated_workflow_database(database_connection: Connection) -> None:
    # The worker claims from the whole queue. A private schema prevents it from
    # claiming pre-existing jobs when this test runs against a development DB.
    # The shared outer transaction rolls back the schema and all its tables.
    schema = f"workflow_{uuid4().hex}"
    database_connection.execute(CreateSchema(schema))
    database_connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}", public')
    Base.metadata.create_all(database_connection, checkfirst=False)


@pytest.fixture
def workflow_embeddings(monkeypatch: pytest.MonkeyPatch) -> WorkflowEmbeddingProvider:
    provider = WorkflowEmbeddingProvider()
    monkeypatch.setitem(
        app.dependency_overrides, provide_embedding_provider, lambda: provider
    )
    return provider


def register_verify_and_login(
    client: TestClient,
    sender: FakeEmailVerificationSender,
    *,
    email: str,
) -> dict:
    password = "workflow-only correct horse battery staple"
    sent_before = len(sender.sent_verifications)
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "display_name": "Workflow Engineer",
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    user = response.json()
    assert len(sender.sent_verifications) == sent_before + 1
    message = sender.sent_verifications[-1]
    assert message.recipient_email == email
    assert message.verification_token not in response.text

    credentials = {"email": email, "password": password}
    assert client.post("/auth/login", json=credentials).status_code == 401
    assert client.cookies.get(settings.session_cookie_name) is None

    verification = client.post(
        "/auth/verify-email", json={"verification_token": message.verification_token}
    )
    assert verification.status_code == 204, verification.text
    login = client.post("/auth/login", json=credentials)
    assert login.status_code == 200, login.text
    assert client.cookies.get(settings.session_cookie_name)
    csrf_token = client.cookies.get(settings.csrf_cookie_name)
    assert csrf_token
    client.headers["X-CSRF-Token"] = csrf_token

    current_user = client.get("/users/me")
    assert current_user.status_code == 200
    assert current_user.json()["id"] == user["id"]
    return user


def test_registered_user_completes_document_to_decision_workflow(
    client: TestClient,
    email_verification_sender: FakeEmailVerificationSender,
    database_connection: Connection,
    document_storage_path: Path,
    workflow_embeddings: WorkflowEmbeddingProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Use actual authentication; no authenticated_client fixture or user seeding.
    assert client.get("/documents").status_code == 401
    owner = register_verify_and_login(
        client, email_verification_sender, email="workflow-owner@example.com"
    )

    document_payload = {"title": "Engineering requirements", "file_name": "design.pdf"}
    rejected = client.post(
        "/documents", json=document_payload, headers={"X-CSRF-Token": "invalid"}
    )
    assert rejected.status_code == 403
    created = client.post("/documents", json=document_payload)
    assert created.status_code == 201, created.text
    document = created.json()
    assert document["status"] == "pending"
    document_url = f"/documents/{document['id']}"

    # Two pages force search to rank the relevant source above a distractor.
    cooling_text = "Cooling pressure must remain below the approved limit."
    electrical_text = "Electrical equipment requires a separate isolation procedure."
    pdf = build_pdf_with_pages((electrical_text, cooling_text))
    uploaded = client.post(
        f"{document_url}/versions",
        files={"file": ("design.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    version = uploaded.json()
    version_url = f"{document_url}/versions/{version['version_number']}"
    job_url = f"{version_url}/processing-job"
    queued = client.get(job_url)
    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"
    assert queued.json()["attempt_count"] == 0

    # Run the real worker's one-iteration entry point, with its own session but
    # inside the test's rollback boundary. No polling sleeps or external API.
    worker_sessions = sessionmaker(
        bind=database_connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(document_processing_worker, "SessionLocal", worker_sessions)
    storage = LocalDocumentStorage(root_path=document_storage_path)
    processed = document_processing_worker.run_worker_iteration(
        storage, embedding_provider=workflow_embeddings
    )
    assert processed is not None
    assert str(processed.id) == queued.json()["id"]
    assert processed.status == "completed"
    completed = client.get(job_url)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["attempt_count"] == 1
    assert completed.json()["error_message"] is None
    assert client.get(document_url).json()["status"] == "ready"
    downloaded = client.get(f"{version_url}/content")
    assert downloaded.status_code == 200
    assert downloaded.content == pdf
    embedded_texts = [text for batch in workflow_embeddings.calls for text in batch]
    assert set(embedded_texts) == {electrical_text, cooling_text}

    query = "What is the cooling pressure limit?"
    search = client.post("/search", json={"query": query, "limit": 2})
    assert search.status_code == 200, search.text
    matches = search.json()["items"]
    assert len(matches) == 2
    match = matches[0]
    assert match["text"] == cooling_text
    assert match["similarity_score"] > matches[1]["similarity_score"]
    assert match["citation"]["document_id"] == document["id"]
    assert match["citation"]["document_version_id"] == version["id"]
    assert match["citation"]["page_number"] == 2
    assert match["citation"]["file_name"] == "design.pdf"
    assert workflow_embeddings.calls[-1] == (query,)

    created_decision = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": "Should we reduce the maximum cooling-system pressure?",
        },
    )
    assert created_decision.status_code == 201, created_decision.text
    decision = created_decision.json()
    decision_url = f"/decisions/{decision['id']}"
    assert decision["created_by_user_id"] == owner["id"]
    assert decision["decided_by_user_id"] is None
    assert client.post(f"{decision_url}/submit").status_code == 409

    alternatives = []
    for title in ("Keep the existing limit", "Reduce the pressure limit"):
        response = client.post(
            f"{decision_url}/alternatives",
            json={"title": title, "description": title + " for the cooling system."},
        )
        assert response.status_code == 201, response.text
        alternatives.append(response.json())
    selected = alternatives[1]
    evidence_url = f"{decision_url}/alternatives/{selected['id']}/evidence"
    attached = client.post(
        evidence_url,
        json={
            "document_chunk_id": match["document_chunk_id"],
            "evidence_type": "supporting",
            "relevance_note": "The source supports a conservative pressure limit.",
        },
    )
    assert attached.status_code == 201, attached.text
    evidence = attached.json()
    assert evidence["text"] == match["text"]
    assert evidence["citation"] == match["citation"]

    submitted = client.post(f"{decision_url}/submit")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "in_review"
    assert submitted.json()["decided_by_user_id"] is None
    rationale = "Reducing the pressure limit follows the cited cooling requirements."
    finalized = client.post(
        f"{decision_url}/decide",
        json={"selected_alternative_id": selected["id"], "rationale": rationale},
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == "decided"
    assert finalized.json()["decided_by_user_id"] == owner["id"]

    record_response = client.get(f"{decision_url}/record")
    assert record_response.status_code == 200
    record = record_response.json()
    assert record["status"] == "decided"
    assert record["selected_alternative_id"] == selected["id"]
    assert record["rationale"] == rationale
    assert record["created_by_user_id"] == record["decided_by_user_id"] == owner["id"]
    assert record["submitted_at"] is not None
    assert record["decided_at"] is not None
    assert record["alternatives"] == [
        {**alternatives[0], "evidence": []},
        {**selected, "evidence": [evidence]},
    ]
    history_response = client.get(record["history"]["url"])
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["total"] == record["history"]["total"] == 6
    assert [item["sequence_number"] for item in history["items"]] == list(range(1, 7))
    assert [item["event_type"] for item in history["items"]] == [
        "decision_created",
        "alternative_added",
        "alternative_added",
        "evidence_added",
        "decision_submitted",
        "decision_finalized",
    ]
    assert all(item["actor_user_id"] == owner["id"] for item in history["items"])
    assert (
        history["items"][-1]["event_data"]["selected_alternative_id"] == selected["id"]
    )

    # A second real session must not see the first user's completed work.
    assert client.post("/auth/logout").status_code == 204
    assert client.cookies.get(settings.session_cookie_name) is None
    assert client.get(f"{decision_url}/record").status_code == 401
    client.headers.pop("X-CSRF-Token")
    other = register_verify_and_login(
        client, email_verification_sender, email="workflow-other@example.com"
    )
    assert other["id"] != owner["id"]
    for url in (
        document_url,
        f"{version_url}/content",
        job_url,
        evidence_url,
        f"{decision_url}/record",
        f"{decision_url}/history",
    ):
        assert client.get(url).status_code == 404, url
    private_search = client.post("/search", json={"query": query, "limit": 2})
    assert private_search.status_code == 200
    assert private_search.json()["items"] == []
