from html import escape
from urllib.parse import urlencode

import httpx

from app.notifications.base import EmailVerificationDeliveryError


class ResendEmailVerificationSender:
    def __init__(
        self,
        *,
        api_key: str,
        sender_identity: str,
        verification_url: str,
        http_client: httpx.Client,
    ) -> None:
        self._api_key = api_key
        self._sender_identity = sender_identity
        self._verification_url = verification_url
        self._http_client = http_client

    def send_email_verification(
        self,
        *,
        recipient_email: str,
        recipient_display_name: str,
        verification_token: str,
    ) -> None:
        verification_url = (
            f"{self._verification_url}?{urlencode({'token': verification_token})}"
        )

        escaped_display_name = escape(
            recipient_display_name,
        )
        escaped_verification_url = escape(
            verification_url,
            quote=True,
        )

        try:
            response = self._http_client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                },
                json={
                    "from": self._sender_identity,
                    "to": [
                        recipient_email,
                    ],
                    "subject": "Verify your email",
                    "html": (
                        f"<p>Hello {escaped_display_name},</p>"
                        "<p>Please verify your email address by clicking "
                        f'<a href="{escaped_verification_url}">'
                        "Verify your email"
                        "</a>.</p>"
                    ),
                    "text": (
                        f"Hello {recipient_display_name},\n\n"
                        "Please verify your email address using this link:\n"
                        f"{verification_url}"
                    ),
                },
            )

            response.raise_for_status()
        except httpx.HTTPError as error:
            raise EmailVerificationDeliveryError(
                "Email verification delivery failed",
            ) from error
