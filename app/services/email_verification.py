from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

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
