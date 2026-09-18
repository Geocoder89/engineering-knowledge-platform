from fastapi.testclient import TestClient

from app.security.email_verification import (
    generate_email_verification_token,
)


def test_login_returns_429_after_email_rate_limit(
    client: TestClient,
) -> None:
    login_payload = {
        "email": "unknown@example.com",
        "password": "correct horse battery staple",
    }

    for _ in range(5):
        response = client.post(
            "/auth/login",
            json=login_payload,
        )

        assert response.status_code == 401

    limited_response = client.post(
        "/auth/login",
        json=login_payload,
    )

    assert limited_response.status_code == 429
    assert limited_response.json() == {
        "detail": "Too many requests",
    }

    retry_after = int(limited_response.headers["Retry-After"])

    assert 1 <= retry_after <= 900


def test_login_returns_429_after_ip_rate_limit_across_different_emails(
    client: TestClient,
) -> None:
    for attempt in range(20):
        response = client.post(
            "/auth/login",
            json={
                "email": f"unknown-{attempt}@example.com",
                "password": "correct horse battery staple",
            },
        )

        assert response.status_code == 401

    limited_response = client.post(
        "/auth/login",
        json={
            "email": "another-unknown@example.com",
            "password": "correct horse battery staple",
        },
    )

    assert limited_response.status_code == 429
    assert limited_response.json() == {
        "detail": "Too many requests",
    }

    retry_after = int(limited_response.headers["Retry-After"])

    assert 1 <= retry_after <= 900


def test_registration_returns_429_after_email_rate_limit(
    client: TestClient,
) -> None:
    registration_payload = {
        "email": "engineer@example.com",
        "display_name": "Engineering Reviewer",
        "password": "correct horse battery staple",
    }

    first_response = client.post(
        "/auth/register",
        json=registration_payload,
    )

    assert first_response.status_code == 201

    for _ in range(2):
        duplicate_response = client.post(
            "/auth/register",
            json=registration_payload,
        )

        assert duplicate_response.status_code == 409

    limited_response = client.post(
        "/auth/register",
        json=registration_payload,
    )

    assert limited_response.status_code == 429
    assert limited_response.json() == {
        "detail": "Too many requests",
    }

    retry_after = int(limited_response.headers["Retry-After"])

    assert 1 <= retry_after <= 3600


def test_resend_verification_returns_429_after_email_rate_limit(
    client: TestClient,
) -> None:
    resend_payload = {
        "email": "unknown@example.com",
    }

    for _ in range(3):
        response = client.post(
            "/auth/resend-verification",
            json=resend_payload,
        )

        assert response.status_code == 202

    limited_response = client.post(
        "/auth/resend-verification",
        json=resend_payload,
    )

    assert limited_response.status_code == 429
    assert limited_response.json() == {
        "detail": "Too many requests",
    }

    retry_after = int(limited_response.headers["Retry-After"])

    assert 1 <= retry_after <= 3600


def test_verify_email_returns_429_after_ip_rate_limit(
    client: TestClient,
) -> None:
    for _ in range(20):
        response = client.post(
            "/auth/verify-email",
            json={
                "verification_token": generate_email_verification_token(),
            },
        )

        assert response.status_code == 400

    limited_response = client.post(
        "/auth/verify-email",
        json={
            "verification_token": generate_email_verification_token(),
        },
    )

    assert limited_response.status_code == 429
    assert limited_response.json() == {
        "detail": "Too many requests",
    }

    retry_after = int(limited_response.headers["Retry-After"])

    assert 1 <= retry_after <= 900


def test_login_rate_limit_uses_normalized_email(
    client: TestClient,
) -> None:
    email_variants = [
        "Engineer@Example.COM",
        " engineer@example.com ",
        "ENGINEER@EXAMPLE.COM",
        "Engineer@example.com",
        "  engineer@Example.Com  ",
    ]

    for email in email_variants:
        response = client.post(
            "/auth/login",
            json={
                "email": email,
                "password": "correct horse battery staple",
            },
        )

        assert response.status_code == 401

    limited_response = client.post(
        "/auth/login",
        json={
            "email": "engineer@example.com",
            "password": "correct horse battery staple",
        },
    )

    assert limited_response.status_code == 429


def test_registration_returns_429_after_ip_rate_limit_across_different_emails(
    client: TestClient,
) -> None:
    for attempt in range(5):
        response = client.post(
            "/auth/register",
            json={
                "email": f"engineer-{attempt}@example.com",
                "display_name": f"Engineering Reviewer {attempt}",
                "password": "correct horse battery staple",
            },
        )

        assert response.status_code == 201

    limited_response = client.post(
        "/auth/register",
        json={
            "email": "another-engineer@example.com",
            "display_name": "Another Engineering Reviewer",
            "password": "correct horse battery staple",
        },
    )

    assert limited_response.status_code == 429


def test_resend_verification_returns_429_after_ip_rate_limit_across_emails(
    client: TestClient,
) -> None:
    for attempt in range(10):
        response = client.post(
            "/auth/resend-verification",
            json={
                "email": f"unknown-{attempt}@example.com",
            },
        )

        assert response.status_code == 202

    limited_response = client.post(
        "/auth/resend-verification",
        json={
            "email": "another-unknown@example.com",
        },
    )

    assert limited_response.status_code == 429
