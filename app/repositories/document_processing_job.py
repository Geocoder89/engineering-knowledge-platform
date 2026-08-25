from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_processing_job import (
    DocumentProcessingJob,
)


def get_processing_job_by_document_version(
    session: Session,
    *,
    document_version_id: UUID,
) -> DocumentProcessingJob | None:
    statement = select(DocumentProcessingJob).where(
        DocumentProcessingJob.document_version_id == document_version_id
    )

    return session.scalar(statement)


def create_processing_job(
    session: Session,
    *,
    document_version_id: UUID,
) -> DocumentProcessingJob:
    processing_job = DocumentProcessingJob(
        document_version_id=document_version_id,
    )

    session.add(processing_job)
    session.flush()

    return processing_job


def get_or_create_processing_job(
    session: Session,
    *,
    document_version_id: UUID,
) -> DocumentProcessingJob:
    existing_job = get_processing_job_by_document_version(
        session,
        document_version_id=document_version_id,
    )

    if existing_job is not None:
        return existing_job

    return create_processing_job(
        session,
        document_version_id=document_version_id,
    )


def start_processing_job(
    session: Session,
    *,
    processing_job: DocumentProcessingJob,
) -> DocumentProcessingJob:
    processing_job.status = "processing"
    processing_job.attempt_count += 1
    processing_job.started_at = datetime.now(timezone.utc)
    processing_job.completed_at = None
    processing_job.error_message = None

    session.flush()

    return processing_job


def complete_processing_job(
    session: Session,
    *,
    processing_job: DocumentProcessingJob,
) -> DocumentProcessingJob:
    processing_job.status = "completed"
    processing_job.completed_at = datetime.now(timezone.utc)
    processing_job.error_message = None

    session.flush()

    return processing_job


def fail_processing_job(
    session: Session,
    *,
    processing_job: DocumentProcessingJob,
    error_message: str,
) -> DocumentProcessingJob:
    processing_job.status = "failed"
    processing_job.error_message = error_message
    processing_job.completed_at = datetime.now(timezone.utc)

    session.flush()

    return processing_job


def requeue_processing_job(
    session: Session,
    *,
    processing_job: DocumentProcessingJob,
) -> DocumentProcessingJob:
    processing_job.status = "queued"
    processing_job.error_message = None
    processing_job.started_at = None
    processing_job.completed_at = None

    session.flush()

    return processing_job


def claim_next_processing_job(session: Session) -> DocumentProcessingJob | None:
    statement = (
        select(DocumentProcessingJob)
        .where(DocumentProcessingJob.status == "queued")
        .order_by(
            DocumentProcessingJob.created_at,
            DocumentProcessingJob.id,
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    processing_job = session.scalar(statement)

    if processing_job is None:
        return None

    return start_processing_job(session, processing_job=processing_job)
