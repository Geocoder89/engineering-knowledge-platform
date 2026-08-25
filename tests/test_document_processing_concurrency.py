from datetime import datetime, timezone

from sqlalchemy import delete

from app.database import SessionLocal
from app.models.document import Document
from app.models.document_processing_job import (
    DocumentProcessingJob,
)
from app.models.document_version import DocumentVersion
from app.repositories import (
    document_processing_job as processing_job_repository,
)


def test_two_sessions_claim_different_processing_jobs() -> None:
    with SessionLocal.begin() as setup_session:
        document = Document(
            title="Concurrent processing",
            file_name="concurrent-processing.pdf",
            status="pending",
        )
        setup_session.add(document)
        setup_session.flush()

        document_versions = [
            DocumentVersion(
                document_id=document.id,
                version_number=version_number,
                file_name=f"concurrent-v{version_number}.pdf",
                content_type="application/pdf",
                size_bytes=100,
                checksum_sha256=checksum_character * 64,
                storage_key=(f"{document.id}/version-{version_number}"),
            )
            for version_number, checksum_character in (
                (1, "a"),
                (2, "b"),
            )
        ]
        setup_session.add_all(document_versions)
        setup_session.flush()

        processing_jobs = [
            DocumentProcessingJob(
                document_version_id=document_version.id,
                created_at=datetime(
                    2000,
                    1,
                    index,
                    tzinfo=timezone.utc,
                ),
            )
            for index, document_version in enumerate(
                document_versions,
                start=1,
            )
        ]
        setup_session.add_all(processing_jobs)
        setup_session.flush()

        document_id = document.id
        document_version_ids = [
            document_version.id for document_version in document_versions
        ]
        expected_job_ids = [processing_job.id for processing_job in processing_jobs]

    try:
        with (
            SessionLocal() as first_session,
            SessionLocal() as second_session,
        ):
            with first_session.begin():
                first_claimed_job = processing_job_repository.claim_next_processing_job(
                    first_session
                )

                assert first_claimed_job is not None
                assert first_claimed_job.id == expected_job_ids[0]

                with second_session.begin():
                    second_claimed_job = (
                        processing_job_repository.claim_next_processing_job(
                            second_session
                        )
                    )

                    assert second_claimed_job is not None
                    assert second_claimed_job.id == expected_job_ids[1]
                    assert second_claimed_job.id != first_claimed_job.id

                assert first_claimed_job.status == "processing"
                assert first_claimed_job.attempt_count == 1
                assert second_claimed_job.status == "processing"
                assert second_claimed_job.attempt_count == 1
    finally:
        with SessionLocal.begin() as cleanup_session:
            cleanup_session.execute(
                delete(DocumentProcessingJob).where(
                    DocumentProcessingJob.id.in_(expected_job_ids)
                )
            )
            cleanup_session.execute(
                delete(DocumentVersion).where(
                    DocumentVersion.id.in_(document_version_ids)
                )
            )
            cleanup_session.execute(delete(Document).where(Document.id == document_id))


def test_rolled_back_claim_returns_job_to_queue() -> None:
    with SessionLocal.begin() as setup_session:
        document = Document(
            title="Rollback processing",
            file_name="rollback-processing.pdf",
            status="pending",
        )
        setup_session.add(document)
        setup_session.flush()

        document_version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            file_name="rollback-processing.pdf",
            content_type="application/pdf",
            size_bytes=100,
            checksum_sha256="c" * 64,
            storage_key=f"{document.id}/version-1",
        )
        setup_session.add(document_version)
        setup_session.flush()

        processing_job = DocumentProcessingJob(
            document_version_id=document_version.id,
            created_at=datetime(
                1999,
                1,
                1,
                tzinfo=timezone.utc,
            ),
        )
        setup_session.add(processing_job)
        setup_session.flush()

        document_id = document.id
        document_version_id = document_version.id
        processing_job_id = processing_job.id

    claiming_session = SessionLocal()
    claiming_transaction = claiming_session.begin()

    try:
        claimed_job = processing_job_repository.claim_next_processing_job(
            claiming_session
        )

        assert claimed_job is not None
        assert claimed_job.id == processing_job_id
        assert claimed_job.status == "processing"
        assert claimed_job.attempt_count == 1
    finally:
        if claiming_transaction.is_active:
            claiming_transaction.rollback()

        claiming_session.close()

    try:
        with SessionLocal.begin() as verification_session:
            rolled_back_job = verification_session.get(
                DocumentProcessingJob,
                processing_job_id,
            )

            assert rolled_back_job is not None
            assert rolled_back_job.status == "queued"
            assert rolled_back_job.attempt_count == 0
            assert rolled_back_job.started_at is None

            reclaimed_job = processing_job_repository.claim_next_processing_job(
                verification_session
            )

            assert reclaimed_job is not None
            assert reclaimed_job.id == processing_job_id
            assert reclaimed_job.status == "processing"
            assert reclaimed_job.attempt_count == 1
    finally:
        with SessionLocal.begin() as cleanup_session:
            cleanup_session.execute(
                delete(DocumentProcessingJob).where(
                    DocumentProcessingJob.id == processing_job_id
                )
            )
            cleanup_session.execute(
                delete(DocumentVersion).where(DocumentVersion.id == document_version_id)
            )
            cleanup_session.execute(delete(Document).where(Document.id == document_id))
