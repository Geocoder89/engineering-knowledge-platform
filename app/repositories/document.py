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
    if status is None:
        status_condition = Document.status != DocumentStatus.ARCHIVED.value
    else:
        status_condition = Document.status == status.value
    statement = statement.where(status_condition)
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
    count_statement = select(func.count()).select_from(Document)
    if status is None:
        status_condition = Document.status != DocumentStatus.ARCHIVED.value
    else:
        status_condition = Document.status == status.value

    count_statement = count_statement.where(status_condition)
    return session.scalar(count_statement) or 0


def update_document_status(
    session: Session, *, document: Document, status: DocumentStatus
) -> Document:
    document.status = status.value
    session.flush()
    return document


def update_document_metadata(
    session: Session,
    *,
    document: Document,
    title: str | None = None,
    file_name: str | None = None,
) -> Document:
    if title is not None:
        document.title = title

    if file_name is not None:
        document.file_name = file_name

    session.flush()

    return document
