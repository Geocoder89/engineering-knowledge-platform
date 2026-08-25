from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.document_processing_job import (
    DocumentProcessingJob,
)
from app.repositories import (
    document_processing_job as processing_job_repository,
)
from app.services import (
    document_processing as document_processing_service,
)
from app.services import document_version as document_version_service
from app.storage.local import LocalDocumentStorage
from app.workers import document_processing as document_processing_worker
from tests.test_pdf_extraction import build_pdf_with_pages


def test_processes_document_job_successfully(
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

            file_content = build_pdf_with_pages(
                (
                    "Cooling system requirements",
                    None,
                    "Electrical system requirements",
                )
            )

            document_version = document_version_service.upload_document_version(
                session,
                storage,
                document_id=document.id,
                file_name="cooling-design.pdf",
                content_type="application/pdf",
                content=file_content,
            )
            processing_job = processing_job_repository.get_or_create_processing_job(
                session,
                document_version_id=document_version.id,
            )

            processing_job_repository.start_processing_job(
                session,
                processing_job=processing_job,
            )

            processed_job = document_processing_service.process_document_job(
                session,
                storage,
                processing_job=processing_job,
            )

            assert processed_job.status == "completed"
            assert processed_job.attempt_count == 1
            assert processed_job.started_at is not None
            assert processed_job.completed_at is not None
            assert processed_job.error_message is None
            assert document.status == "ready"

            statement = (
                select(DocumentPage)
                .where(DocumentPage.document_version_id == document_version.id)
                .order_by(DocumentPage.page_number)
            )

            persisted_pages = list(session.scalars(statement).all())

            assert [
                (
                    page.page_number,
                    page.text,
                    page.requires_ocr,
                )
                for page in persisted_pages
            ] == [
                (1, "Cooling system requirements", False),
                (2, "", True),
                (3, "Electrical system requirements", False),
            ]
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_records_failed_document_processing_job(
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

            original_content = build_pdf_with_pages(("Original cooling requirements",))

            document_version = document_version_service.upload_document_version(
                session,
                storage,
                document_id=document.id,
                file_name="cooling-design.pdf",
                content_type="application/pdf",
                content=original_content,
            )
            processing_job = processing_job_repository.get_or_create_processing_job(
                session,
                document_version_id=document_version.id,
            )

            storage.save(
                key=document_version.storage_key,
                content=build_pdf_with_pages(("Tampered cooling requirements",)),
            )

            processing_job_repository.start_processing_job(
                session,
                processing_job=processing_job,
            )

            failed_job = document_processing_service.process_document_job(
                session,
                storage,
                processing_job=processing_job,
            )

            assert failed_job.status == "failed"
            assert failed_job.attempt_count == 1
            assert failed_job.started_at is not None
            assert failed_job.completed_at is not None
            assert failed_job.error_message == (
                "Document content failed integrity check"
            )
            assert document.status == "failed"

            statement = select(DocumentPage).where(
                DocumentPage.document_version_id == document_version.id
            )

            assert list(session.scalars(statement).all()) == []
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_worker_claims_and_processes_next_queued_job(
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
            queued_job = session.scalar(
                select(DocumentProcessingJob).where(
                    DocumentProcessingJob.document_version_id == document_version.id
                )
            )

            assert queued_job is not None
            assert queued_job.status == "queued"
            assert queued_job.attempt_count == 0

            processed_job = document_processing_worker.process_next_document_job(
                session,
                storage,
            )

            assert processed_job is not None
            assert processed_job.id == queued_job.id
            assert processed_job.status == "completed"
            assert processed_job.attempt_count == 1
            assert document.status == "ready"

            assert (
                document_processing_worker.process_next_document_job(
                    session,
                    storage,
                )
                is None
            )
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()
