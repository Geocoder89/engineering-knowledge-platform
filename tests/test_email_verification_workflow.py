from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_email_verification_token import (
    UserEmailVerificationToken,
)
from app.notifications.base import EmailVerificationDeliveryError
from app.notifications.dependencies import (
    get_email_verification_sender,
)
from app.repositories import user as user_repository
from app.repositories import user_session as user_session_repository
from app.security.email_verification import (
    generate_email_verification_token,
    hash_email_verification_token,
)
from app.security.session import generate_session_token, hash_session_token
from app.services import authentication as authentication_service
from app.services import email_verification as email_verification_service
from app.services import user_password as user_password_service
from app.services import user_registration as user_registration_service


def test_service_rejects_login_for_unverified_user(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(user)
    db_session.flush()

    assert user.email_verified_at is None

    password = "correct horse battery staple"
    user_password_service.set_user_password(
        db_session,
        user=user,
        password=password,
    )

    try:
        authentication_service.authenticate_user(
            db_session,
            email=user.email,
            password=password,
        )
    except authentication_service.InvalidCredentialsError as error:
        assert str(error) == "Invalid email or password"
    else:
        raise AssertionError(
            "Unverified user was allowed to authenticate",
        )


def test_service_rejects_existing_session_for_unverified_user(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(user)
    db_session.flush()

    assert user.email_verified_at is None

    session_token = generate_session_token()
    issued_at = datetime.now(
        timezone.utc,
    )
    user_session_repository.create_user_session(
        db_session,
        user_id=user.id,
        token_hash=hash_session_token(
            session_token,
        ),
        expires_at=issued_at + authentication_service.SESSION_DURATION,
    )

    with pytest.raises(
        authentication_service.InvalidSessionError,
        match="Authentication required",
    ):
        authentication_service.resolve_authenticated_user(
            db_session,
            session_token=session_token,
        )


def test_service_registers_unverified_user_and_issues_email_verification(
    db_session: Session,
) -> None:
    registration = user_registration_service.register_user(
        db_session,
        email="  Engineer@Example.COM  ",
        display_name="  Engineering Reviewer  ",
        password="correct horse battery staple",
    )

    assert registration.user.email == "engineer@example.com"
    assert registration.user.display_name == "Engineering Reviewer"
    assert registration.user.email_verified_at is None

    verification = registration.email_verification

    assert verification.user is registration.user
    assert verification.token_record.user_id == registration.user.id
    assert verification.token_record.consumed_at is None
    assert verification.token_record.token_hash == hash_email_verification_token(
        verification.verification_token,
    )
    assert verification.verification_token != verification.token_record.token_hash


def test_verifies_registered_user_email(
    client: TestClient,
    db_session: Session,
) -> None:
    registration = user_registration_service.register_user(
        db_session,
        email="engineer@example.com",
        display_name="Engineering Reviewer",
        password="correct horse battery staple",
    )

    user_id = registration.user.id
    token_id = registration.email_verification.token_record.id

    response = client.post(
        "/auth/verify-email",
        json={
            "verification_token": (registration.email_verification.verification_token),
        },
    )

    assert response.status_code == 204
    assert response.content == b""

    db_session.expire_all()

    persisted_user = db_session.get(
        User,
        user_id,
    )
    persisted_token = db_session.get(
        UserEmailVerificationToken,
        token_id,
    )

    assert persisted_user is not None
    assert persisted_user.email_verified_at is not None
    assert persisted_token is not None
    assert persisted_token.consumed_at is not None


def test_registered_user_can_verify_email_and_authenticate(
    client: TestClient,
    email_verification_sender,
) -> None:
    registration_response = client.post(
        "/auth/register",
        json={
            "email": "  Engineer@Example.COM  ",
            "display_name": "  Engineering Reviewer  ",
            "password": "correct horse battery staple",
        },
    )

    assert registration_response.status_code == 201

    registered_user = registration_response.json()

    assert len(email_verification_sender.sent_verifications) == 1

    verification_token = email_verification_sender.sent_verifications[
        0
    ].verification_token

    assert verification_token not in registration_response.text

    login_before_verification = client.post(
        "/auth/login",
        json={
            "email": registered_user["email"],
            "password": "correct horse battery staple",
        },
    )

    assert login_before_verification.status_code == 401
    assert client.cookies.get("decision_session") is None

    verification_response = client.post(
        "/auth/verify-email",
        json={
            "verification_token": verification_token,
        },
    )

    assert verification_response.status_code == 204
    assert verification_response.content == b""

    login_response = client.post(
        "/auth/login",
        json={
            "email": registered_user["email"],
            "password": "correct horse battery staple",
        },
    )

    assert login_response.status_code == 200
    assert client.cookies.get("decision_session") is not None

    current_user_response = client.get(
        "/users/me",
    )

    assert current_user_response.status_code == 200
    assert current_user_response.json() == registered_user


def test_registration_sends_email_verification_without_exposing_token(
    client: TestClient,
    email_verification_sender,
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "engineer@example.com",
            "display_name": "Engineering Reviewer",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 201
    assert len(email_verification_sender.sent_verifications) == 1

    sent_verification = email_verification_sender.sent_verifications[0]

    assert sent_verification.recipient_email == "engineer@example.com"
    assert sent_verification.recipient_display_name == "Engineering Reviewer"
    assert sent_verification.verification_token
    assert sent_verification.verification_token not in response.text


def test_registration_rolls_back_when_email_verification_delivery_fails(
    client: TestClient,
    db_session: Session,
    email_verification_sender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_send_email_verification(
        *,
        recipient_email: str,
        recipient_display_name: str,
        verification_token: str,
    ) -> None:
        raise EmailVerificationDeliveryError(
            "Email provider unavailable",
        )

    monkeypatch.setattr(
        email_verification_sender,
        "send_email_verification",
        fail_to_send_email_verification,
    )

    response = client.post(
        "/auth/register",
        json={
            "email": "engineer@example.com",
            "display_name": "Engineering Reviewer",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "User registration could not be completed",
    }

    persisted_user = user_repository.get_user_by_email(
        db_session,
        email="engineer@example.com",
    )

    assert persisted_user is None


@pytest.mark.parametrize(
    "scenario",
    [
        "unknown",
        "expired",
        "consumed",
    ],
)
def test_verify_email_rejects_invalid_token_consistently(
    client: TestClient,
    email_verification_sender,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    if scenario == "unknown":
        verification_token = generate_email_verification_token()
    else:
        registration_response = client.post(
            "/auth/register",
            json={
                "email": "engineer@example.com",
                "display_name": "Engineering Reviewer",
                "password": "correct horse battery staple",
            },
        )

        assert registration_response.status_code == 201

        verification_token = email_verification_sender.sent_verifications[
            0
        ].verification_token

        if scenario == "expired":
            expired_time = (
                datetime.now(
                    timezone.utc,
                )
                + email_verification_service.EMAIL_VERIFICATION_DURATION
                + timedelta(
                    seconds=1,
                )
            )
            monkeypatch.setattr(
                email_verification_service,
                "utc_now",
                lambda: expired_time,
            )

        if scenario == "consumed":
            first_response = client.post(
                "/auth/verify-email",
                json={
                    "verification_token": verification_token,
                },
            )

            assert first_response.status_code == 204

    response = client.post(
        "/auth/verify-email",
        json={
            "verification_token": verification_token,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid or expired email verification token",
    }


def test_service_reissues_email_verification_and_invalidates_previous_token(
    db_session: Session,
) -> None:
    registration = user_registration_service.register_user(
        db_session,
        email="engineer@example.com",
        display_name="Engineering Reviewer",
        password="correct horse battery staple",
    )

    previous_verification = registration.email_verification

    reissued_verification = email_verification_service.request_email_verification(
        db_session,
        email="  Engineer@Example.COM  ",
    )

    assert reissued_verification is not None
    assert reissued_verification.user is registration.user
    assert (
        reissued_verification.verification_token
        != previous_verification.verification_token
    )
    assert previous_verification.token_record.consumed_at is not None
    assert reissued_verification.token_record.consumed_at is None

    with pytest.raises(
        email_verification_service.InvalidEmailVerificationTokenError,
        match="Invalid or expired email verification token",
    ):
        email_verification_service.verify_email(
            db_session,
            verification_token=previous_verification.verification_token,
        )

    verified_user = email_verification_service.verify_email(
        db_session,
        verification_token=reissued_verification.verification_token,
    )

    assert verified_user.id == registration.user.id
    assert verified_user.email_verified_at is not None


def test_resends_email_verification_and_invalidates_previous_token(
    client: TestClient,
    email_verification_sender,
) -> None:
    registration_response = client.post(
        "/auth/register",
        json={
            "email": "engineer@example.com",
            "display_name": "Engineering Reviewer",
            "password": "correct horse battery staple",
        },
    )

    assert registration_response.status_code == 201
    assert len(email_verification_sender.sent_verifications) == 1

    previous_token = email_verification_sender.sent_verifications[0].verification_token

    email_verification_sender.sent_verifications.clear()

    resend_response = client.post(
        "/auth/resend-verification",
        json={
            "email": "  Engineer@Example.COM  ",
        },
    )

    assert resend_response.status_code == 202
    assert resend_response.content == b""
    assert len(email_verification_sender.sent_verifications) == 1

    replacement_token = email_verification_sender.sent_verifications[
        0
    ].verification_token

    assert replacement_token != previous_token

    previous_token_response = client.post(
        "/auth/verify-email",
        json={
            "verification_token": previous_token,
        },
    )

    assert previous_token_response.status_code == 400

    replacement_token_response = client.post(
        "/auth/verify-email",
        json={
            "verification_token": replacement_token,
        },
    )

    assert replacement_token_response.status_code == 204


@pytest.mark.parametrize(
    "scenario",
    [
        "unknown_user",
        "verified_user",
    ],
)
def test_resend_verification_does_not_reveal_account_state(
    client: TestClient,
    email_verification_sender,
    scenario: str,
) -> None:
    requested_email = "unknown@example.com"

    if scenario == "verified_user":
        registration_response = client.post(
            "/auth/register",
            json={
                "email": "engineer@example.com",
                "display_name": "Engineering Reviewer",
                "password": "correct horse battery staple",
            },
        )

        assert registration_response.status_code == 201

        verification_token = email_verification_sender.sent_verifications[
            0
        ].verification_token

        verification_response = client.post(
            "/auth/verify-email",
            json={
                "verification_token": verification_token,
            },
        )

        assert verification_response.status_code == 204

        requested_email = "engineer@example.com"
        email_verification_sender.sent_verifications.clear()

    response = client.post(
        "/auth/resend-verification",
        json={
            "email": requested_email,
        },
    )

    assert response.status_code == 202
    assert response.content == b""
    assert email_verification_sender.sent_verifications == []


def test_resend_delivery_failure_preserves_previous_token(
    client: TestClient,
    email_verification_sender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration_response = client.post(
        "/auth/register",
        json={
            "email": "engineer@example.com",
            "display_name": "Engineering Reviewer",
            "password": "correct horse battery staple",
        },
    )

    assert registration_response.status_code == 201

    previous_token = email_verification_sender.sent_verifications[0].verification_token

    def fail_to_send_email_verification(
        *,
        recipient_email: str,
        recipient_display_name: str,
        verification_token: str,
    ) -> None:
        raise EmailVerificationDeliveryError(
            "Email provider unavailable",
        )

    monkeypatch.setattr(
        email_verification_sender,
        "send_email_verification",
        fail_to_send_email_verification,
    )

    resend_response = client.post(
        "/auth/resend-verification",
        json={
            "email": "engineer@example.com",
        },
    )

    assert resend_response.status_code == 202
    assert resend_response.content == b""

    previous_token_response = client.post(
        "/auth/verify-email",
        json={
            "verification_token": previous_token,
        },
    )

    assert previous_token_response.status_code == 204


def test_unconfigured_email_sender_fails_during_delivery() -> None:
    email_verification_sender = get_email_verification_sender()

    with pytest.raises(
        EmailVerificationDeliveryError,
        match="Email verification sender is not configured",
    ):
        email_verification_sender.send_email_verification(
            recipient_email="engineer@example.com",
            recipient_display_name="Engineering Reviewer",
            verification_token=generate_email_verification_token(),
        )
