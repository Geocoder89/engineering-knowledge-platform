from dataclasses import dataclass
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.models.decision_alternative import DecisionAlternative
from app.models.decision_evidence import DecisionEvidence
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion
from app.repositories import (
    decision_evidence as decision_evidence_repository,
)


@dataclass(frozen=True, slots=True)
class EvidenceTestGraph:
    decision: Decision
    alternative: DecisionAlternative
    document: Document
    document_version: DocumentVersion
    document_page: DocumentPage
    document_chunk: DocumentChunk


def create_evidence_test_graph(
    session: Session,
) -> EvidenceTestGraph:
    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    session.add(decision)
    session.flush()

    alternative = DecisionAlternative(
        decision_id=decision.id,
        title="Reduce the pressure limit",
        description=(
            "Lower the approved maximum pressure to improve the safety margin."
        ),
        position=0,
    )
    session.add(alternative)
    session.flush()

    document = Document(
        title="Cooling system",
        file_name="cooling-design.pdf",
        status="ready",
    )
    session.add(document)
    session.flush()

    document_version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_name="cooling-design.pdf",
        content_type="application/pdf",
        size_bytes=100,
        checksum_sha256="a" * 64,
        storage_key=f"{document.id}/version-1",
    )
    session.add(document_version)
    session.flush()

    page_text = (
        "Reducing maximum operating pressure increases the available safety margin."
    )
    document_page = DocumentPage(
        document_version_id=document_version.id,
        page_number=4,
        text=page_text,
    )
    session.add(document_page)
    session.flush()

    document_chunk = DocumentChunk(
        document_page_id=document_page.id,
        chunk_index=0,
        text=page_text,
        start_offset=0,
        end_offset=len(page_text),
    )
    session.add(document_chunk)
    session.flush()

    return EvidenceTestGraph(
        decision=decision,
        alternative=alternative,
        document=document,
        document_version=document_version,
        document_page=document_page,
        document_chunk=document_chunk,
    )


def test_database_persists_supporting_decision_evidence(
    db_session: Session,
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )

    evidence = DecisionEvidence(
        decision_alternative_id=graph.alternative.id,
        document_chunk_id=graph.document_chunk.id,
        evidence_type="supporting",
        relevance_note=(
            "The source directly describes the safety benefit of this alternative."
        ),
    )
    db_session.add(evidence)
    db_session.flush()

    assert evidence.id is not None
    assert evidence.decision_alternative_id == graph.alternative.id
    assert evidence.document_chunk_id == graph.document_chunk.id
    assert evidence.evidence_type == "supporting"
    assert evidence.relevance_note == (
        "The source directly describes the safety benefit of this alternative."
    )
    assert evidence.created_at is not None


