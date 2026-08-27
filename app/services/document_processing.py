from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.chunking.text import chunk_text
from app.domain.document import DocumentStatus
from app.domain.document_processing_job import (
    MAX_PROCESSING_ATTEMPTS,
)
from app.domain.document_version import DocumentContentIntegrityError
from app.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    InvalidEmbeddingResponseError,
)
from app.extraction.base import DocumentTextExtractionError
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_processing_job import DocumentProcessingJob
from app.models.document_version import DocumentVersion
from app.repositories import document as document_repository
from app.repositories import document_chunk as document_chunk_repository
from app.repositories import document_processing_job as processing_job_repository
from app.services import document as document_service
from app.services import document_embedding as document_embedding_service
from app.services import document_version as document_version_service
from app.storage.base import DocumentStorage


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


DOCUMENT_CHUNK_MAX_CHARACTERS = 1200
DOCUMENT_CHUNK_OVERLAP_CHARACTERS = 200


def process_document_job(
    session: Session,
    storage: DocumentStorage,
    *,
    embedding_provider: EmbeddingProvider,
    processing_job: DocumentProcessingJob,
) -> DocumentProcessingJob:
    document_version = session.get(DocumentVersion, processing_job.document_version_id)

    if document_version is None:
        raise RuntimeError("Processing job document version was not found")

    document = document_repository.get_document_by_id(
        session, document_version.document_id
    )

    if document is None:
        raise RuntimeError("Processing job document was not found")

    # processing_job_repository.start_processing_job(
    #     session, processing_job=processing_job
    # )

    current_document_status = DocumentStatus(document.status)

    if current_document_status == DocumentStatus.PENDING:
        document_service.transition_document_status(
            session,
            document=document,
            target_status=DocumentStatus.PROCESSING,
        )
    elif current_document_status != DocumentStatus.PROCESSING:
        raise RuntimeError(
            "Document must be pending or processing to run a processing job"
        )
    try:
        with session.begin_nested():
            document_pages = document_version_service.extract_document_version_pages(
                session, storage, document_version=document_version
            )
            document_chunks: list[DocumentChunk] = []

            for document_page in document_pages:
                chunks = chunk_text(
                    document_page.text,
                    max_characters=(DOCUMENT_CHUNK_MAX_CHARACTERS),
                    overlap_characters=(DOCUMENT_CHUNK_OVERLAP_CHARACTERS),
                )

                persisted_chunks = document_chunk_repository.replace_document_chunks(
                    session, document_page_id=document_page.id, chunks=chunks
                )
                document_chunks.extend(persisted_chunks)

            document_embedding_service.embed_document_chunks(
                session,
                embedding_provider=embedding_provider,
                document_chunks=document_chunks,
            )

    except (
        FileNotFoundError,
        DocumentContentIntegrityError,
        DocumentTextExtractionError,
        InvalidEmbeddingResponseError,
    ) as error:
        processing_job_repository.fail_processing_job(
            session, processing_job=processing_job, error_message=str(error)
        )

        document_service.transition_document_status(
            session, document=document, target_status=DocumentStatus.FAILED
        )
        return processing_job
    except EmbeddingProviderError as error:
        if processing_job.attempt_count >= MAX_PROCESSING_ATTEMPTS:
            processing_job_repository.fail_processing_job(
                session,
                processing_job=processing_job,
                error_message=str(error),
            )

            document_service.transition_document_status(
                session,
                document=document,
                target_status=DocumentStatus.FAILED,
            )
            return processing_job

        processing_job_repository.schedule_processing_job_retry(
            session,
            processing_job=processing_job,
            error_message=str(error),
            attempted_at=utc_now(),
        )

        return processing_job

    processing_job_repository.complete_processing_job(
        session, processing_job=processing_job
    )
    document_service.transition_document_status(
        session, document=document, target_status=DocumentStatus.READY
    )

    return processing_job


def retry_document_processing_job(
    session: Session, *, document: Document, processing_job: DocumentProcessingJob
) -> DocumentProcessingJob:
    requeued_job = processing_job_repository.requeue_processing_job(
        session, processing_job=processing_job
    )

    document_service.retry_failed_document(session, document=document)

    return requeued_job
