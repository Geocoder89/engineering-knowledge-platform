from typing import Annotated

from fastapi import Depends

from app.embeddings.base import EmbeddingProvider
from app.embeddings.dependencies import get_embedding_provider


def provide_embedding_provider() -> EmbeddingProvider:
    return get_embedding_provider()


EmbeddingProviderDependency = Annotated[
    EmbeddingProvider,
    Depends(provide_embedding_provider),
]
