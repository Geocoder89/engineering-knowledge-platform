from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chunking.text import TextChunk
from app.database import engine
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion
from app.repositories import document_chunk as document_chunk_repository


def test_database_persists_document_chunk() -> None:
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

            document_page = DocumentPage(
                document_version_id=document_version.id,
                page_number=1,
                text="Cooling system requirements",
            )
            session.add(document_page)
            session.flush()

            document_chunk = DocumentChunk(
                document_page_id=document_page.id,
                chunk_index=0,
                text="Cooling system requirements",
                start_offset=0,
                end_offset=27,
            )
            session.add(document_chunk)
            session.flush()

            persisted_chunk = session.get(
                DocumentChunk,
                document_chunk.id,
            )

            assert persisted_chunk is not None
            assert persisted_chunk.document_page_id == document_page.id
            assert persisted_chunk.chunk_index == 0
            assert persisted_chunk.text == "Cooling system requirements"
            assert persisted_chunk.start_offset == 0
            assert persisted_chunk.end_offset == 27
            assert persisted_chunk.created_at is not None
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_repository_replaces_document_chunks() -> None:
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
                checksum_sha256="b" * 64,
                storage_key=f"{document.id}/version-1",
            )
            session.add(document_version)
            session.flush()

            document_page = DocumentPage(
                document_version_id=document_version.id,
                page_number=1,
                text="Cooling system requirements",
            )
            session.add(document_page)
            session.flush()

            document_chunk_repository.replace_document_chunks(
                session,
                document_page_id=document_page.id,
                chunks=(
                    TextChunk(
                        chunk_index=0,
                        text="Cooling system",
                        start_offset=0,
                        end_offset=14,
                    ),
                    TextChunk(
                        chunk_index=1,
                        text="system requirements",
                        start_offset=8,
                        end_offset=27,
                    ),
                ),
            )

            document_chunk_repository.replace_document_chunks(
                session,
                document_page_id=document_page.id,
                chunks=(
                    TextChunk(
                        chunk_index=0,
                        text="Updated cooling requirements",
                        start_offset=0,
                        end_offset=28,
                    ),
                ),
            )

            statement = (
                select(DocumentChunk)
                .where(DocumentChunk.document_page_id == document_page.id)
                .order_by(DocumentChunk.chunk_index)
            )
            persisted_chunks = list(session.scalars(statement).all())

            assert [
                (
                    chunk.chunk_index,
                    chunk.text,
                    chunk.start_offset,
                    chunk.end_offset,
                )
                for chunk in persisted_chunks
            ] == [
                (
                    0,
                    "Updated cooling requirements",
                    0,
                    28,
                )
            ]
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()
