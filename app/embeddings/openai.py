from openai import OpenAI, OpenAIError

from app.embeddings.base import EmbeddingProviderError, EmbeddingVector


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        client: OpenAI,
        model: str,
        dimensions: int,
    ) -> None:
        self.client = client
        self.model = model
        self.dimensions = dimensions

    def embed_texts(
        self,
        texts: tuple[str, ...],
    ) -> tuple[EmbeddingVector, ...]:
        if not texts:
            return ()
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=list(texts),
                dimensions=self.dimensions,
            )

        except OpenAIError as error:
            raise EmbeddingProviderError("OpenAI embedding request failed") from error

        ordered_embeddings = sorted(
            response.data,
            key=lambda item: item.index,
        )

        return tuple(
            tuple(float(value) for value in item.embedding)
            for item in ordered_embeddings
        )
