from sqlalchemy.orm import Session

from app.domain.document import DocumentStatus
from app.domain.document_version import DocumentContentIntegrityError
from app.extraction.base import DocumentTextExtractionError
from app.models.document import Document
from app.models.document_processing_job import DocumentProcessingJob
from app.models.document_version import DocumentVersion
from app.repositories import document as document_repository
from app.repositories import document_processing_job as processing_job_repository
from app.services import document as document_service
from app.services import document_version as document_version_service
from app.storage.base import DocumentStorage


def process_document_job(
    session: Session, storage: DocumentStorage, *, processing_job: DocumentProcessingJob
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

    document_service.transition_document_status(
        session, document=document, target_status=DocumentStatus.PROCESSING
    )

    try:
        with session.begin_nested():
            document_version_service.extract_document_version_pages(
                session, storage, document_version=document_version
            )
    except (
        FileNotFoundError,
        DocumentContentIntegrityError,
        DocumentTextExtractionError,
    ) as error:
        processing_job_repository.fail_processing_job(
            session, processing_job=processing_job, error_message=str(error)
        )

        document_service.transition_document_status(
            session, document=document, target_status=DocumentStatus.FAILED
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
