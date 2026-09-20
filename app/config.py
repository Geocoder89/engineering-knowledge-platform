from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
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

    csrf_trusted_origins: frozenset[str] = frozenset(
        {
            "http://localhost:3000",
        },
    )

    csrf_cookie_name: str = Field(
        default="decision_csrf",
        min_length=1,
    )

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

    @field_validator(
        "csrf_trusted_origins",
    )
    @classmethod
    def validate_csrf_trusted_origins(
        cls,
        origins: frozenset[str],
    ) -> frozenset[str]:
        error_message = "CSRF trusted origins must contain valid HTTP origins"

        if not origins:
            raise ValueError(error_message)

        for origin in origins:
            try:
                parsed_origin = urlsplit(origin)
                hostname = parsed_origin.hostname
                parsed_origin.port
            except ValueError as error:
                raise ValueError(error_message) from error

            if (
                origin != origin.strip()
                or parsed_origin.scheme not in {"http", "https"}
                or hostname is None
                or parsed_origin.username is not None
                or parsed_origin.password is not None
                or parsed_origin.path
                or parsed_origin.query
                or parsed_origin.fragment
            ):
                raise ValueError(error_message)

        return origins

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
