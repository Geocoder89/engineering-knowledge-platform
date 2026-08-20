from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.document import DocumentStatus
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


def list_documents(
    session: Session, *, offset: int, limit: int, status: DocumentStatus | None = None
) -> list[Document]:
    statement = select(Document)
    if status is not None:
        statement = statement.where(Document.status == status)
    statement = (
        statement.order_by(Document.created_at.desc(), Document.id.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(session.scalars(statement).all())


def count_documents(
    session: Session,
    *,
    status: DocumentStatus | None = None,
) -> int:
    statement = select(func.count()).select_from(Document)
    if status is not None:
        statement = statement.where(
            Document.status == status.value,
        )

    return session.scalar(statement) or 0


def update_document_status(
    session: Session, *, document: Document, status: DocumentStatus
) -> Document:
    document.status = status.value
    session.flush()
    return document
