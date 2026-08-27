from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.embeddings.base import (
    EmbeddingProvider,
    EmbeddingVector,
)
from app.models.document_chunk import DocumentChunk
from app.services import (
    document_embedding as document_embedding_service,
)


class FakeEmbeddingProvider:
    def __init__(
        self,
        embeddings_by_text: dict[str, EmbeddingVector],
    ) -> None:
        self.embeddings_by_text = embeddings_by_text
        self.calls: list[tuple[str, ...]] = []

    def embed_texts(
        self,
        texts: tuple[str, ...],
    ) -> tuple[EmbeddingVector, ...]:
        self.calls.append(texts)

        return tuple(self.embeddings_by_text[text] for text in texts)


def test_embedding_provider_supports_batch_generation() -> None:
    provider = FakeEmbeddingProvider(
        {
            "Cooling requirements": (1.0, 0.0, 0.0),
            "Electrical requirements": (0.0, 1.0, 0.0),
        }
    )

    assert isinstance(provider, EmbeddingProvider)

    embeddings = provider.embed_texts(
        (
            "Cooling requirements",
            "Electrical requirements",
        )
    )

    assert provider.calls == [
        (
            "Cooling requirements",
            "Electrical requirements",
        )
    ]
    assert embeddings == (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )


def test_embeds_document_chunks_in_one_batch() -> None:
    cooling_text = "Cooling requirements"
    electrical_text = "Electrical requirements"

    cooling_embedding = (1.0,) + (0.0,) * 1535
    electrical_embedding = (0.0, 1.0) + (0.0,) * 1534

    provider = FakeEmbeddingProvider(
        {
            cooling_text: cooling_embedding,
            electrical_text: electrical_embedding,
        }
    )
    session = Mock(spec=Session)
    document_page_id = uuid4()

    document_chunks = [
        DocumentChunk(
            document_page_id=document_page_id,
            chunk_index=0,
            text=cooling_text,
            start_offset=0,
            end_offset=len(cooling_text),
        ),
        DocumentChunk(
            document_page_id=document_page_id,
            chunk_index=1,
            text=electrical_text,
            start_offset=10,
            end_offset=10 + len(electrical_text),
        ),
    ]

    embedded_chunks = document_embedding_service.embed_document_chunks(
        session,
        embedding_provider=provider,
        document_chunks=document_chunks,
    )

    assert provider.calls == [
        (
            cooling_text,
            electrical_text,
        )
    ]
    assert embedded_chunks == document_chunks

    assert document_chunks[0].embedding == list(cooling_embedding)
    assert document_chunks[1].embedding == list(electrical_embedding)

    session.flush.assert_called_once_with()


def test_skips_embedding_provider_when_there_are_no_chunks() -> None:
    provider = FakeEmbeddingProvider({})
    session = Mock(spec=Session)

    embedded_chunks = document_embedding_service.embed_document_chunks(
        session,
        embedding_provider=provider,
        document_chunks=[],
    )

    assert embedded_chunks == []
    assert provider.calls == []
    session.flush.assert_not_called()


def test_rejects_embedding_response_with_wrong_count() -> None:
    class IncompleteEmbeddingProvider:
        def embed_texts(
            self,
            texts: tuple[str, ...],
        ) -> tuple[EmbeddingVector, ...]:
            return ((1.0,) + (0.0,) * 1535,)

    session = Mock(spec=Session)
    document_page_id = uuid4()
    document_chunks = [
        DocumentChunk(
            document_page_id=document_page_id,
            chunk_index=0,
            text="Cooling requirements",
            start_offset=0,
            end_offset=20,
        ),
        DocumentChunk(
            document_page_id=document_page_id,
            chunk_index=1,
            text="Electrical requirements",
            start_offset=10,
            end_offset=33,
        ),
    ]

    with pytest.raises(
        ValueError,
        match=("Embedding provider returned 1 embeddings for 2 document chunks"),
    ):
        document_embedding_service.embed_document_chunks(
            session,
            embedding_provider=IncompleteEmbeddingProvider(),
            document_chunks=document_chunks,
        )

    assert document_chunks[0].embedding is None
    assert document_chunks[1].embedding is None
    session.flush.assert_not_called()


def test_rejects_embedding_with_wrong_dimensions() -> None:
    class WrongDimensionEmbeddingProvider:
        def embed_texts(
            self,
            texts: tuple[str, ...],
        ) -> tuple[EmbeddingVector, ...]:
            return ((1.0, 0.0, 0.0),)

    session = Mock(spec=Session)
    chunk_text = "Cooling requirements"
    document_chunk = DocumentChunk(
        document_page_id=uuid4(),
        chunk_index=0,
        text=chunk_text,
        start_offset=0,
        end_offset=len(chunk_text),
    )

    with pytest.raises(
        ValueError,
        match=("Embedding 0 has 3 dimensions; expected 1536"),
    ):
        document_embedding_service.embed_document_chunks(
            session,
            embedding_provider=(WrongDimensionEmbeddingProvider()),
            document_chunks=[document_chunk],
        )

    assert document_chunk.embedding is None
    session.flush.assert_not_called()
