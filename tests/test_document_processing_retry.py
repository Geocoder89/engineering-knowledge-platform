from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.database import engine
from app.domain.document import DocumentStatus
from app.models.document import Document
from app.repositories import document_processing_job as processing_job_repository
from app.repositories import document_version as document_version_repository
from app.services import document as document_service
from app.services import (
    document_processing as document_processing_service,
)
from app.services import document_version as document_version_service
from app.storage.local import LocalDocumentStorage
from tests.test_pdf_extraction import build_pdf_with_pages


def test_retries_failed_document_processing(
    tmp_path: Path,
) -> None:
    connection = engine.connect()
    outer_transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            storage = LocalDocumentStorage(
                root_path=tmp_path / "document-storage",
            )
            document = Document(
                title="Cooling system",
                file_name="cooling-design.pdf",
                status="pending",
            )
            session.add(document)
            session.flush()

            document_version = document_version_service.upload_document_version(
                session,
                storage,
                document_id=document.id,
                file_name="cooling-design.pdf",
                content_type="application/pdf",
                content=build_pdf_with_pages(("Cooling system requirements",)),
            )
            processing_job = (
                processing_job_repository.get_processing_job_by_document_version(
                    session,
                    document_version_id=document_version.id,
                )
            )

            assert processing_job is not None

            processing_job_repository.start_processing_job(
                session,
                processing_job=processing_job,
            )
            document_service.transition_document_status(
                session,
                document=document,
                target_status=DocumentStatus.PROCESSING,
            )
            processing_job_repository.fail_processing_job(
                session,
                processing_job=processing_job,
                error_message="Temporary processing failure",
            )
            document_service.transition_document_status(
                session,
                document=document,
                target_status=DocumentStatus.FAILED,
            )

            retried_job = document_processing_service.retry_document_processing_job(
                session,
                document=document,
                processing_job=processing_job,
            )

            assert retried_job.status == "queued"
            assert retried_job.attempt_count == 1
            assert retried_job.error_message is None
            assert retried_job.started_at is None
            assert retried_job.completed_at is None
            assert document.status == "pending"
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_retries_failed_document_version_through_api(
    client,
    db_session: Session,
) -> None:
    create_response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )
    assert create_response.status_code == 201
    created_document = create_response.json()

    upload_response = client.post(
        f"/documents/{created_document['id']}/versions",
        files={
            "file": (
                "cooling-design.pdf",
                build_pdf_with_pages(("Cooling system requirements",)),
                "application/pdf",
            )
        },
    )
    assert upload_response.status_code == 201
    uploaded_version = upload_response.json()

    document_id = UUID(created_document["id"])
    document = db_session.get(Document, document_id)
    assert document is not None

    document_version = document_version_repository.get_document_version_by_number(
        db_session,
        document_id=document_id,
        version_number=uploaded_version["version_number"],
    )
    assert document_version is not None

    processing_job = processing_job_repository.get_processing_job_by_document_version(
        db_session,
        document_version_id=document_version.id,
    )
    assert processing_job is not None

    processing_job_repository.start_processing_job(
        db_session,
        processing_job=processing_job,
    )
    document_service.transition_document_status(
        db_session,
        document=document,
        target_status=DocumentStatus.PROCESSING,
    )
    processing_job_repository.fail_processing_job(
        db_session,
        processing_job=processing_job,
        error_message="Temporary processing failure",
    )
    document_service.transition_document_status(
        db_session,
        document=document,
        target_status=DocumentStatus.FAILED,
    )
    db_session.commit()

    retry_url = (
        f"/documents/{document_id}/versions/{uploaded_version['version_number']}/retry"
    )

    response = client.post(retry_url)

    assert response.status_code == 200
    assert response.json()["id"] == str(document_id)
    assert response.json()["status"] == "pending"

    duplicate_retry_response = client.post(retry_url)
    assert duplicate_retry_response.status_code == 409

    assert duplicate_retry_response.json() == {
        "detail": (
            "Only failed processing jobs can be retried; current status is 'queued'"
        )
    }

    db_session.expire_all()

    refreshed_document = db_session.get(Document, document_id)
    refreshed_job = processing_job_repository.get_processing_job_by_document_version(
        db_session,
        document_version_id=document_version.id,
    )

    assert refreshed_document is not None
    assert refreshed_document.status == "pending"
    assert refreshed_job is not None
    assert refreshed_job.status == "queued"
    assert refreshed_job.attempt_count == 1
    assert refreshed_job.error_message is None
    assert refreshed_job.started_at is None
    assert refreshed_job.completed_at is None
