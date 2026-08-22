from datetime import datetime
from hashlib import sha256
from uuid import UUID, uuid4

from app.config import settings


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


def test_lists_document_versions_with_pagination(client):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201

    document = create_response.json()

    for version_number in range(1, 4):
        upload_response = client.post(
            f"/documents/{document['id']}/versions",
            files={
                "file": (
                    f"cooling-design-v{version_number}.pdf",
                    (f"%PDF-1.7\nCooling system version {version_number}").encode(),
                    "application/pdf",
                )
            },
        )

        assert upload_response.status_code == 201

    first_response = client.get(
        f"/documents/{document['id']}/versions?offset=0&limit=2"
    )

    assert first_response.status_code == 200

    first_page = first_response.json()

    assert first_page["total"] == 3
    assert first_page["offset"] == 0
    assert first_page["limit"] == 2
    assert [version["version_number"] for version in first_page["items"]] == [3, 2]

    second_response = client.get(
        f"/documents/{document['id']}/versions?offset=2&limit=2"
    )

    assert second_response.status_code == 200

    second_page = second_response.json()

    assert second_page["total"] == 3
    assert second_page["offset"] == 2
    assert second_page["limit"] == 2
    assert [version["version_number"] for version in second_page["items"]] == [1]


def test_rejects_invalid_document_version_pagination(client):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201

    document = create_response.json()

    response = client.get(f"/documents/{document['id']}/versions?offset=-1&limit=0")

    assert response.status_code == 422


def test_returns_404_when_listing_versions_for_unknown_document(client):
    response = client.get(f"/documents/{uuid4()}/versions")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_retrieves_document_version_metadata(client):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201

    document = create_response.json()

    upload_response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design.pdf",
                b"%PDF-1.7\nCooling system design",
                "application/pdf",
            )
        },
    )
    assert upload_response.status_code == 201

    uploaded_version = upload_response.json()

    response = client.get(f"/documents/{document['id']}/versions/1")

    assert response.status_code == 200
    assert response.json() == uploaded_version


def test_returns_404_for_unknown_document_version(client):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201

    document = create_response.json()

    response = client.get(f"/documents/{document['id']}/versions/99")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document version not found"}


def test_returns_404_when_retrieving_version_for_unknown_document(client):
    response = client.get(f"/documents/{uuid4()}/versions/1")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_rejects_invalid_document_version_number(client):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201

    document = create_response.json()

    response = client.get(f"/documents/{document['id']}/versions/0")

    assert response.status_code == 422


def test_downloads_document_version_content(client):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201

    document = create_response.json()
    file_content = b"%PDF-1.7\nCooling system design"

    upload_response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design.pdf",
                file_content,
                "application/pdf",
            )
        },
    )
    assert upload_response.status_code == 201

    response = client.get(f"/documents/{document['id']}/versions/1/content")

    assert response.status_code == 200
    assert response.content == file_content
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''cooling-design.pdf"
    )
    assert response.headers["x-content-type-options"] == "nosniff"


def test_returns_404_when_downloading_unknown_document_version(client):
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201

    document = create_response.json()

    response = client.get(f"/documents/{document['id']}/versions/99/content")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document version not found"}


def test_returns_404_when_downloading_from_unknown_document(client):
    response = client.get(f"/documents/{uuid4()}/versions/1/content")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_returns_404_when_document_version_content_is_missing(
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

    upload_response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design.pdf",
                b"%PDF-1.7\nCooling system design",
                "application/pdf",
            )
        },
    )
    assert upload_response.status_code == 201

    stored_file = next(
        path for path in document_storage_path.rglob("*") if path.is_file()
    )
    stored_file.unlink()

    response = client.get(f"/documents/{document['id']}/versions/1/content")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document content not found"}


def test_rejects_corrupted_document_version_content(
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

    upload_response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design.pdf",
                b"%PDF-1.7\nCooling system design",
                "application/pdf",
            )
        },
    )
    assert upload_response.status_code == 201

    stored_file = next(
        path for path in document_storage_path.rglob("*") if path.is_file()
    )
    stored_file.write_bytes(b"corrupted content")

    response = client.get(f"/documents/{document['id']}/versions/1/content")

    assert response.status_code == 409
    assert response.json() == {"detail": "Document content failed integrity check"}


def test_accepts_document_file_at_upload_limit(
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

    maximum_size_bytes = settings.document_max_upload_size_bytes
    pdf_header = b"%PDF-1.7\n"
    file_content = pdf_header + (b"x" * (maximum_size_bytes - len(pdf_header)))

    assert len(file_content) == maximum_size_bytes

    upload_response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design.pdf",
                file_content,
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 201

    uploaded_version = upload_response.json()

    assert uploaded_version["size_bytes"] == maximum_size_bytes

    stored_files = [path for path in document_storage_path.rglob("*") if path.is_file()]

    assert len(stored_files) == 1
    assert stored_files[0].stat().st_size == maximum_size_bytes


def test_rejects_document_file_exceeding_upload_limit(
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

    maximum_size_bytes = settings.document_max_upload_size_bytes
    oversized_content = b"%PDF-1.7\n" + (b"x" * maximum_size_bytes)

    upload_response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design.pdf",
                oversized_content,
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code == 413
    assert upload_response.json() == {
        "detail": "Document file exceeds maximum upload size"
    }

    versions_response = client.get(f"/documents/{document['id']}/versions")
    assert versions_response.status_code == 200
    assert versions_response.json()["total"] == 0

    stored_files = [path for path in document_storage_path.rglob("*") if path.is_file()]
    assert stored_files == []
