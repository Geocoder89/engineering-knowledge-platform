from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_email_verification_token import (
    UserEmailVerificationToken,
)


def create_email_verification_token(
    session: Session,
    *,
    user_id: UUID,
    token_hash: str,
    expires_at: datetime,
) -> UserEmailVerificationToken:
    verification_token = UserEmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    session.add(
        verification_token,
    )
    session.flush()

    return verification_token


def get_active_email_verification_token_by_token_hash(
    session: Session,
    *,
    token_hash: str,
    current_time: datetime,
) -> UserEmailVerificationToken | None:
    statement = (
        select(
            UserEmailVerificationToken,
        )
        .where(
            UserEmailVerificationToken.token_hash == token_hash,
            UserEmailVerificationToken.consumed_at.is_(None),
            UserEmailVerificationToken.expires_at > current_time,
        )
        .with_for_update()
    )

    return session.scalar(
        statement,
    )


def consume_email_verification_token(
    session: Session,
    *,
    verification_token: UserEmailVerificationToken,
    consumed_at: datetime,
) -> UserEmailVerificationToken:
    verification_token.consumed_at = consumed_at
    session.flush()

    return verification_token
