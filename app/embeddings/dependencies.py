from openai import OpenAI

from app.config import Settings, settings
from app.embeddings.base import (
    EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
)
from app.embeddings.openai import OpenAIEmbeddingProvider


def get_embedding_provider(
    configuration: Settings = settings,
) -> EmbeddingProvider:
    api_key = (
        configuration.openai_api_key.get_secret_value().strip()
        if configuration.openai_api_key is not None
        else ""
    )
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to run document embeddings")

    client = OpenAI(
        api_key=api_key,
    )

    return OpenAIEmbeddingProvider(
        client=client,
        model=configuration.openai_embedding_model,
        dimensions=EMBEDDING_DIMENSIONS,
    )
