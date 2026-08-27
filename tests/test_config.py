import pytest
from pydantic import ValidationError

from app.config import Settings


def test_configures_document_worker_poll_interval() -> None:
    configuration = Settings(
        database_url="postgresql://user:password@localhost/test",
        document_processing_poll_interval_seconds=2.5,
    )

    assert configuration.document_processing_poll_interval_seconds == 2.5


def test_rejects_nonpositive_document_worker_poll_interval() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url=("postgresql://user:password@localhost/test"),
            document_processing_poll_interval_seconds=0,
        )


def test_configures_openai_embedding_provider() -> None:
    configuration = Settings(
        database_url="postgresql://user:password@localhost/test",
        openai_api_key="test-api-key",
        openai_embedding_model="text-embedding-3-small",
    )

    assert configuration.openai_api_key is not None
    assert configuration.openai_api_key.get_secret_value() == "test-api-key"
    assert configuration.openai_embedding_model == "text-embedding-3-small"
