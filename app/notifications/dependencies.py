import httpx

from app.config import settings
from app.notifications.base import (
    EmailVerificationDeliveryError,
    EmailVerificationSender,
)
from app.notifications.resend import (
    ResendEmailVerificationSender,
)


class UnconfiguredEmailVerificationSender:
    def send_email_verification(
        self,
        *,
        recipient_email: str,
        recipient_display_name: str,
        verification_token: str,
    ) -> None:
        raise EmailVerificationDeliveryError(
            "Email verification sender is not configured",
        )


def get_email_verification_sender(
    *,
    http_client: httpx.Client | None = None,
) -> EmailVerificationSender:
    if settings.resend_api_key is None:
        return UnconfiguredEmailVerificationSender()

    if http_client is None:
        raise RuntimeError(
            "HTTP client is required for configured email delivery",
        )

    sender_identity = settings.email_sender_identity
    verification_url = settings.email_verification_url

    if sender_identity is None or verification_url is None:
        raise RuntimeError(
            "Resend email delivery configuration is incomplete",
        )

    return ResendEmailVerificationSender(
        api_key=settings.resend_api_key.get_secret_value(),
        sender_identity=sender_identity,
        verification_url=str(
            verification_url,
        ),
        http_client=http_client,
    )
