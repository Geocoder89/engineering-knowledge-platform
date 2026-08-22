from datetime import datetime
from hashlib import sha256
from uuid import UUID, uuid4


def test_uploads_first_document_version(client, document_storage_path):
    create_response = client.post(
        "/documents",
        json={"title": "Cooling system", "file_name": "cooling-design.pdf"},
    )

    assert create_response.status_code == 201

    document = create_response.json()

    file_content = b"%PDF-1.7\nCooling system design"

    upload_response = client.post(
        f"/documents/{document['id']}/versions",
        files={"file": ("cooling-design.pdf", file_content, "application/pdf")},
    )

    assert upload_response.status_code == 201
    uploaded_version = upload_response.json()

    assert uploaded_version["document_id"] == document["id"]
    assert uploaded_version["version_number"] == 1
    assert uploaded_version["file_name"] == "cooling-design.pdf"
    assert uploaded_version["content_type"] == "application/pdf"
    assert uploaded_version["size_bytes"] == len(file_content)
    assert uploaded_version["checksum_sha256"] == sha256(file_content).hexdigest()

    created_at = datetime.fromisoformat(uploaded_version["created_at"])

    assert created_at.tzinfo is not None

    stored_files = [path for path in document_storage_path.rglob("*") if path.is_file()]

    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == file_content

    UUID(uploaded_version["id"])


def test_returns_404_when_uploading_to_unknown_document(
    client,
    document_storage_path,
):
    response = client.post(
        f"/documents/{uuid4()}/versions",
        files={
            "file": (
                "cooling-design.pdf",
                b"%PDF-1.7\nCooling system design",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}

    stored_files = [path for path in document_storage_path.rglob("*") if path.is_file()]

    assert stored_files == []


def test_rejects_empty_document_file(
    client,
    document_storage_path,
):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201

    document = create_response.json()

    response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design.pdf",
                b"",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Document file cannot be empty"}

    stored_files = [path for path in document_storage_path.rglob("*") if path.is_file()]

    assert stored_files == []


def test_rejects_unsupported_document_file_type(
    client,
    document_storage_path,
):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201

    document = create_response.json()

    response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design.txt",
                b"Cooling system design",
                "text/plain",
            )
        },
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Only PDF files are supported"}

    stored_files = [path for path in document_storage_path.rglob("*") if path.is_file()]

    assert stored_files == []


def test_rejects_invalid_pdf_content(
    client,
    document_storage_path,
):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201

    document = create_response.json()

    response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design.pdf",
                b"This is not actually a PDF",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Uploaded content is not a valid PDF"}

    stored_files = [path for path in document_storage_path.rglob("*") if path.is_file()]

    assert stored_files == []


def test_uploads_subsequent_document_versions(
    client,
    document_storage_path,
):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201

    document = create_response.json()

    uploaded_versions = []
    file_contents = (
        b"%PDF-1.7\nCooling system version one",
        b"%PDF-1.7\nCooling system version two",
    )

    for version_number, content in enumerate(
        file_contents,
        start=1,
    ):
        response = client.post(
            f"/documents/{document['id']}/versions",
            files={
                "file": (
                    f"cooling-design-v{version_number}.pdf",
                    content,
                    "application/pdf",
                )
            },
        )

        assert response.status_code == 201
        uploaded_versions.append(response.json())

    assert [version["version_number"] for version in uploaded_versions] == [1, 2]

    assert uploaded_versions[0]["id"] != uploaded_versions[1]["id"]

    stored_files = [path for path in document_storage_path.rglob("*") if path.is_file()]

    assert len(stored_files) == 2
    assert {path.read_bytes() for path in stored_files} == set(file_contents)
