from sqlalchemy.orm import Session

from app.embeddings.base import (
    EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    InvalidEmbeddingResponseError,
)
from app.models.document_chunk import DocumentChunk


def embed_document_chunks(
    session: Session,
    *,
    embedding_provider: EmbeddingProvider,
    document_chunks: list[DocumentChunk],
) -> list[DocumentChunk]:
    if not document_chunks:
        return []
    texts = tuple(document_chunk.text for document_chunk in document_chunks)
    embeddings = embedding_provider.embed_texts(texts)

    if len(embeddings) != len(document_chunks):
        raise InvalidEmbeddingResponseError(
            f"Embedding provider returned "
            f"{len(embeddings)} embeddings for "
            f"{len(document_chunks)} document chunks"
        )

    for embedding_index, embedding in enumerate(embeddings):
        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise InvalidEmbeddingResponseError(
                f"Embedding {embedding_index} has "
                f"{len(embedding)} dimensions; expected "
                f"{EMBEDDING_DIMENSIONS}"
            )

    for document_chunk, embedding in zip(
        document_chunks,
        embeddings,
        strict=True,
    ):
        document_chunk.embedding = list(embedding)

    session.flush()

    return document_chunks
