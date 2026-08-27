from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.chunking.text import TextChunk
from app.domain.document import DocumentStatus
from app.domain.document_search import DocumentChunkSearchResult
from app.embeddings.base import EmbeddingVector
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion


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


def search_document_chunks(
    session: Session,
    *,
    query_embedding: EmbeddingVector,
    limit: int,
) -> list[DocumentChunkSearchResult]:
    cosine_distance = DocumentChunk.embedding.cosine_distance(
        list(query_embedding)
    ).label("cosine_distance")

    statement = (
        select(
            DocumentChunk.id.label("document_chunk_id"),
            DocumentChunk.document_page_id,
            DocumentPage.document_version_id,
            DocumentVersion.document_id,
            Document.title.label("document_title"),
            DocumentVersion.file_name,
            DocumentVersion.version_number,
            DocumentPage.page_number,
            DocumentChunk.chunk_index,
            DocumentChunk.text,
            DocumentChunk.start_offset,
            DocumentChunk.end_offset,
            cosine_distance,
        )
        .join(
            DocumentPage,
            DocumentPage.id == DocumentChunk.document_page_id,
        )
        .join(
            DocumentVersion,
            DocumentVersion.id == DocumentPage.document_version_id,
        )
        .join(
            Document,
            Document.id == DocumentVersion.document_id,
        )
        .where(
            DocumentChunk.embedding.is_not(None),
            Document.status == DocumentStatus.READY,
        )
        .order_by(
            cosine_distance.asc(),
            DocumentChunk.id.asc(),
        )
        .limit(limit)
    )

    rows = session.execute(statement).all()

    return [
        DocumentChunkSearchResult(
            document_chunk_id=row.document_chunk_id,
            document_page_id=row.document_page_id,
            document_version_id=row.document_version_id,
            document_id=row.document_id,
            document_title=row.document_title,
            file_name=row.file_name,
            version_number=row.version_number,
            page_number=row.page_number,
            chunk_index=row.chunk_index,
            text=row.text,
            start_offset=row.start_offset,
            end_offset=row.end_offset,
            cosine_distance=float(row.cosine_distance),
        )
        for row in rows
    ]
