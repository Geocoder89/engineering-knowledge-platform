from sqlalchemy.orm import Session

from app.domain.document_search import DocumentChunkSearchResult
from app.embeddings.base import (
    EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    InvalidEmbeddingResponseError,
)
from app.repositories import document_chunk as document_chunk_repository


def search_documents(
    session: Session,
    *,
    embedding_provider: EmbeddingProvider,
    query: str,
    limit: int,
) -> list[DocumentChunkSearchResult]:
    embeddings = embedding_provider.embed_texts((query,))

    if len(embeddings) != 1:
        raise InvalidEmbeddingResponseError(
            "Embedding provider must return one embedding for one search query"
        )

    query_embedding = embeddings[0]

    if len(query_embedding) != EMBEDDING_DIMENSIONS:
        raise InvalidEmbeddingResponseError(
            f"Search embedding has {len(query_embedding)} "
            f"dimensions; expected {EMBEDDING_DIMENSIONS}"
        )

    return document_chunk_repository.search_document_chunks(
        session,
        query_embedding=query_embedding,
        limit=limit,
    )
