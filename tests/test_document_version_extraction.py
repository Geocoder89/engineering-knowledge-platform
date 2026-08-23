from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.domain.document_version import DocumentContentIntegrityError
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.services import document_version as document_version_service
from app.storage.local import LocalDocumentStorage
from tests.test_pdf_extraction import build_pdf_with_pages


def test_extracts_and_persists_pages_from_stored_document_version(
    tmp_path: Path,
) -> None:
    connection = engine.connect()
    outer_transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            storage = LocalDocumentStorage(
                root_path=tmp_path / "document-storage",
            )
            document = Document(
                title="Cooling system",
                file_name="cooling-design.pdf",
                status="pending",
            )
            session.add(document)
            session.flush()

            file_content = build_pdf_with_pages(
                (
                    "Cooling system requirements",
                    None,
                    "Electrical system requirements",
                )
            )

            document_version = document_version_service.upload_document_version(
                session,
                storage,
                document_id=document.id,
                file_name="cooling-design.pdf",
                content_type="application/pdf",
                content=file_content,
            )

            persisted_pages = document_version_service.extract_document_version_pages(
                session,
                storage,
                document_version=document_version,
            )

            assert [
                (
                    page.page_number,
                    page.text,
                    page.requires_ocr,
                )
                for page in persisted_pages
            ] == [
                (1, "Cooling system requirements", False),
                (2, "", True),
                (3, "Electrical system requirements", False),
            ]

            statement = (
                select(DocumentPage)
                .where(DocumentPage.document_version_id == document_version.id)
                .order_by(DocumentPage.page_number)
            )

            database_pages = list(session.scalars(statement).all())

            assert [(page.page_number, page.text) for page in database_pages] == [
                (1, "Cooling system requirements"),
                (2, ""),
                (3, "Electrical system requirements"),
            ]
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


#  Corrupted stored content must not be extracted persisted
def test_rejects_corrupted_content_before_persisting_pages(
    tmp_path: Path,
) -> None:
    connection = engine.connect()
    outer_transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            storage = LocalDocumentStorage(
                root_path=tmp_path / "document-storage",
            )
            document = Document(
                title="Cooling system",
                file_name="cooling-design.pdf",
                status="pending",
            )
            session.add(document)
            session.flush()

            original_content = build_pdf_with_pages(("Original cooling requirements",))

            document_version = document_version_service.upload_document_version(
                session,
                storage,
                document_id=document.id,
                file_name="cooling-design.pdf",
                content_type="application/pdf",
                content=original_content,
            )

            storage.save(
                key=document_version.storage_key,
                content=build_pdf_with_pages(("Tampered cooling requirements",)),
            )

            with pytest.raises(
                DocumentContentIntegrityError,
                match="Document content failed integrity check",
            ):
                document_version_service.extract_document_version_pages(
                    session,
                    storage,
                    document_version=document_version,
                )

            statement = select(DocumentPage).where(
                DocumentPage.document_version_id == document_version.id
            )

            assert list(session.scalars(statement).all()) == []
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()
