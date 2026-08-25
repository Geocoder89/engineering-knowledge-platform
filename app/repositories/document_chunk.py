from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.chunking.text import TextChunk
from app.models.document_chunk import DocumentChunk


def replace_document_chunks(
    session: Session,
    *,
    document_page_id: UUID,
    chunks: tuple[TextChunk, ...],
) -> list[DocumentChunk]:
    delete_statement = delete(DocumentChunk).where(
        DocumentChunk.document_page_id == document_page_id
    )

    session.execute(delete_statement)
    session.flush()

    document_chunks = [
        DocumentChunk(
            document_page_id=document_page_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
        )
        for chunk in sorted(
            chunks,
            key=lambda chunk: chunk.chunk_index,
        )
    ]

    session.add_all(document_chunks)
    session.flush()

    return document_chunks
