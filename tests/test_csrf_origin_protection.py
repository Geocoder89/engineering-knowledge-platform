import re

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.security.csrf import (
    csrf_tokens_match,
    generate_csrf_token,
    is_trusted_request_origin,
)


def test_accepts_exact_trusted_request_origin() -> None:
    assert is_trusted_request_origin(
        origin="https://app.example.com",
        trusted_origins={
            "https://app.example.com",
        },
    )


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "",
        "null",
        "https://evil.example.com",
        "https://app.example.com.evil.example",
        "https://app.example.com/path",
    ],
)
def test_rejects_missing_or_untrusted_request_origin(
    origin: str | None,
) -> None:
    assert not is_trusted_request_origin(
        origin=origin,
        trusted_origins={
            "https://app.example.com",
        },
    )


def test_accepts_trusted_origin_configuration() -> None:
    configured_origins = frozenset(
        {
            "http://localhost:3000",
            "https://app.example.com",
        },
    )

    configured_settings = Settings(
        database_url="postgresql://localhost/test",
        csrf_trusted_origins=configured_origins,
        _env_file=None,
    )

    assert configured_settings.csrf_trusted_origins == configured_origins


@pytest.mark.parametrize(
    "configured_origins",
    [
        frozenset(),
        frozenset({"ftp://app.example.com"}),
        frozenset({"https://app.example.com/path"}),
        frozenset({"https://user:password@app.example.com"}),
    ],
)
def test_rejects_invalid_trusted_origin_configuration(
    configured_origins: frozenset[str],
) -> None:
    with pytest.raises(
        ValidationError,
        match="CSRF trusted origins must contain valid HTTP origins",
    ):
        Settings(
            database_url="postgresql://localhost/test",
            csrf_trusted_origins=configured_origins,
            _env_file=None,
        )


def test_generates_unique_url_safe_csrf_tokens() -> None:
    tokens = {generate_csrf_token() for _ in range(10)}

    assert len(tokens) == 10

    for token in tokens:
        assert re.fullmatch(
            r"[A-Za-z0-9_-]{43}",
            token,
        )


@pytest.mark.parametrize(
    (
        "cookie_token",
        "header_token",
        "expected_match",
    ),
    [
        (
            "matching-csrf-token",
            "matching-csrf-token",
            True,
        ),
        (
            "cookie-csrf-token",
            "different-header-token",
            False,
        ),
        (
            None,
            "header-csrf-token",
            False,
        ),
        (
            "cookie-csrf-token",
            None,
            False,
        ),
        (
            "",
            "",
            False,
        ),
    ],
)
def test_compares_csrf_cookie_and_header_tokens(
    cookie_token: str | None,
    header_token: str | None,
    expected_match: bool,
) -> None:
    assert (
        csrf_tokens_match(
            cookie_token=cookie_token,
            header_token=header_token,
        )
        is expected_match
    )


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "https://evil.example.com",
    ],
)
def test_rejects_unsafe_request_from_missing_or_untrusted_origin(
    client: TestClient,
    origin: str | None,
) -> None:
    headers = {}

    if origin is None:
        client.headers.pop(
            "Origin",
            None,
        )
    else:
        headers["Origin"] = origin

    response = client.post(
        "/auth/login",
        headers=headers,
        json={
            "email": "unknown@example.com",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Request origin is not allowed",
    }


def test_allows_safe_request_without_origin(
    client: TestClient,
) -> None:
    client.headers.pop(
        "Origin",
        None,
    )

    response = client.get(
        "/health",
    )

    assert response.status_code == 200


def test_public_authentication_route_does_not_require_csrf_token_for_stale_session(
    client: TestClient,
) -> None:
    client.cookies.set(
        "decision_session",
        "stale-session-token",
        domain="testserver.local",
        path="/",
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid email or password",
    }


@pytest.mark.parametrize(
    "method",
    [
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ],
)
def test_requires_csrf_token_for_unsafe_method_with_session_cookie(
    client: TestClient,
    method: str,
) -> None:
    client.cookies.set(
        "decision_session",
        "stale-session-token",
        domain="testserver.local",
        path="/",
    )

    response = client.request(
        method,
        "/health",
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "CSRF token is invalid",
    }


def test_does_not_require_csrf_token_for_options_request(
    client: TestClient,
) -> None:
    client.cookies.set(
        "decision_session",
        "stale-session-token",
        domain="testserver.local",
        path="/",
    )

    response = client.options(
        "/health",
    )

    assert response.status_code != 403


def test_loads_trusted_origins_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CSRF_TRUSTED_ORIGINS",
        ('["http://localhost:3000","https://app.example.com"]'),
    )

    configured_settings = Settings(
        database_url="postgresql://localhost/test",
        _env_file=None,
    )

    assert configured_settings.csrf_trusted_origins == frozenset(
        {
            "http://localhost:3000",
            "https://app.example.com",
        },
    )
