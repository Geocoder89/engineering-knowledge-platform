import logging
import signal
from threading import Event
from types import FrameType

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.embeddings.base import EmbeddingProvider
from app.embeddings.dependencies import get_embedding_provider
from app.models.document_processing_job import (
    DocumentProcessingJob,
)
from app.repositories import (
    document_processing_job as processing_job_repository,
)
from app.services import (
    document_processing as document_processing_service,
)
from app.storage.base import DocumentStorage
from app.storage.dependencies import get_document_storage

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = settings.document_processing_poll_interval_seconds


def process_next_document_job(
    session: Session,
    storage: DocumentStorage,
    *,
    embedding_provider: EmbeddingProvider,
) -> DocumentProcessingJob | None:
    processing_job = processing_job_repository.claim_next_processing_job(
        session,
    )

    if processing_job is None:
        return None

    logger.info(
        "Document processing job claimed",
        extra={
            "processing_job_id": str(processing_job.id),
            "document_version_id": str(processing_job.document_version_id),
            "attempt_count": processing_job.attempt_count,
        },
    )

    return document_processing_service.process_document_job(
        session,
        storage,
        embedding_provider=embedding_provider,
        processing_job=processing_job,
    )


def install_shutdown_signal_handlers(
    stop_event: Event,
) -> None:
    def request_shutdown(
        signal_number: int,
        _frame: FrameType | None,
    ) -> None:
        logger.info(
            "Document processing worker shutdown requested",
            extra={
                "signal_number": signal_number,
            },
        )
        stop_event.set()

    signal.signal(
        signal.SIGINT,
        request_shutdown,
    )
    signal.signal(
        signal.SIGTERM,
        request_shutdown,
    )


def run_worker_iteration(
    storage: DocumentStorage,
    *,
    embedding_provider: EmbeddingProvider,
) -> DocumentProcessingJob | None:
    with SessionLocal.begin() as session:
        return process_next_document_job(
            session, storage, embedding_provider=embedding_provider
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=("%(asctime)s %(levelname)s %(name)s %(message)s"),
    )

    stop_event = Event()
    embedding_provider = get_embedding_provider()
    install_shutdown_signal_handlers(stop_event)

    run_document_processing_worker(
        stop_event=stop_event, embedding_provider=embedding_provider
    )


def run_document_processing_worker(
    *,
    embedding_provider: EmbeddingProvider,
    stop_event: Event | None = None,
    storage: DocumentStorage | None = None,
    poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
) -> None:
    shutdown_event = stop_event or Event()
    worker_storage = storage or get_document_storage()

    logger.info(
        "Document processing worker started",
        extra={
            "poll_interval_seconds": poll_interval_seconds,
        },
    )

    try:
        while not shutdown_event.is_set():
            processed_job = run_worker_iteration(
                worker_storage, embedding_provider=embedding_provider
            )

            if processed_job is None:
                shutdown_event.wait(poll_interval_seconds)
                continue

            logger.info(
                "Document processing job finished",
                extra={
                    "processing_job_id": str(processed_job.id),
                    "document_version_id": str(processed_job.document_version_id),
                    "status": processed_job.status,
                    "attempt_count": (processed_job.attempt_count),
                },
            )
    finally:
        logger.info("Document processing worker stopped")


if __name__ == "__main__":
    main()
