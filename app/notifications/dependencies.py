from app.notifications.base import (
    EmailVerificationDeliveryError,
    EmailVerificationSender,
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


def get_email_verification_sender() -> EmailVerificationSender:
    return UnconfiguredEmailVerificationSender()
