from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.extraction.base import ExtractedDocumentPage
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion
from app.repositories import document_page as document_page_repository


def create_document_version(
    session: Session,
) -> DocumentVersion:
    document = Document(
        title="Cooling system",
        file_name="cooling-design.pdf",
        status="pending",
    )
    session.add(document)
    session.flush()

    document_version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_name="cooling-design.pdf",
        content_type="application/pdf",
        size_bytes=100,
        checksum_sha256="b" * 64,
        storage_key=f"{document.id}/version-1",
    )
    session.add(document_version)
    session.flush()

    return document_version


def test_database_persists_extracted_document_pages() -> None:
    connection = engine.connect()
    outer_transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            document = Document(
                title="Cooling system",
                file_name="cooling-design.pdf",
                status="pending",
            )
            session.add(document)
            session.flush()

            document_version = DocumentVersion(
                document_id=document.id,
                version_number=1,
                file_name="cooling-design.pdf",
                content_type="application/pdf",
                size_bytes=100,
                checksum_sha256="a" * 64,
                storage_key=f"{document.id}/version-1",
            )
            session.add(document_version)
            session.flush()

            pages = [
                DocumentPage(
                    document_version_id=document_version.id,
                    page_number=1,
                    text="Cooling system requirements",
                ),
                DocumentPage(
                    document_version_id=document_version.id,
                    page_number=2,
                    text="",
                ),
            ]

            session.add_all(pages)
            session.flush()

            statement = (
                select(DocumentPage)
                .where(DocumentPage.document_version_id == document_version.id)
                .order_by(DocumentPage.page_number)
            )

            persisted_pages = list(session.scalars(statement).all())

            assert len(persisted_pages) == 2

            assert persisted_pages[0].page_number == 1
            assert persisted_pages[0].text == "Cooling system requirements"
            assert persisted_pages[0].requires_ocr is False

            assert persisted_pages[1].page_number == 2
            assert persisted_pages[1].text == ""
            assert persisted_pages[1].requires_ocr is True
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_repository_replaces_pages_when_extraction_is_retried() -> None:
    connection = engine.connect()
    outer_transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            document_version = create_document_version(session)

            first_extraction = (
                ExtractedDocumentPage(
                    page_number=1,
                    text="Original cooling requirements",
                ),
            )

            document_page_repository.replace_document_pages(
                session,
                document_version_id=document_version.id,
                pages=first_extraction,
            )

            retried_extraction = (
                ExtractedDocumentPage(
                    page_number=1,
                    text="Updated cooling requirements",
                ),
                ExtractedDocumentPage(
                    page_number=2,
                    text="Electrical requirements",
                ),
            )

            persisted_pages = document_page_repository.replace_document_pages(
                session,
                document_version_id=document_version.id,
                pages=retried_extraction,
            )

            assert len(persisted_pages) == 2
            assert [(page.page_number, page.text) for page in persisted_pages] == [
                (1, "Updated cooling requirements"),
                (2, "Electrical requirements"),
            ]

            statement = (
                select(DocumentPage)
                .where(DocumentPage.document_version_id == document_version.id)
                .order_by(DocumentPage.page_number)
            )

            database_pages = list(session.scalars(statement).all())

            assert len(database_pages) == 2
            assert [(page.page_number, page.text) for page in database_pages] == [
                (1, "Updated cooling requirements"),
                (2, "Electrical requirements"),
            ]
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()
