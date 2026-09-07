from typing import Protocol


class EmailVerificationSender(Protocol):
    def send_email_verification(
        self,
        *,
        recipient_email: str,
        recipient_display_name: str,
        verification_token: str,
    ) -> None: ...


class EmailVerificationDeliveryError(RuntimeError):
    pass
