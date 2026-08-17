from uuid import UUID, uuid4


def test_create_document(client):
    payload = {"title": "cooling system", "file_name": "cooling-design.pdf"}
    response = client.post("/documents", json=payload)

    body = response.json()

    assert response.status_code == 201
    assert response.history == []
    assert body["title"] == payload["title"]
    assert body["file_name"] == payload["file_name"]
    assert body["status"] == "pending"

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
