from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.database import engine
from app.embeddings.base import (
    EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    InvalidEmbeddingResponseError,
)
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion
from app.repositories import document_chunk as document_chunk_repository
from app.services import document_search as document_search_service


def test_repository_ranks_document_chunks_by_cosine_distance() -> None:
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
                status="ready",
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
                page_number=4,
                text="Cooling and electrical requirements",
            )
            session.add(document_page)
            session.flush()

            exact_text = "Exact cooling match"
            related_text = "Related cooling design"
            distant_text = "Electrical requirements"
            unembedded_text = "Chunk waiting for an embedding"

            exact_chunk = DocumentChunk(
                document_page_id=document_page.id,
                chunk_index=0,
                text=exact_text,
                start_offset=0,
                end_offset=len(exact_text),
                embedding=[1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1),
            )
            related_chunk = DocumentChunk(
                document_page_id=document_page.id,
                chunk_index=1,
                text=related_text,
                start_offset=0,
                end_offset=len(related_text),
                embedding=[0.8, 0.6] + [0.0] * (EMBEDDING_DIMENSIONS - 2),
            )
            distant_chunk = DocumentChunk(
                document_page_id=document_page.id,
                chunk_index=2,
                text=distant_text,
                start_offset=0,
                end_offset=len(distant_text),
                embedding=[0.0, 1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 2),
            )
            unembedded_chunk = DocumentChunk(
                document_page_id=document_page.id,
                chunk_index=3,
                text=unembedded_text,
                start_offset=0,
                end_offset=len(unembedded_text),
                embedding=None,
            )

            session.add_all(
                [
                    exact_chunk,
                    related_chunk,
                    distant_chunk,
                    unembedded_chunk,
                ]
            )
            session.flush()

            matches = document_chunk_repository.search_document_chunks(
                session,
                query_embedding=tuple(exact_chunk.embedding),
                limit=2,
            )

            assert [match.document_chunk_id for match in matches] == [
                exact_chunk.id,
                related_chunk.id,
            ]

            assert matches[0].document_page_id == document_page.id
            assert matches[0].document_version_id == document_version.id
            assert matches[0].document_id == document.id
            assert matches[0].document_title == "Cooling system"
            assert matches[0].file_name == "cooling-design.pdf"
            assert matches[0].version_number == 1
            assert matches[0].page_number == 4
            assert matches[0].chunk_index == 0
            assert matches[0].text == exact_text
            assert matches[0].start_offset == 0
            assert matches[0].end_offset == len(exact_text)
            assert matches[0].cosine_distance == 0.0

            # An unembedded chunk must not appear in semantic search.
            all_searchable_matches = document_chunk_repository.search_document_chunks(
                session,
                query_embedding=tuple(exact_chunk.embedding),
                limit=10,
            )

            assert [match.document_chunk_id for match in all_searchable_matches] == [
                exact_chunk.id,
                related_chunk.id,
                distant_chunk.id,
            ]

            # Chunks belonging to a document that is not ready must be hidden.
            document.status = "processing"
            session.flush()

            assert (
                document_chunk_repository.search_document_chunks(
                    session,
                    query_embedding=tuple(exact_chunk.embedding),
                    limit=10,
                )
                == []
            )
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_service_embeds_query_and_returns_document_matches(
    monkeypatch,
) -> None:
    session = Mock(spec=Session)
    embedding_provider = Mock(spec=EmbeddingProvider)

    query_embedding = tuple([1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1))
    embedding_provider.embed_texts.return_value = (query_embedding,)

    expected_matches = [Mock()]
    search_document_chunks = Mock(
        return_value=expected_matches,
    )
    monkeypatch.setattr(
        document_search_service.document_chunk_repository,
        "search_document_chunks",
        search_document_chunks,
    )

    matches = document_search_service.search_documents(
        session,
        embedding_provider=embedding_provider,
        query="cooling requirements",
        limit=5,
    )

    embedding_provider.embed_texts.assert_called_once_with(("cooling requirements",))
    search_document_chunks.assert_called_once_with(
        session,
        query_embedding=query_embedding,
        limit=5,
    )
    assert matches is expected_matches


@pytest.mark.parametrize(
    (
        "provider_response",
        "expected_error_message",
    ),
    [
        (
            (),
            "Embedding provider must return one embedding for one search query",
        ),
        (
            ((1.0, 0.0, 0.0),),
            "Search embedding has 3 dimensions; expected 1536",
        ),
    ],
)
def test_service_rejects_invalid_query_embedding_response(
    monkeypatch,
    provider_response,
    expected_error_message: str,
) -> None:
    session = Mock(spec=Session)
    embedding_provider = Mock(spec=EmbeddingProvider)
    embedding_provider.embed_texts.return_value = provider_response

    search_document_chunks = Mock()
    monkeypatch.setattr(
        document_search_service.document_chunk_repository,
        "search_document_chunks",
        search_document_chunks,
    )

    with pytest.raises(
        InvalidEmbeddingResponseError,
        match=expected_error_message,
    ):
        document_search_service.search_documents(
            session,
            embedding_provider=embedding_provider,
            query="cooling requirements",
            limit=5,
        )

    embedding_provider.embed_texts.assert_called_once_with(("cooling requirements",))
    search_document_chunks.assert_not_called()
