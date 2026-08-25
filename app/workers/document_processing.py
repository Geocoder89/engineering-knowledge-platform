import time
from typing import NoReturn

from sqlalchemy.orm import Session

from app.database import SessionLocal
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

POLL_INTERVAL_SECONDS = 1.0


def process_next_document_job(
    session: Session,
    storage: DocumentStorage,
) -> DocumentProcessingJob | None:
    processing_job = processing_job_repository.claim_next_processing_job(
        session,
    )

    if processing_job is None:
        return None

    return document_processing_service.process_document_job(
        session,
        storage,
        processing_job=processing_job,
    )


def run_document_processing_worker() -> NoReturn:
    storage = get_document_storage()

    while True:
        with SessionLocal.begin() as session:
            processed_job = process_next_document_job(
                session,
                storage,
            )

        if processed_job is None:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_document_processing_worker()
