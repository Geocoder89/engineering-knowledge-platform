from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.domain.user import (
    InvalidUserEmail,
    UserStatus,
)
from app.models.user import User
from app.models.user_session import UserSession
from app.repositories import (
    user as user_repository,
)
from app.repositories import (
    user_password_credential as user_password_credential_repository,
)
from app.repositories import (
    user_session as user_session_repository,
)
from app.security.password import (
    hash_password,
    verify_password,
)
from app.security.session import (
    generate_session_token,
    hash_session_token,
)

SESSION_DURATION = timedelta(
    hours=12,
)

DUMMY_PASSWORD_HASH = hash_password(
    password="authentication timing placeholder",
)


class InvalidSessionError(ValueError):
    def __init__(self) -> None:
        super().__init__("Authentication required")


class InvalidCredentialsError(ValueError):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


@dataclass(frozen=True)
class AuthenticationResult:
    user: User
    user_session: UserSession
    session_token: str


@dataclass(frozen=True)
class AuthenticatedUser:
    user: User
    user_session: UserSession


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc,
    )


def authenticate_user(
    session: Session,
    *,
    email: str,
    password: str,
) -> AuthenticationResult:
    try:
        user = user_repository.get_user_by_email(
            session,
            email=email,
        )
    except InvalidUserEmail:
        user = None

    credential = None

    if user is not None:
        credential = user_password_credential_repository.get_user_password_credential(
            session,
            user_id=user.id,
        )

    password_hash = (
        credential.password_hash if credential is not None else DUMMY_PASSWORD_HASH
    )
    password_is_valid = verify_password(
        password=password,
        password_hash=password_hash,
    )

    if (
        user is None
        or credential is None
        or user.status != UserStatus.ACTIVE.value
        or not password_is_valid
    ):
        raise InvalidCredentialsError()

    authenticated_at = utc_now()
    session_token = generate_session_token()
    token_hash = hash_session_token(
        session_token,
    )
    user_session = user_session_repository.create_user_session(
        session,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=authenticated_at + SESSION_DURATION,
    )

    return AuthenticationResult(
        user=user,
        user_session=user_session,
        session_token=session_token,
    )


def resolve_authenticated_user(
    session: Session,
    *,
    session_token: str,
) -> AuthenticatedUser:
    token_hash = hash_session_token(
        session_token,
    )
    user_session = user_session_repository.get_active_user_session_by_token_hash(
        session,
        token_hash=token_hash,
        current_time=utc_now(),
    )

    if user_session is None:
        raise InvalidSessionError()

    user = user_repository.get_user_by_id(
        session,
        user_session.user_id,
    )

    if user is None or user.status != UserStatus.ACTIVE.value:
        raise InvalidSessionError()

    return AuthenticatedUser(
        user=user,
        user_session=user_session,
    )


def revoke_authenticated_session(
    session: Session,
    *,
    session_token: str,
) -> UserSession | None:
    revoked_at = utc_now()
    token_hash = hash_session_token(
        session_token,
    )
    user_session = user_session_repository.get_active_user_session_by_token_hash(
        session,
        token_hash=token_hash,
        current_time=revoked_at,
    )

    if user_session is None:
        return None

    return user_session_repository.revoke_user_session(
        session,
        user_session=user_session,
        revoked_at=revoked_at,
    )
