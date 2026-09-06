from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_session import UserSession


def create_user_session(
    session: Session,
    *,
    user_id: UUID,
    token_hash: str,
    expires_at: datetime,
) -> UserSession:
    user_session = UserSession(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    session.add(user_session)
    session.flush()

    return user_session


def get_active_user_session_by_token_hash(
    session: Session,
    *,
    token_hash: str,
    current_time: datetime,
) -> UserSession | None:
    statement = select(UserSession).where(
        UserSession.token_hash == token_hash,
        UserSession.revoked_at.is_(None),
        UserSession.expires_at > current_time,
    )

    return session.scalar(statement)


def revoke_user_session(
    session: Session,
    *,
    user_session: UserSession,
    revoked_at: datetime,
) -> UserSession:
    user_session.revoked_at = revoked_at
    session.flush()

    return user_session
