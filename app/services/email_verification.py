from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.user import InvalidUserEmail
from app.models.user import User
from app.models.user_email_verification_token import (
    UserEmailVerificationToken,
)
from app.repositories import user as user_repository
from app.repositories import (
    user_email_verification_token as email_verification_token_repository,
)
from app.security.email_verification import (
    generate_email_verification_token,
    hash_email_verification_token,
)

EMAIL_VERIFICATION_DURATION = timedelta(
    hours=24,
)


class InvalidEmailVerificationTokenError(ValueError):
    def __init__(self) -> None:
        super().__init__(
            "Invalid or expired email verification token",
        )


@dataclass(frozen=True)
class EmailVerificationIssue:
    user: User
    token_record: UserEmailVerificationToken
    verification_token: str


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc,
    )


def issue_email_verification(
    session: Session,
    *,
    user: User,
) -> EmailVerificationIssue:
    issued_at = utc_now()
    verification_token = generate_email_verification_token()
    token_hash = hash_email_verification_token(
        verification_token,
    )
    token_record = email_verification_token_repository.create_email_verification_token(
        session,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=issued_at + EMAIL_VERIFICATION_DURATION,
    )

    return EmailVerificationIssue(
        user=user,
        token_record=token_record,
        verification_token=verification_token,
    )


def verify_email(
    session: Session,
    *,
    verification_token: str,
) -> User:
    verified_at = utc_now()
    token_hash = hash_email_verification_token(
        verification_token,
    )
    token_record = email_verification_token_repository.get_active_email_verification_token_by_token_hash(
        session,
        token_hash=token_hash,
        current_time=verified_at,
    )

    if token_record is None:
        raise InvalidEmailVerificationTokenError()

    verified_at = max(verified_at, token_record.created_at)

    user = user_repository.get_user_by_id(
        session,
        token_record.user_id,
    )

    if user is None:
        raise InvalidEmailVerificationTokenError()

    with session.begin_nested():
        user_repository.set_user_email_verified_at(
            session,
            user=user,
            verified_at=verified_at,
        )
        email_verification_token_repository.consume_email_verification_token(
            session,
            verification_token=token_record,
            consumed_at=verified_at,
        )

    return user


def consume_active_email_verification_tokens_for_user(
    session: Session,
    *,
    user_id: UUID,
    consumed_at: datetime,
) -> list[UserEmailVerificationToken]:
    statement = (
        select(
            UserEmailVerificationToken,
        )
        .where(
            UserEmailVerificationToken.user_id == user_id,
            UserEmailVerificationToken.consumed_at.is_(None),
            UserEmailVerificationToken.expires_at > consumed_at,
        )
        .with_for_update()
    )

    verification_tokens = list(
        session.scalars(
            statement,
        ),
    )

    for verification_token in verification_tokens:
        verification_token.consumed_at = consumed_at

    session.flush()

    return verification_tokens


def request_email_verification(
    session: Session,
    *,
    email: str,
) -> EmailVerificationIssue | None:
    try:
        user = user_repository.get_user_by_email(
            session,
            email=email,
        )
    except InvalidUserEmail:
        return None

    if user is None or user.email_verified_at is not None:
        return None

    requested_at = utc_now()

    with session.begin_nested():
        email_verification_token_repository.consume_active_email_verification_tokens_for_user(
            session,
            user_id=user.id,
            consumed_at=requested_at,
        )
        verification = issue_email_verification(
            session,
            user=user,
        )

    return verification
