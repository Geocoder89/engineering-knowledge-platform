from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document import Document


def create_document(session: Session, *, title: str, file_name: str) -> Document:
    document = Document(
        title=title,
        file_name=file_name,
        status="pending",
    )
    session.add(document)
    session.flush()
    return document


def get_document_by_id(
    session: Session,
    document_id: UUID,
) -> Document | None:
    return session.get(Document, document_id)
