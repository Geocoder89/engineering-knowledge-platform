from sqlalchemy.orm import Session

from app.domain import DocumentStatus, validate_document_status_transition
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
