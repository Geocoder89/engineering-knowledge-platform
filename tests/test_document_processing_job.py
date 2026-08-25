from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import engine
from app.models.document import Document
from app.models.document_processing_job import (
    DocumentProcessingJob,
)
from app.models.document_version import DocumentVersion
from app.repositories import (
    document_processing_job as processing_job_repository,
)


def test_database_persists_queued_document_processing_job() -> None:
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

            processing_job = DocumentProcessingJob(
                document_version_id=document_version.id,
            )
            session.add(processing_job)
            session.flush()

            assert processing_job.id is not None
            assert processing_job.document_version_id == document_version.id
            assert processing_job.status == "queued"
            assert processing_job.attempt_count == 0
            assert processing_job.error_message is None
            assert processing_job.created_at is not None
            assert processing_job.started_at is None
            assert processing_job.completed_at is None
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_repository_reuses_existing_job_for_same_version() -> None:
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

            document_version = DocumentVersion(
                document_id=document.id,
                version_number=1,
                file_name="cooling-design.pdf",
                content_type="application/pdf",
                size_bytes=100,
                checksum_sha256="b" * 64,
                storage_key=f"{document.id}/version-1",
            )
            session.add(document_version)
            session.flush()

            first_job = processing_job_repository.get_or_create_processing_job(
                session,
                document_version_id=document_version.id,
            )
            second_job = processing_job_repository.get_or_create_processing_job(
                session,
                document_version_id=document_version.id,
            )

            assert second_job.id == first_job.id
            assert second_job.status == "queued"
            assert second_job.attempt_count == 0

            statement = (
                select(func.count())
                .select_from(DocumentProcessingJob)
                .where(DocumentProcessingJob.document_version_id == document_version.id)
            )

            assert session.scalar(statement) == 1
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_repository_transitions_job_through_successful_processing() -> None:
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

            document_version = DocumentVersion(
                document_id=document.id,
                version_number=1,
                file_name="cooling-design.pdf",
                content_type="application/pdf",
                size_bytes=100,
                checksum_sha256="c" * 64,
                storage_key=f"{document.id}/version-1",
            )
            session.add(document_version)
            session.flush()

            processing_job = processing_job_repository.get_or_create_processing_job(
                session,
                document_version_id=document_version.id,
            )

            started_job = processing_job_repository.start_processing_job(
                session,
                processing_job=processing_job,
            )

            assert started_job.status == "processing"
            assert started_job.attempt_count == 1
            assert started_job.started_at is not None
            assert started_job.completed_at is None
            assert started_job.error_message is None

            completed_job = processing_job_repository.complete_processing_job(
                session,
                processing_job=started_job,
            )

            assert completed_job.status == "completed"
            assert completed_job.attempt_count == 1
            assert completed_job.started_at is not None
            assert completed_job.completed_at is not None
            assert completed_job.error_message is None
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_repository_requeues_failed_job_for_retry() -> None:
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

            document_version = DocumentVersion(
                document_id=document.id,
                version_number=1,
                file_name="cooling-design.pdf",
                content_type="application/pdf",
                size_bytes=100,
                checksum_sha256="d" * 64,
                storage_key=f"{document.id}/version-1",
            )
            session.add(document_version)
            session.flush()

            processing_job = processing_job_repository.get_or_create_processing_job(
                session,
                document_version_id=document_version.id,
            )
            processing_job_repository.start_processing_job(
                session,
                processing_job=processing_job,
            )

            failed_job = processing_job_repository.fail_processing_job(
                session,
                processing_job=processing_job,
                error_message="Document text extraction failed",
            )

            assert failed_job.status == "failed"
            assert failed_job.attempt_count == 1
            assert failed_job.error_message == "Document text extraction failed"
            assert failed_job.completed_at is not None

            requeued_job = processing_job_repository.requeue_processing_job(
                session,
                processing_job=failed_job,
            )

            assert requeued_job.status == "queued"
            assert requeued_job.attempt_count == 1
            assert requeued_job.error_message is None
            assert requeued_job.started_at is None
            assert requeued_job.completed_at is None

            retried_job = processing_job_repository.start_processing_job(
                session,
                processing_job=requeued_job,
            )

            assert retried_job.status == "processing"
            assert retried_job.attempt_count == 2
            assert retried_job.started_at is not None
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_repository_claims_queued_jobs_once() -> None:
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

            document_versions = [
                DocumentVersion(
                    document_id=document.id,
                    version_number=version_number,
                    file_name=f"cooling-design-v{version_number}.pdf",
                    content_type="application/pdf",
                    size_bytes=100,
                    checksum_sha256=checksum_character * 64,
                    storage_key=(f"{document.id}/version-{version_number}"),
                )
                for (
                    version_number,
                    checksum_character,
                ) in (
                    (1, "e"),
                    (2, "f"),
                )
            ]
            session.add_all(document_versions)
            session.flush()

            for document_version in document_versions:
                processing_job_repository.create_processing_job(
                    session,
                    document_version_id=document_version.id,
                )

            first_claimed_job = processing_job_repository.claim_next_processing_job(
                session
            )
            second_claimed_job = processing_job_repository.claim_next_processing_job(
                session
            )
            no_remaining_job = processing_job_repository.claim_next_processing_job(
                session
            )

            assert first_claimed_job is not None
            assert second_claimed_job is not None
            assert first_claimed_job.id != second_claimed_job.id
            assert first_claimed_job.status == "processing"
            assert second_claimed_job.status == "processing"
            assert first_claimed_job.attempt_count == 1
            assert second_claimed_job.attempt_count == 1
            assert no_remaining_job is None
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()
