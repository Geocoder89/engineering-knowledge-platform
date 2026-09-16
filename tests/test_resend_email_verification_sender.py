import json
from types import SimpleNamespace

import httpx
import pytest

from app.api import dependencies as api_dependencies
from app.config import Settings
from app.notifications import dependencies as notification_dependencies
from app.notifications.base import EmailVerificationDeliveryError
from app.notifications.resend import ResendEmailVerificationSender


def test_sends_email_verification_through_resend() -> None:
    captured_requests: list[httpx.Request] = []

    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        captured_requests.append(request)

        return httpx.Response(
            status_code=200,
            json={
                "id": "email-message-id",
            },
        )

    transport = httpx.MockTransport(
        handle_request,
    )

    with httpx.Client(
        transport=transport,
    ) as http_client:
        sender = ResendEmailVerificationSender(
            api_key="resend-api-key",
            sender_identity=("Knowledge Decision Platform <accounts@example.com>"),
            verification_url="https://app.example.com/verify-email",
            http_client=http_client,
        )

        sender.send_email_verification(
            recipient_email="engineer@example.com",
            recipient_display_name="Engineering Reviewer",
            verification_token="verification-token",
        )

    assert len(captured_requests) == 1

    request = captured_requests[0]

    assert request.method == "POST"
    assert str(request.url) == "https://api.resend.com/emails"
    assert request.headers["authorization"] == "Bearer resend-api-key"

    payload = json.loads(
        request.content,
    )

    assert payload["from"] == ("Knowledge Decision Platform <accounts@example.com>")
    assert payload["to"] == [
        "engineer@example.com",
    ]
    assert payload["subject"] == "Verify your email"

    verification_url = "https://app.example.com/verify-email?token=verification-token"

    assert "Engineering Reviewer" in payload["html"]
    assert verification_url in payload["html"]
    assert verification_url in payload["text"]


@pytest.mark.parametrize(
    "scenario",
    [
        "provider_rejection",
        "network_failure",
    ],
)
def test_translates_resend_failure_into_delivery_error(
    scenario: str,
) -> None:
    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        if scenario == "network_failure":
            raise httpx.ConnectError(
                "Resend unavailable",
                request=request,
            )

        return httpx.Response(
            status_code=503,
            json={
                "message": "Sensitive provider response",
            },
        )

    transport = httpx.MockTransport(
        handle_request,
    )

    with httpx.Client(
        transport=transport,
    ) as http_client:
        sender = ResendEmailVerificationSender(
            api_key="secret-resend-api-key",
            sender_identity=("Knowledge Decision Platform <accounts@example.com>"),
            verification_url="https://app.example.com/verify-email",
            http_client=http_client,
        )

        with pytest.raises(
            EmailVerificationDeliveryError,
            match="^Email verification delivery failed$",
        ) as captured_error:
            sender.send_email_verification(
                recipient_email="engineer@example.com",
                recipient_display_name="Engineering Reviewer",
                verification_token="secret-verification-token",
            )

    error_message = str(
        captured_error.value,
    )

    assert "secret-resend-api-key" not in error_message
    assert "secret-verification-token" not in error_message
    assert "Sensitive provider response" not in error_message


def test_configured_factory_builds_resend_email_verification_sender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_settings = Settings(
        database_url="postgresql://localhost/test",
        resend_api_key="secret-resend-api-key",
        email_sender_identity=("Knowledge Decision Platform <accounts@example.com>"),
        email_verification_url=("https://app.example.com/verify-email"),
        email_delivery_timeout_seconds=10.0,
        _env_file=None,
    )

    monkeypatch.setattr(
        notification_dependencies,
        "settings",
        configured_settings,
    )

    with httpx.Client() as http_client:
        sender = notification_dependencies.get_email_verification_sender(
            http_client=http_client,
        )

        assert isinstance(
            sender,
            ResendEmailVerificationSender,
        )


def test_api_dependency_closes_email_delivery_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_settings = Settings(
        database_url="postgresql://localhost/test",
        resend_api_key="secret-resend-api-key",
        email_sender_identity=("Knowledge Decision Platform <accounts@example.com>"),
        email_verification_url=("https://app.example.com/verify-email"),
        email_delivery_timeout_seconds=7.5,
        _env_file=None,
    )

    monkeypatch.setattr(
        api_dependencies,
        "settings",
        configured_settings,
    )
    monkeypatch.setattr(
        notification_dependencies,
        "settings",
        configured_settings,
    )

    created_clients = []

    class TrackingHttpClient:
        def __init__(
            self,
            *,
            timeout: float,
        ) -> None:
            self.timeout = timeout
            self.is_closed = False
            created_clients.append(self)

        def __enter__(self) -> "TrackingHttpClient":
            return self

        def __exit__(
            self,
            exception_type: object | None,
            exception: object | None,
            traceback: object | None,
        ) -> None:
            self.is_closed = True

    monkeypatch.setattr(
        api_dependencies,
        "httpx",
        SimpleNamespace(
            Client=TrackingHttpClient,
        ),
        raising=False,
    )

    dependency = api_dependencies.provide_email_verification_sender()
    sender = next(
        dependency,
    )

    assert isinstance(
        sender,
        ResendEmailVerificationSender,
    )
    assert len(created_clients) == 1
    assert created_clients[0].timeout == 7.5
    assert created_clients[0].is_closed is False

    dependency.close()

    assert created_clients[0].is_closed is True


def test_encodes_verification_token_and_escapes_html_content() -> None:
    captured_requests: list[httpx.Request] = []

    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        captured_requests.append(request)

        return httpx.Response(
            status_code=200,
            json={
                "id": "email-message-id",
            },
        )

    transport = httpx.MockTransport(
        handle_request,
    )

    with httpx.Client(
        transport=transport,
    ) as http_client:
        sender = ResendEmailVerificationSender(
            api_key="resend-api-key",
            sender_identity="Knowledge Decision Platform <accounts@example.com>",
            verification_url="https://app.example.com/verify-email",
            http_client=http_client,
        )

        sender.send_email_verification(
            recipient_email="engineer@example.com",
            recipient_display_name='<script>alert("reviewer")</script>',
            verification_token="token+/=&?",
        )

    payload = json.loads(
        captured_requests[0].content,
    )

    expected_url = "https://app.example.com/verify-email?token=token%2B%2F%3D%26%3F"

    assert "<script>" not in payload["html"]
    assert "&lt;script&gt;alert(&quot;reviewer&quot;)&lt;/script&gt;" in payload["html"]
    assert expected_url in payload["html"]
    assert expected_url in payload["text"]
    assert "token+/=&?" not in payload["html"]
