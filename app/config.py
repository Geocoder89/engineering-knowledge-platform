from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    document_storage_path: Path = Path("var/document-storage")
    document_max_upload_size_bytes: int = Field(
        default=10 * 1024 * 1024,
        gt=0,
    )
    document_processing_poll_interval_seconds: float = Field(
        default=1.0,
        gt=0,
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    openai_api_key: SecretStr | None = None
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        min_length=1,
    )


settings = Settings()
