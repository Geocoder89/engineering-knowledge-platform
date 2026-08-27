from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.api.dependencies import provide_embedding_provider
from app.domain.document_search import DocumentChunkSearchResult
from app.embeddings.base import (
    EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    EmbeddingProviderError,
    InvalidEmbeddingResponseError,
)
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion
from app.services import document_search as document_search_service


def test_searches_documents_and_returns_source_citations(
    client,
    monkeypatch,
) -> None:
    embedding_provider = Mock(spec=EmbeddingProvider)
    match = DocumentChunkSearchResult(
        document_chunk_id=uuid4(),
        document_page_id=uuid4(),
        document_version_id=uuid4(),
        document_id=uuid4(),
        document_title="Cooling system",
        file_name="cooling-design.pdf",
        version_number=2,
        page_number=4,
        chunk_index=1,
        text="Cooling pressure must remain below the approved limit.",
        start_offset=120,
        end_offset=175,
        cosine_distance=0.2,
    )
    search_documents = Mock(
        return_value=[match],
    )

    monkeypatch.setattr(
        document_search_service,
        "search_documents",
        search_documents,
    )
    app.dependency_overrides[provide_embedding_provider] = lambda: embedding_provider

    try:
        response = client.post(
            "/search",
            json={
                "query": "cooling pressure limits",
                "limit": 5,
            },
        )
    finally:
        app.dependency_overrides.pop(
            provide_embedding_provider,
            None,
        )

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == "cooling pressure limits"
    assert body["limit"] == 5
    assert len(body["items"]) == 1

    item = body["items"][0]

    assert item["document_chunk_id"] == str(match.document_chunk_id)
    assert item["chunk_index"] == 1
    assert item["text"] == match.text
    assert item["start_offset"] == 120
    assert item["end_offset"] == 175
    assert item["similarity_score"] == pytest.approx(0.8)
    assert item["citation"] == {
        "document_id": str(match.document_id),
        "document_version_id": str(match.document_version_id),
        "document_page_id": str(match.document_page_id),
        "document_title": "Cooling system",
        "file_name": "cooling-design.pdf",
        "version_number": 2,
        "page_number": 4,
    }

    assert search_documents.call_count == 1
    assert search_documents.call_args.kwargs == {
        "embedding_provider": embedding_provider,
        "query": "cooling pressure limits",
        "limit": 5,
    }


@pytest.mark.parametrize(
    (
        "embedding_error",
        "expected_status",
        "expected_detail",
    ),
    [
        (
            EmbeddingProviderError("OpenAI embedding request failed"),
            503,
            "Document search is temporarily unavailable",
        ),
        (
            InvalidEmbeddingResponseError(
                "Search embedding has 3 dimensions; expected 1536"
            ),
            502,
            "Embedding provider returned an invalid response",
        ),
    ],
)
def test_maps_embedding_failures_to_http_errors(
    client,
    monkeypatch,
    embedding_error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    embedding_provider = Mock(spec=EmbeddingProvider)
    search_documents = Mock(
        side_effect=embedding_error,
    )

    monkeypatch.setattr(
        document_search_service,
        "search_documents",
        search_documents,
    )
    app.dependency_overrides[provide_embedding_provider] = lambda: embedding_provider

    try:
        response = client.post(
            "/search",
            json={
                "query": "cooling pressure limits",
                "limit": 5,
            },
        )
    finally:
        app.dependency_overrides.pop(
            provide_embedding_provider,
            None,
        )

    assert response.status_code == expected_status
    assert response.json() == {
        "detail": expected_detail,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {
            "query": "  ",
            "limit": 5,
        },
        {
            "query": "cooling requirements",
            "limit": 0,
        },
        {
            "query": "cooling requirements",
            "limit": 51,
        },
    ],
)
def test_rejects_invalid_document_search_requests(
    client,
    monkeypatch,
    payload: dict[str, object],
) -> None:
    embedding_provider = Mock(spec=EmbeddingProvider)
    search_documents = Mock()

    monkeypatch.setattr(
        document_search_service,
        "search_documents",
        search_documents,
    )
    app.dependency_overrides[provide_embedding_provider] = lambda: embedding_provider

    try:
        response = client.post(
            "/search",
            json=payload,
        )
    finally:
        app.dependency_overrides.pop(
            provide_embedding_provider,
            None,
        )

    assert response.status_code == 422
    search_documents.assert_not_called()
    embedding_provider.embed_texts.assert_not_called()


def test_searches_persisted_document_chunks_through_api(
    client,
    db_session,
) -> None:
    query_embedding = tuple([1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1))
    embedding_provider = Mock(spec=EmbeddingProvider)
    embedding_provider.embed_texts.return_value = (query_embedding,)

    document = Document(
        title="Cooling system",
        file_name="cooling-design.pdf",
        status="ready",
    )
    db_session.add(document)
    db_session.flush()

    document_version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_name="cooling-design.pdf",
        content_type="application/pdf",
        size_bytes=100,
        checksum_sha256="b" * 64,
        storage_key=f"{document.id}/version-1",
    )
    db_session.add(document_version)
    db_session.flush()

    document_page = DocumentPage(
        document_version_id=document_version.id,
        page_number=3,
        text="Cooling pressure and electrical requirements",
    )
    db_session.add(document_page)
    db_session.flush()

    exact_text = "Cooling pressure requirements"
    related_text = "Related cooling design"

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
    db_session.add_all(
        [
            exact_chunk,
            related_chunk,
        ]
    )
    db_session.commit()

    app.dependency_overrides[provide_embedding_provider] = lambda: embedding_provider

    try:
        response = client.post(
            "/search",
            json={
                "query": "cooling pressure limits",
                "limit": 2,
            },
        )
    finally:
        app.dependency_overrides.pop(
            provide_embedding_provider,
            None,
        )

    assert response.status_code == 200

    items = response.json()["items"]

    assert [item["document_chunk_id"] for item in items] == [
        str(exact_chunk.id),
        str(related_chunk.id),
    ]
    assert items[0]["similarity_score"] == pytest.approx(1.0)
    assert items[1]["similarity_score"] == pytest.approx(0.8)
    assert items[0]["citation"]["document_id"] == str(document.id)
    assert items[0]["citation"]["version_number"] == 1
    assert items[0]["citation"]["page_number"] == 3

    embedding_provider.embed_texts.assert_called_once_with(("cooling pressure limits",))
