from unittest.mock import Mock

import pytest

from app.config import Settings
from app.embeddings import dependencies as embedding_dependencies
from app.embeddings.base import EMBEDDING_DIMENSIONS
from app.embeddings.openai import OpenAIEmbeddingProvider


def test_builds_openai_embedding_provider_from_settings(
    monkeypatch,
) -> None:
    openai_client = Mock()
    create_openai_client = Mock(
        return_value=openai_client,
    )
    monkeypatch.setattr(
        embedding_dependencies,
        "OpenAI",
        create_openai_client,
    )
    configuration = Settings(
        database_url="postgresql://user:password@localhost/test",
        openai_api_key="test-api-key",
        openai_embedding_model="text-embedding-3-small",
    )

    provider = embedding_dependencies.get_embedding_provider(
        configuration,
    )

    create_openai_client.assert_called_once_with(
        api_key="test-api-key",
    )
    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.client is openai_client
    assert provider.model == "text-embedding-3-small"
    assert provider.dimensions == EMBEDDING_DIMENSIONS


@pytest.mark.parametrize(
    "api_key",
    [
        None,
        "",
        "   ",
    ],
)
def test_rejects_missing_openai_api_key(
    monkeypatch,
    api_key: str | None,
) -> None:
    create_openai_client = Mock()
    monkeypatch.setattr(
        embedding_dependencies,
        "OpenAI",
        create_openai_client,
    )
    configuration = Settings(
        database_url="postgresql://user:password@localhost/test",
        openai_api_key=api_key,
    )

    with pytest.raises(
        RuntimeError,
        match="OPENAI_API_KEY is required to run document embeddings",
    ):
        embedding_dependencies.get_embedding_provider(
            configuration,
        )

    create_openai_client.assert_not_called()
