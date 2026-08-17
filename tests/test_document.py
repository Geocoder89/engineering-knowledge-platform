from datetime import datetime
from uuid import UUID, uuid4


def test_create_document(client):
    payload = {"title": "cooling system", "file_name": "cooling-design.pdf"}
    response = client.post("/documents", json=payload)

    body = response.json()
    created_at = datetime.fromisoformat(body["created_at"])

    assert response.status_code == 201
    assert response.history == []
    assert body["title"] == payload["title"]
    assert body["file_name"] == payload["file_name"]
    assert body["status"] == "pending"
    assert created_at.tzinfo is not None

    UUID(body["id"])


def test_rejects_short_document_title(client):
    payload = {"title": "A", "file_name": "cooling-design.pdf"}
    response = client.post("/documents", json=payload)
    assert response.status_code == 422


def test_rejects_empty_document_file_name(client):
    payload = {"title": "A title", "file_name": ""}
    response = client.post("/documents", json=payload)
    assert response.status_code == 422


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
