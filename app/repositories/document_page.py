from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.extraction.base import ExtractedDocumentPage
from app.models.document_page import DocumentPage


def replace_document_pages(
    session: Session,
    *,
    document_version_id: UUID,
    pages: tuple[ExtractedDocumentPage, ...],
) -> list[DocumentPage]:
    delete_statement = delete(DocumentPage).where(
        DocumentPage.document_version_id == document_version_id
    )

    session.execute(delete_statement)
    session.flush()

    document_pages = [
        DocumentPage(
            document_version_id=document_version_id,
            page_number=page.page_number,
            text=page.text,
        )
        for page in sorted(
            pages,
            key=lambda page: page.page_number,
        )
    ]

    session.add_all(document_pages)
    session.flush()

    return document_pages
