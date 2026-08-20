from datetime import datetime
from uuid import UUID, uuid4


def test_create_document(client):
    payload = {"title": "cooling system", "file_name": "cooling-design.pdf"}
    response = client.post("/documents", json=payload)

    body = response.json()
    created_at = datetime.fromisoformat(body["created_at"])
    updated_at = datetime.fromisoformat(body["updated_at"])

    assert response.status_code == 201
    assert response.history == []
    assert body["title"] == payload["title"]
    assert body["file_name"] == payload["file_name"]
    assert body["status"] == "pending"
    assert created_at.tzinfo is not None
    assert updated_at.tzinfo is not None
    assert updated_at >= created_at

    UUID(body["id"])


def test_rejects_short_document_title(client):
    payload = {"title": "A", "file_name": "cooling-design.pdf"}
    response = client.post("/documents", json=payload)
    assert response.status_code == 422


def test_rejects_empty_document_file_name(client):
    payload = {"title": "A title", "file_name": ""}
    response = client.post("/documents", json=payload)
    assert response.status_code == 422


def test_status_transition_updates_document_timestamp(client):
    create_response = client.post(
        "/documents",
        json={"title": "Cooling system", "file_name": "cooling-design.pdf"},
    )

    assert create_response.status_code == 201

    created_document = create_response.json()
    original_updated_at = datetime.fromisoformat(created_document["updated_at"])
    update_response = client.patch(
        f"/documents/{created_document['id']}/status", json={"status": "processing"}
    )

    assert update_response.status_code == 200
    updated_document = update_response.json()
    new_updated_at = datetime.fromisoformat(updated_document["updated_at"])
    assert new_updated_at > original_updated_at


def test_retrieves_created_document(client):
    payload = {"title": "cooling system", "file_name": "cooling-design.pdf"}
    create_response = client.post("/documents", json=payload)
    assert create_response.status_code == 201

    created_document = create_response.json()

    response = client.get(f"/documents/{created_document['id']}")
    assert response.status_code == 200

    assert response.json() == created_document


def test_returns_404_for_unknown_document(client):
    unknown_id = uuid4()
    response = client.get(f"/documents/{unknown_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_rejects_malformed_document_id(client):
    malformed_id = "abc-def-ghi-jkl"
    response = client.get(f"/documents/{malformed_id}")
    assert response.status_code == 422


def test_lists_documents_with_pagination(client):
    payloads = [
        {
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
        {
            "title": "Electrical system",
            "file_name": "electrical-design.pdf",
        },
        {
            "title": "Hydraulic system",
            "file_name": "hydraulic-design.pdf",
        },
    ]

    created_ids = set()

    for payload in payloads:
        response = client.post("/documents", json=payload)
        assert response.status_code == 201
        created_ids.add(response.json()["id"])

    first_response = client.get("/documents?offset=0&limit=2")
    assert first_response.status_code == 200
    first_page = first_response.json()
    assert first_page["total"] == 3
    assert first_page["offset"] == 0
    assert first_page["limit"] == 2
    assert len(first_page["items"]) == 2

    second_response = client.get("/documents?offset=2&limit=2")
    assert second_response.status_code == 200
    second_page = second_response.json()

    assert second_page["total"] == 3
    assert second_page["offset"] == 2
    assert second_page["limit"] == 2
    assert len(second_page["items"]) == 1
    returned_ids = {
        document["id"] for document in first_page["items"] + second_page["items"]
    }

    assert returned_ids == created_ids


def test_rejects_invalid_document_pagination(client):
    response = client.get("/documents?offset=-1&limit=0")

    assert response.status_code == 422


def test_transitions_document_through_valid_statuses(client):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    document = create_response.json()

    for expected_status in ("processing", "ready", "archived"):
        response = client.patch(
            f"/documents/{document['id']}/status",
            json={"status": expected_status},
        )

        assert response.status_code == 200
        assert response.json()["id"] == document["id"]
        assert response.json()["status"] == expected_status


def test_retries_failed_document(client):
    create_response = client.post(
        "/documents",
        json={
            "title": "Electrical system",
            "file_name": "electrical-design.pdf",
        },
    )
    document = create_response.json()

    for expected_status in ("processing", "failed", "pending"):
        response = client.patch(
            f"/documents/{document['id']}/status",
            json={"status": expected_status},
        )

        assert response.status_code == 200
        assert response.json()["status"] == expected_status


def test_rejects_invalid_document_status_transition(client):
    create_response = client.post(
        "/documents",
        json={
            "title": "Hydraulic system",
            "file_name": "hydraulic-design.pdf",
        },
    )
    document = create_response.json()

    response = client.patch(
        f"/documents/{document['id']}/status",
        json={"status": "ready"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Cannot transition document from 'pending' to 'ready'"
    }


def test_rejects_unknown_document_status(client):
    create_response = client.post(
        "/documents",
        json={
            "title": "Structural system",
            "file_name": "structural-design.pdf",
        },
    )
    document = create_response.json()

    response = client.patch(
        f"/documents/{document['id']}/status",
        json={"status": "finished"},
    )

    assert response.status_code == 422


def test_filters_documents_by_status(client):
    documents = []

    for title, file_name in (
        ("Cooling system", "cooling-design.pdf"),
        ("Electrical system", "electrical-design.pdf"),
        ("Hydraulic system", "hydraulic-design.pdf"),
    ):
        response = client.post(
            "/documents", json={"title": title, "file_name": file_name}
        )

        assert response.status_code == 201
        documents.append(response.json())

    ready_document = documents[0]
    failed_document = documents[1]
    pending_document = documents[2]

    for target_status in ("processing", "ready"):
        response = client.patch(
            f"/documents/{ready_document['id']}/status",
            json={"status": target_status},
        )
        assert response.status_code == 200

    for target_status in ("processing", "failed"):
        response = client.patch(
            f"/documents/{failed_document['id']}/status", json={"status": target_status}
        )

        assert response.status_code == 200

    failed_response = client.get("/documents?status=failed")

    assert failed_response.status_code == 200

    failed_page = failed_response.json()
    assert failed_page["total"] == 1
    assert len(failed_page["items"]) == 1
    assert failed_page["items"][0]["id"] == failed_document["id"]
    assert failed_page["items"][0]["status"] == "failed"

    pending_response = client.get("/documents?status=pending")

    assert pending_response.status_code == 200

    pending_page = pending_response.json()

    assert pending_page["total"] == 1
    assert len(pending_page["items"]) == 1
    assert pending_page["items"][0]["id"] == pending_document["id"]
    assert pending_page["items"][0]["status"] == "pending"


def test_rejects_unknown_document_status_filter(client):
    response = client.get("/documents?status=finished")

    assert response.status_code == 422
