import pytest
from pydantic import ValidationError

from app.config import Settings


def test_accepts_complete_resend_email_delivery_configuration() -> None:
    settings = Settings(
        database_url="postgresql://localhost/test",
        resend_api_key="secret-resend-api-key",
        email_sender_identity=("Knowledge Decision Platform <accounts@example.com>"),
        email_verification_url=("https://app.example.com/verify-email"),
        email_delivery_timeout_seconds=10.0,
        _env_file=None,
    )

    assert settings.resend_api_key is not None
    assert settings.resend_api_key.get_secret_value() == "secret-resend-api-key"
    assert settings.email_sender_identity == (
        "Knowledge Decision Platform <accounts@example.com>"
    )
    assert str(settings.email_verification_url) == (
        "https://app.example.com/verify-email"
    )
    assert settings.email_delivery_timeout_seconds == 10.0
    assert "secret-resend-api-key" not in repr(settings)


@pytest.mark.parametrize(
    "configuration",
    [
        {
            "resend_api_key": "secret-resend-api-key",
        },
        {
            "email_sender_identity": (
                "Knowledge Decision Platform <accounts@example.com>"
            ),
        },
        {
            "email_verification_url": ("https://app.example.com/verify-email"),
        },
    ],
)
def test_rejects_partial_resend_email_delivery_configuration(
    configuration: dict[str, str],
) -> None:
    with pytest.raises(
        ValidationError,
        match="Resend email delivery configuration must be complete",
    ):
        Settings(
            database_url="postgresql://localhost/test",
            _env_file=None,
            **configuration,
        )


def test_treats_empty_resend_configuration_as_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "RESEND_API_KEY",
        "",
    )
    monkeypatch.setenv(
        "EMAIL_SENDER_IDENTITY",
        "",
    )
    monkeypatch.setenv(
        "EMAIL_VERIFICATION_URL",
        "",
    )

    settings = Settings(
        database_url="postgresql://localhost/test",
        _env_file=None,
    )

    assert settings.resend_api_key is None
    assert settings.email_sender_identity is None
    assert settings.email_verification_url is None
