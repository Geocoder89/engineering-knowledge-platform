from typing import Protocol, runtime_checkable

EMBEDDING_DIMENSIONS = 1536

type EmbeddingVector = tuple[float, ...]


@runtime_checkable
class EmbeddingProvider(Protocol):
    def embed_texts(
        self,
        texts: tuple[str, ...],
    ) -> tuple[EmbeddingVector, ...]: ...


class EmbeddingProviderError(RuntimeError):
    """
    Raised when an embedding provider cannot generate embeddings.
    """


class InvalidEmbeddingResponseError(ValueError):
    """
    Raised when an embedding provider returns an invalid response.
    """
