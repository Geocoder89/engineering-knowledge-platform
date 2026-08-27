from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from openai import OpenAIError

from app.embeddings.base import EmbeddingProviderError
from app.embeddings.openai import OpenAIEmbeddingProvider


def test_openai_provider_generates_embeddings_in_input_order() -> None:
    create_embedding = Mock(
        return_value=SimpleNamespace(
            data=[
                SimpleNamespace(
                    index=1,
                    embedding=[0.0, 1.0, 0.0],
                ),
                SimpleNamespace(
                    index=0,
                    embedding=[1.0, 0.0, 0.0],
                ),
            ]
        )
    )
    client = SimpleNamespace(
        embeddings=SimpleNamespace(
            create=create_embedding,
        )
    )
    provider = OpenAIEmbeddingProvider(
        client=client,
        model="text-embedding-3-small",
        dimensions=3,
    )

    embeddings = provider.embed_texts(
        (
            "Cooling requirements",
            "Electrical requirements",
        )
    )

    create_embedding.assert_called_once_with(
        model="text-embedding-3-small",
        input=[
            "Cooling requirements",
            "Electrical requirements",
        ],
        dimensions=3,
    )
    assert embeddings == (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )


def test_openai_provider_translates_sdk_errors() -> None:
    create_embedding = Mock(
        side_effect=OpenAIError("Temporary OpenAI failure"),
    )
    client = SimpleNamespace(
        embeddings=SimpleNamespace(
            create=create_embedding,
        )
    )
    provider = OpenAIEmbeddingProvider(
        client=client,
        model="text-embedding-3-small",
        dimensions=3,
    )

    with pytest.raises(
        EmbeddingProviderError,
        match="OpenAI embedding request failed",
    ):
        provider.embed_texts(("Cooling requirements",))

    create_embedding.assert_called_once_with(
        model="text-embedding-3-small",
        input=["Cooling requirements"],
        dimensions=3,
    )