def test_database_rejects_duplicate_evidence_link(
    db_session: Session,
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )

    first_evidence = DecisionEvidence(
        decision_alternative_id=graph.alternative.id,
        document_chunk_id=graph.document_chunk.id,
        evidence_type="supporting",
    )
    db_session.add(first_evidence)
    db_session.flush()

    duplicate_evidence = DecisionEvidence(
        decision_alternative_id=graph.alternative.id,
        document_chunk_id=graph.document_chunk.id,
        evidence_type="opposing",
    )
    db_session.add(duplicate_evidence)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_database_rejects_invalid_evidence_type(
    db_session: Session,
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )

    evidence = DecisionEvidence(
        decision_alternative_id=graph.alternative.id,
        document_chunk_id=graph.document_chunk.id,
        evidence_type="unknown",
    )
    db_session.add(evidence)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_database_protects_cited_document_chunk(
    db_session: Session,
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )

    evidence = DecisionEvidence(
        decision_alternative_id=graph.alternative.id,
        document_chunk_id=graph.document_chunk.id,
        evidence_type="supporting",
    )
    db_session.add(evidence)
    db_session.flush()

    db_session.delete(
        graph.document_chunk,
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_repository_creates_and_lists_evidence_with_citation(
    db_session: Session,
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )
    relevance_note = (
        "The source directly describes the safety benefit of this alternative."
    )

    created_evidence = decision_evidence_repository.create_decision_evidence(
        db_session,
        decision_alternative_id=graph.alternative.id,
        document_chunk_id=graph.document_chunk.id,
        evidence_type="supporting",
        relevance_note=relevance_note,
    )

    citations = decision_evidence_repository.list_decision_evidence(
        db_session,
        decision_alternative_id=graph.alternative.id,
    )

    assert created_evidence.id is not None
    assert len(citations) == 1

    citation = citations[0]

    assert citation.decision_evidence_id == created_evidence.id
    assert citation.decision_alternative_id == graph.alternative.id
    assert citation.evidence_type == "supporting"
    assert citation.relevance_note == relevance_note
    assert citation.created_at == created_evidence.created_at

    assert citation.document_chunk_id == graph.document_chunk.id
    assert citation.document_page_id == graph.document_page.id
    assert citation.document_version_id == graph.document_version.id
    assert citation.document_id == graph.document.id

    assert citation.document_title == "Cooling system"
    assert citation.file_name == "cooling-design.pdf"
    assert citation.version_number == 1
    assert citation.page_number == 4
    assert citation.chunk_index == 0
    assert citation.text == graph.document_chunk.text
    assert citation.start_offset == 0
    assert citation.end_offset == len(
        graph.document_chunk.text,
    )


def test_adds_and_lists_decision_evidence_with_citation(
    client,
    db_session: Session,
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )
    relevance_note = (
        "The source directly describes the safety benefit of this alternative."
    )
    evidence_url = (
        f"/decisions/{graph.decision.id}/alternatives/{graph.alternative.id}/evidence"
    )

    create_response = client.post(
        evidence_url,
        json={
            "document_chunk_id": str(
                graph.document_chunk.id,
            ),
            "evidence_type": "supporting",
            "relevance_note": relevance_note,
        },
    )

    assert create_response.status_code == 201

    created_evidence = create_response.json()

    assert created_evidence["id"] is not None
    assert created_evidence["decision_alternative_id"] == str(
        graph.alternative.id,
    )
    assert created_evidence["document_chunk_id"] == str(
        graph.document_chunk.id,
    )
    assert created_evidence["evidence_type"] == "supporting"
    assert created_evidence["relevance_note"] == relevance_note
    assert created_evidence["chunk_index"] == 0
    assert created_evidence["text"] == graph.document_chunk.text
    assert created_evidence["start_offset"] == 0
    assert created_evidence["end_offset"] == len(
        graph.document_chunk.text,
    )

    assert created_evidence["citation"] == {
        "document_id": str(graph.document.id),
        "document_version_id": str(
            graph.document_version.id,
        ),
        "document_page_id": str(
            graph.document_page.id,
        ),
        "document_title": "Cooling system",
        "file_name": "cooling-design.pdf",
        "version_number": 1,
        "page_number": 4,
    }

    list_response = client.get(
        evidence_url,
    )

    assert list_response.status_code == 200
    assert list_response.json() == [
        created_evidence,
    ]


def test_rejects_duplicate_decision_evidence_link(
    client,
    db_session: Session,
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )
    evidence_url = (
        f"/decisions/{graph.decision.id}/alternatives/{graph.alternative.id}/evidence"
    )
    payload = {
        "document_chunk_id": str(
            graph.document_chunk.id,
        ),
        "evidence_type": "supporting",
        "relevance_note": ("This source supports the proposed alternative."),
    }

    first_response = client.post(
        evidence_url,
        json=payload,
    )

    assert first_response.status_code == 201

    duplicate_response = client.post(
        evidence_url,
        json={
            **payload,
            "evidence_type": "opposing",
        },
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": ("Document chunk is already linked to this decision alternative"),
    }


@pytest.mark.parametrize(
    "document_status",
    [
        "pending",
        "processing",
        "failed",
        "archived",
    ],
)
def test_rejects_evidence_from_document_that_is_not_ready(
    client,
    db_session: Session,
    document_status: str,
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )
    graph.document.status = document_status
    db_session.flush()

    response = client.post(
        (
            f"/decisions/{graph.decision.id}"
            f"/alternatives/{graph.alternative.id}"
            "/evidence"
        ),
        json={
            "document_chunk_id": str(
                graph.document_chunk.id,
            ),
            "evidence_type": "supporting",
            "relevance_note": ("This source supports the proposed alternative."),
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": ("Document chunk is not available for evidence"),
    }


def test_removes_decision_evidence_without_deleting_source(
    client,
    db_session: Session,
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )
    evidence_url = (
        f"/decisions/{graph.decision.id}/alternatives/{graph.alternative.id}/evidence"
    )

    create_response = client.post(
        evidence_url,
        json={
            "document_chunk_id": str(
                graph.document_chunk.id,
            ),
            "evidence_type": "supporting",
            "relevance_note": ("This source supports the proposed alternative."),
        },
    )

    assert create_response.status_code == 201

    created_evidence = create_response.json()

    delete_response = client.delete(
        (f"{evidence_url}/{created_evidence['id']}"),
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""

    list_response = client.get(
        evidence_url,
    )

    assert list_response.status_code == 200
    assert list_response.json() == []

    assert (
        db_session.get(
            DocumentChunk,
            graph.document_chunk.id,
        )
        is not None
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "document_chunk_id": str(uuid4()),
            "evidence_type": "neutral",
        },
        {
            "document_chunk_id": str(uuid4()),
            "evidence_type": "supporting",
            "relevance_note": "   ",
        },
        {
            "document_chunk_id": str(uuid4()),
            "evidence_type": "supporting",
            "unexpected_field": "not allowed",
        },
    ],
)
def test_rejects_invalid_decision_evidence_request(
    client,
    db_session: Session,
    payload: dict[str, object],
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )

    response = client.post(
        (
            f"/decisions/{graph.decision.id}"
            f"/alternatives/{graph.alternative.id}"
            "/evidence"
        ),
        json=payload,
    )

    assert response.status_code == 422


def test_rejects_unknown_document_chunk_as_evidence(
    client,
    db_session: Session,
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )

    response = client.post(
        (
            f"/decisions/{graph.decision.id}"
            f"/alternatives/{graph.alternative.id}"
            "/evidence"
        ),
        json={
            "document_chunk_id": str(
                uuid4(),
            ),
            "evidence_type": "supporting",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document chunk not found",
    }


def test_cannot_delete_evidence_through_another_alternative(
    client,
    db_session: Session,
) -> None:
    graph = create_evidence_test_graph(
        db_session,
    )

    other_alternative = DecisionAlternative(
        decision_id=graph.decision.id,
        title="Keep the existing pressure limit",
        description=("Retain the currently approved maximum pressure."),
        position=1,
    )
    db_session.add(other_alternative)
    db_session.flush()

    evidence_url = (
        f"/decisions/{graph.decision.id}/alternatives/{graph.alternative.id}/evidence"
    )
    create_response = client.post(
        evidence_url,
        json={
            "document_chunk_id": str(
                graph.document_chunk.id,
            ),
            "evidence_type": "supporting",
        },
    )

    assert create_response.status_code == 201

    evidence = create_response.json()

    response = client.delete(
        (
            f"/decisions/{graph.decision.id}"
            f"/alternatives/{other_alternative.id}"
            f"/evidence/{evidence['id']}"
        ),
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision evidence not found",
    }

    list_response = client.get(
        evidence_url,
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
