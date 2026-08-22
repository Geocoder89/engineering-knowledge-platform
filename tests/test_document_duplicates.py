import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import engine
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.repositories import (
    document_version as document_version_repository,
)


def test_rejects_duplicate_content_for_same_document(
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
    file_content = b"%PDF-1.7\nCooling system design"

    first_response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design-v1.pdf",
                file_content,
                "application/pdf",
            )
        },
    )

    assert first_response.status_code == 201

    duplicate_response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design-copy.pdf",
                file_content,
                "application/pdf",
            )
        },
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "This document version has already been uploaded"
    }

    versions_response = client.get(f"/documents/{document['id']}/versions")

    assert versions_response.status_code == 200
    assert versions_response.json()["total"] == 1

    stored_files = [path for path in document_storage_path.rglob("*") if path.is_file()]

    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == file_content


def test_allows_identical_content_for_different_documents(
    client,
    document_storage_path,
):
    file_content = b"%PDF-1.7\nShared engineering reference"
    uploaded_versions = []

    for title, file_name in (
        ("Cooling system", "cooling-design.pdf"),
        ("Electrical system", "electrical-design.pdf"),
    ):
        create_response = client.post(
            "/documents",
            json={
                "title": title,
                "file_name": file_name,
            },
        )
        assert create_response.status_code == 201

        document = create_response.json()

        upload_response = client.post(
            f"/documents/{document['id']}/versions",
            files={
                "file": (
                    file_name,
                    file_content,
                    "application/pdf",
                )
            },
        )

        assert upload_response.status_code == 201
        uploaded_versions.append(upload_response.json())

    assert uploaded_versions[0]["document_id"] != uploaded_versions[1]["document_id"]

    stored_files = [path for path in document_storage_path.rglob("*") if path.is_file()]

    assert len(stored_files) == 2
    assert all(path.read_bytes() == file_content for path in stored_files)


def test_database_rejects_duplicate_content_for_same_document():
    connection = engine.connect()
    outer_transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            document = Document(
                title="Cooling system",
                file_name="cooling-design.pdf",
                status="pending",
            )
            session.add(document)
            session.flush()

            checksum_sha256 = "a" * 64

            first_version = DocumentVersion(
                document_id=document.id,
                version_number=1,
                file_name="cooling-design-v1.pdf",
                content_type="application/pdf",
                size_bytes=100,
                checksum_sha256=checksum_sha256,
                storage_key=f"{document.id}/version-1",
            )
            session.add(first_version)
            session.flush()

            duplicate_version = DocumentVersion(
                document_id=document.id,
                version_number=2,
                file_name="cooling-design-v2.pdf",
                content_type="application/pdf",
                size_bytes=100,
                checksum_sha256=checksum_sha256,
                storage_key=f"{document.id}/version-2",
            )
            session.add(duplicate_version)

            with pytest.raises(IntegrityError):
                session.flush()
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_maps_database_duplicate_race_to_conflict(
    client,
    document_storage_path,
    monkeypatch,
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
    file_content = b"%PDF-1.7\nCooling system design"

    first_response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design-v1.pdf",
                file_content,
                "application/pdf",
            )
        },
    )
    assert first_response.status_code == 201

    def simulate_missed_duplicate(
        session,
        *,
        document_id,
        checksum_sha256,
    ):
        return None

    monkeypatch.setattr(
        document_version_repository,
        "get_document_version_by_checksum",
        simulate_missed_duplicate,
    )

    duplicate_response = client.post(
        f"/documents/{document['id']}/versions",
        files={
            "file": (
                "cooling-design-copy.pdf",
                file_content,
                "application/pdf",
            )
        },
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "This document version has already been uploaded"
    }

    stored_files = [path for path in document_storage_path.rglob("*") if path.is_file()]

    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == file_content
