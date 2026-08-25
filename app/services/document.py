from sqlalchemy.orm import Session

from app.domain import (
    DocumentStatus,
    InvalidDocumentStatusTransition,
    validate_document_status_transition,
)
from app.models.document import Document
from app.repositories import document as document_repository


def transition_document_status(
    session: Session, *, document: Document, target_status: DocumentStatus
) -> Document:
    current_status = DocumentStatus(document.status)
    validate_document_status_transition(current_status, target_status)

    return document_repository.update_document_status(
        session, document=document, status=target_status
    )


def retry_failed_document(
    session: Session,
    *,
    document: Document,
) -> Document:
    current_status = DocumentStatus(document.status)

    if current_status != DocumentStatus.FAILED:
        raise InvalidDocumentStatusTransition(
            current_status,
            DocumentStatus.PENDING,
        )

    return document_repository.update_document_status(
        session,
        document=document,
        status=DocumentStatus.PENDING,
    )
