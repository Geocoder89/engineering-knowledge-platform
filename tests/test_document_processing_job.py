from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import engine
from app.domain import document_processing_job as processing_job_domain
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


def test_repository_rejects_requeue_after_maximum_attempts() -> None:
    session = Mock(spec=Session)
    processing_job = DocumentProcessingJob(
        document_version_id=uuid4(),
        status="failed",
        attempt_count=3,
    )

    with pytest.raises(
        ValueError,
        match=("Processing job has reached the maximum of 3 attempts"),
    ):
        processing_job_repository.requeue_processing_job(
            session,
            processing_job=processing_job,
        )

    session.flush.assert_not_called()


def test_repository_claims_only_jobs_whose_retry_time_has_arrived() -> None:
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
                    storage_key=f"{document.id}/version-{version_number}",
                )
                for version_number, checksum_character in (
                    (1, "g"),
                    (2, "h"),
                )
            ]
            session.add_all(document_versions)
            session.flush()

            now = datetime.now(timezone.utc)

            delayed_job = DocumentProcessingJob(
                document_version_id=document_versions[0].id,
                created_at=now - timedelta(minutes=1),
                next_attempt_at=now + timedelta(hours=1),
            )
            available_job = DocumentProcessingJob(
                document_version_id=document_versions[1].id,
                created_at=now,
                next_attempt_at=None,
            )
            session.add_all(
                [
                    delayed_job,
                    available_job,
                ]
            )
            session.flush()

            claimed_job = processing_job_repository.claim_next_processing_job(session)
            no_due_job = processing_job_repository.claim_next_processing_job(session)

            assert claimed_job is not None
            assert claimed_job.id == available_job.id
            assert claimed_job.status == "processing"
            assert claimed_job.attempt_count == 1
            assert claimed_job.next_attempt_at is None

            assert no_due_job is None
            assert delayed_job.status == "queued"
            assert delayed_job.attempt_count == 0

            delayed_job.next_attempt_at = now - timedelta(seconds=1)
            session.flush()

            retried_job = processing_job_repository.claim_next_processing_job(session)

            assert retried_job is not None
            assert retried_job.id == delayed_job.id
            assert retried_job.status == "processing"
            assert retried_job.attempt_count == 1
            assert retried_job.next_attempt_at is None
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_repository_rejects_requeue_when_job_is_not_failed() -> None:
    session = Mock(spec=Session)
    processing_job = DocumentProcessingJob(
        document_version_id=uuid4(),
        status="completed",
        attempt_count=1,
    )

    with pytest.raises(
        ValueError,
        match=(
            "Only failed processing jobs can be retried; current status is 'completed'"
        ),
    ):
        processing_job_repository.requeue_processing_job(
            session,
            processing_job=processing_job,
        )

    session.flush.assert_not_called()


@pytest.mark.parametrize(
    (
        "attempt_count",
        "expected_delay",
    ),
    [
        (
            1,
            timedelta(seconds=30),
        ),
        (
            2,
            timedelta(seconds=60),
        ),
    ],
)
def test_calculates_exponential_processing_retry_time(
    attempt_count: int,
    expected_delay: timedelta,
) -> None:
    attempted_at = datetime(
        2026,
        8,
        27,
        16,
        0,
        tzinfo=timezone.utc,
    )

    next_attempt_at = processing_job_domain.calculate_processing_job_retry_at(
        attempted_at=attempted_at,
        attempt_count=attempt_count,
    )

    assert next_attempt_at == attempted_at + expected_delay


def test_repository_schedules_processing_job_for_delayed_retry() -> None:
    session = Mock(spec=Session)
    attempted_at = datetime(
        2026,
        8,
        27,
        16,
        0,
        tzinfo=timezone.utc,
    )
    processing_job = DocumentProcessingJob(
        document_version_id=uuid4(),
        status="processing",
        attempt_count=1,
        started_at=attempted_at,
    )

    scheduled_job = processing_job_repository.schedule_processing_job_retry(
        session,
        processing_job=processing_job,
        error_message="OpenAI embedding request failed",
        attempted_at=attempted_at,
    )

    assert scheduled_job is processing_job
    assert scheduled_job.status == "queued"
    assert scheduled_job.attempt_count == 1
    assert scheduled_job.error_message == "OpenAI embedding request failed"
    assert scheduled_job.started_at is None
    assert scheduled_job.completed_at is None
    assert scheduled_job.next_attempt_at == (attempted_at + timedelta(seconds=30))

    session.flush.assert_called_once_with()
