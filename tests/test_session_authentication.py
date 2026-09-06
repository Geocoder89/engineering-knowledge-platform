from datetime import datetime, timedelta, timezone
from string import ascii_letters, digits
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.user import UserStatus
from app.models.user import User
from app.models.user_session import UserSession
from app.repositories import user_session as user_session_repository
from app.security.session import (
    generate_session_token,
    hash_session_token,
)
from app.services import (
    authentication as authentication_service,
)
from app.services import (
    user_password as user_password_service,
)


def test_generates_unique_url_safe_session_tokens() -> None:
    tokens = {
        generate_session_token()
        for _ in range(
            10,
        )
    }
    url_safe_characters = set(
        ascii_letters + digits + "-_",
    )

    assert len(tokens) == 10

    for token in tokens:
        assert len(token) >= 43
        assert set(token) <= url_safe_characters


def test_hashes_session_tokens_deterministically() -> None:
    token = "test-session-token"

    token_hash = hash_session_token(
        token,
    )

    assert token_hash == hash_session_token(
        token,
    )
    assert token_hash != token
    assert len(token_hash) == 64
    assert token_hash != hash_session_token(
        "different-session-token",
    )

    int(
        token_hash,
        16,
    )


def test_database_persists_active_user_session(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    raw_token = generate_session_token()
    token_hash = hash_session_token(
        raw_token,
    )
    expires_at = datetime.now(
        timezone.utc,
    ) + timedelta(
        hours=12,
    )
    user_session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db_session.add(
        user_session,
    )
    db_session.flush()
    session_id = user_session.id
    db_session.expire_all()

    persisted_session = db_session.get(
        UserSession,
        session_id,
    )

    assert persisted_session is not None
    assert persisted_session.user_id == user.id
    assert persisted_session.token_hash == token_hash
    assert persisted_session.token_hash != raw_token
    assert persisted_session.expires_at == expires_at
    assert persisted_session.revoked_at is None
    assert persisted_session.created_at is not None


def test_repository_creates_and_retrieves_active_user_session(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    issued_at = datetime.now(
        timezone.utc,
    )
    expires_at = issued_at + timedelta(
        hours=12,
    )
    raw_token = generate_session_token()
    token_hash = hash_session_token(
        raw_token,
    )

    created_session = user_session_repository.create_user_session(
        db_session,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    retrieved_session = user_session_repository.get_active_user_session_by_token_hash(
        db_session,
        token_hash=token_hash,
        current_time=issued_at,
    )

    assert retrieved_session is created_session
    assert retrieved_session.user_id == user.id
    assert retrieved_session.token_hash != raw_token
    assert retrieved_session.expires_at == expires_at
    assert retrieved_session.revoked_at is None


def test_repository_returns_none_for_unknown_session_token(
    db_session: Session,
) -> None:
    retrieved_session = user_session_repository.get_active_user_session_by_token_hash(
        db_session,
        token_hash=hash_session_token(
            generate_session_token(),
        ),
        current_time=datetime.now(
            timezone.utc,
        ),
    )

    assert retrieved_session is None


def test_repository_does_not_return_expired_user_session(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(user)
    db_session.flush()

    issued_at = datetime.now(
        timezone.utc,
    )
    expires_at = issued_at + timedelta(
        hours=1,
    )
    token_hash = hash_session_token(
        generate_session_token(),
    )

    user_session_repository.create_user_session(
        db_session,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    retrieved_session = user_session_repository.get_active_user_session_by_token_hash(
        db_session,
        token_hash=token_hash,
        current_time=expires_at,
    )

    assert retrieved_session is None


def test_repository_revokes_user_session(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(user)
    db_session.flush()

    issued_at = datetime.now(
        timezone.utc,
    )
    token_hash = hash_session_token(
        generate_session_token(),
    )
    user_session = user_session_repository.create_user_session(
        db_session,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=issued_at
        + timedelta(
            hours=12,
        ),
    )
    revoked_at = user_session.created_at + timedelta(
        seconds=1,
    )

    revoked_session = user_session_repository.revoke_user_session(
        db_session,
        user_session=user_session,
        revoked_at=revoked_at,
    )

    retrieved_session = user_session_repository.get_active_user_session_by_token_hash(
        db_session,
        token_hash=token_hash,
        current_time=revoked_at,
    )

    assert revoked_session is user_session
    assert revoked_session.revoked_at == revoked_at
    assert retrieved_session is None


def test_service_authenticates_active_user_and_creates_session(
    db_session: Session,
    monkeypatch,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(user)
    db_session.flush()

    password = "correct horse battery staple"
    user_password_service.set_user_password(
        db_session,
        user=user,
        password=password,
    )

    authenticated_at = datetime.now(
        timezone.utc,
    )
    monkeypatch.setattr(
        authentication_service,
        "utc_now",
        lambda: authenticated_at,
    )

    result = authentication_service.authenticate_user(
        db_session,
        email="  Engineer@Example.COM  ",
        password=password,
    )

    assert result.user is user
    assert result.user_session.user_id == user.id
    assert result.user_session.expires_at == authenticated_at + timedelta(
        hours=12,
    )
    assert result.user_session.token_hash == hash_session_token(
        result.session_token,
    )
    assert result.user_session.token_hash != result.session_token
    assert result.user_session.revoked_at is None


@pytest.mark.parametrize(
    "scenario",
    [
        "unknown_user",
        "incorrect_password",
        "disabled_user",
        "missing_credential",
        "blank_email",
    ],
)
def test_service_rejects_invalid_credentials_without_creating_session(
    db_session: Session,
    scenario: str,
) -> None:
    email = "engineer@example.com"
    valid_password = "correct horse battery staple"
    submitted_email = email
    submitted_password = valid_password

    if scenario not in {
        "unknown_user",
        "blank_email",
    }:
        user = User(
            email=email,
            display_name="Engineering Reviewer",
        )
        db_session.add(user)
        db_session.flush()

        if scenario != "missing_credential":
            user_password_service.set_user_password(
                db_session,
                user=user,
                password=valid_password,
            )

        if scenario == "disabled_user":
            user.status = UserStatus.DISABLED.value
            db_session.flush()

    if scenario == "unknown_user":
        submitted_email = "unknown@example.com"

    if scenario == "incorrect_password":
        submitted_password = "incorrect password value"

    if scenario == "blank_email":
        submitted_email = "   "

    with pytest.raises(
        authentication_service.InvalidCredentialsError,
        match="Invalid email or password",
    ):
        authentication_service.authenticate_user(
            db_session,
            email=submitted_email,
            password=submitted_password,
        )

    session_count = db_session.scalar(
        select(
            func.count(),
        ).select_from(UserSession),
    )

    assert session_count == 0


def test_service_performs_password_verification_for_unknown_user(
    db_session: Session,
    monkeypatch,
) -> None:
    verify_password = Mock(
        return_value=False,
    )
    monkeypatch.setattr(
        authentication_service,
        "verify_password",
        verify_password,
    )

    with pytest.raises(
        authentication_service.InvalidCredentialsError,
        match="Invalid email or password",
    ):
        authentication_service.authenticate_user(
            db_session,
            email="unknown@example.com",
            password="incorrect password value",
        )

    verify_password.assert_called_once()


def test_service_resolves_authenticated_user_from_session_token(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(user)
    db_session.flush()

    password = "correct horse battery staple"
    user_password_service.set_user_password(
        db_session,
        user=user,
        password=password,
    )
    authentication = authentication_service.authenticate_user(
        db_session,
        email=user.email,
        password=password,
    )

    authenticated_user = authentication_service.resolve_authenticated_user(
        db_session,
        session_token=authentication.session_token,
    )

    assert authenticated_user.user is user
    assert authenticated_user.user_session is authentication.user_session


@pytest.mark.parametrize(
    "scenario",
    [
        "unknown_token",
        "expired_session",
        "revoked_session",
        "disabled_user",
    ],
)
def test_service_rejects_invalid_authenticated_session(
    db_session: Session,
    monkeypatch,
    scenario: str,
) -> None:
    session_token = generate_session_token()
    current_time = datetime.now(
        timezone.utc,
    )

    if scenario != "unknown_token":
        user = User(
            email="engineer@example.com",
            display_name="Engineering Reviewer",
        )
        db_session.add(user)
        db_session.flush()

        password = "correct horse battery staple"
        user_password_service.set_user_password(
            db_session,
            user=user,
            password=password,
        )
        authentication = authentication_service.authenticate_user(
            db_session,
            email=user.email,
            password=password,
        )
        session_token = authentication.session_token

        if scenario == "expired_session":
            current_time = authentication.user_session.expires_at

        if scenario == "revoked_session":
            current_time = authentication.user_session.created_at + timedelta(
                seconds=1,
            )
            user_session_repository.revoke_user_session(
                db_session,
                user_session=authentication.user_session,
                revoked_at=current_time,
            )

        if scenario == "disabled_user":
            user.status = UserStatus.DISABLED.value
            db_session.flush()

    monkeypatch.setattr(
        authentication_service,
        "utc_now",
        lambda: current_time,
    )

    with pytest.raises(
        authentication_service.InvalidSessionError,
        match="Authentication required",
    ):
        authentication_service.resolve_authenticated_user(
            db_session,
            session_token=session_token,
        )


def test_service_revokes_authenticated_session(
    db_session: Session,
    monkeypatch,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(user)
    db_session.flush()

    password = "correct horse battery staple"
    user_password_service.set_user_password(
        db_session,
        user=user,
        password=password,
    )
    authentication = authentication_service.authenticate_user(
        db_session,
        email=user.email,
        password=password,
    )

    revoked_at = authentication.user_session.created_at + timedelta(
        seconds=1,
    )
    monkeypatch.setattr(
        authentication_service,
        "utc_now",
        lambda: revoked_at,
    )

    revoked_session = authentication_service.revoke_authenticated_session(
        db_session,
        session_token=authentication.session_token,
    )

    assert revoked_session is authentication.user_session
    assert revoked_session.revoked_at == revoked_at

    with pytest.raises(
        authentication_service.InvalidSessionError,
        match="Authentication required",
    ):
        authentication_service.resolve_authenticated_user(
            db_session,
            session_token=authentication.session_token,
        )


def test_service_ignores_unknown_session_during_logout(
    db_session: Session,
) -> None:
    revoked_session = authentication_service.revoke_authenticated_session(
        db_session,
        session_token=generate_session_token(),
    )

    assert revoked_session is None


def test_logs_in_user_and_sets_secure_session_cookie(
    client,
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(user)
    db_session.flush()

    password = "correct horse battery staple"
    user_password_service.set_user_password(
        db_session,
        user=user,
        password=password,
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "  Engineer@Example.COM  ",
            "password": password,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "status": UserStatus.ACTIVE.value,
    }

    set_cookie = response.headers["set-cookie"]

    assert "decision_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie
    assert "Max-Age=43200" in set_cookie
    assert "session_token" not in response.json()

    session_token = client.cookies.get(
        "decision_session",
    )

    assert session_token is not None

    stored_session = user_session_repository.get_active_user_session_by_token_hash(
        db_session,
        token_hash=hash_session_token(session_token),
        current_time=datetime.now(timezone.utc),
    )

    assert stored_session is not None
    assert stored_session.user_id == user.id
    assert stored_session.token_hash != session_token


def test_gets_current_authenticated_user(
    client,
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(user)
    db_session.flush()

    password = "correct horse battery staple"
    user_password_service.set_user_password(
        db_session,
        user=user,
        password=password,
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": user.email,
            "password": password,
        },
    )

    assert login_response.status_code == 200
    assert (
        client.cookies.get(
            "decision_session",
        )
        is not None
    )

    response = client.get(
        "/users/me",
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "status": UserStatus.ACTIVE.value,
    }


def test_logs_out_user_revokes_session_and_clears_cookie(
    client,
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(user)
    db_session.flush()

    password = "correct horse battery staple"
    user_password_service.set_user_password(
        db_session,
        user=user,
        password=password,
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": user.email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    session_token = client.cookies.get(
        "decision_session",
    )

    assert session_token is not None

    stored_session = user_session_repository.get_active_user_session_by_token_hash(
        db_session,
        token_hash=hash_session_token(session_token),
        current_time=datetime.now(timezone.utc),
    )

    assert stored_session is not None

    stored_session_id = stored_session.id

    response = client.post(
        "/auth/logout",
    )

    assert response.status_code == 204
    assert (
        client.cookies.get(
            "decision_session",
        )
        is None
    )

    set_cookie = response.headers["set-cookie"]

    assert "decision_session=" in set_cookie
    assert "Max-Age=0" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie

    db_session.expire_all()

    revoked_session = db_session.get(
        UserSession,
        stored_session_id,
    )

    assert revoked_session is not None
    assert revoked_session.revoked_at is not None

    current_user_response = client.get(
        "/users/me",
    )

    assert current_user_response.status_code == 401
    assert current_user_response.json() == {
        "detail": "Authentication required",
    }


@pytest.mark.parametrize(
    "scenario",
    [
        "unknown_user",
        "incorrect_password",
        "disabled_user",
    ],
)
def test_rejects_invalid_login_without_creating_session_cookie(
    client,
    db_session: Session,
    scenario: str,
) -> None:
    email = "engineer@example.com"
    password = "correct horse battery staple"
    submitted_email = email
    submitted_password = password

    if scenario != "unknown_user":
        user = User(
            email=email,
            display_name="Engineering Reviewer",
        )
        db_session.add(user)
        db_session.flush()

        user_password_service.set_user_password(
            db_session,
            user=user,
            password=password,
        )

        if scenario == "disabled_user":
            user.status = UserStatus.DISABLED.value
            db_session.flush()

    if scenario == "unknown_user":
        submitted_email = "unknown@example.com"

    if scenario == "incorrect_password":
        submitted_password = "incorrect password value"

    response = client.post(
        "/auth/login",
        json={
            "email": submitted_email,
            "password": submitted_password,
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid email or password",
    }
    assert "set-cookie" not in response.headers
    assert (
        client.cookies.get(
            "decision_session",
        )
        is None
    )

    session_count = db_session.scalar(
        select(
            func.count(),
        ).select_from(UserSession),
    )

    assert session_count == 0


@pytest.mark.parametrize(
    "scenario",
    [
        "missing_cookie",
        "invalid_cookie",
    ],
)
def test_current_user_requires_valid_session_cookie(
    client,
    scenario: str,
) -> None:
    if scenario == "invalid_cookie":
        client.cookies.set(
            "decision_session",
            generate_session_token(),
        )

    response = client.get(
        "/users/me",
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required",
    }


def test_logout_without_session_is_idempotent(
    client,
) -> None:
    response = client.post(
        "/auth/logout",
    )

    assert response.status_code == 204
    assert (
        client.cookies.get(
            "decision_session",
        )
        is None
    )

    set_cookie = response.headers["set-cookie"]

    assert "decision_session=" in set_cookie
    assert "Max-Age=0" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie
