from pathlib import Path
from typing import Literal, Self

from pydantic import Field, HttpUrl, SecretStr, model_validator
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
        env_ignore_empty=True,
        extra="ignore",
    )

    openai_api_key: SecretStr | None = None
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        min_length=1,
    )

    session_cookie_name: str = Field(
        default="decision_session",
        min_length=1,
    )
    session_cookie_secure: bool = True
    session_cookie_samesite: Literal[
        "lax",
        "strict",
        "none",
    ] = "lax"

    resend_api_key: SecretStr | None = Field(
        default=None,
        min_length=1,
    )
    email_sender_identity: str | None = Field(
        default=None,
        min_length=1,
    )
    email_verification_url: HttpUrl | None = None
    email_delivery_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
    )

    @model_validator(
        mode="after",
    )
    def validate_resend_email_delivery_configuration(
        self,
    ) -> Self:
        configuration_values = (
            self.resend_api_key,
            self.email_sender_identity,
            self.email_verification_url,
        )
        configured_values = sum(value is not None for value in configuration_values)

        if configured_values not in {
            0,
            len(configuration_values),
        }:
            raise ValueError(
                "Resend email delivery configuration must be complete",
            )

        return self


settings = Settings()
