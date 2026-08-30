from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user_password_credential import (
    UserPasswordCredential,
)


def create_user_password_credential(
    session: Session,
    *,
    user_id: UUID,
    password_hash: str,
    password_changed_at: datetime,
) -> UserPasswordCredential:
    credential = UserPasswordCredential(
        user_id=user_id,
        password_hash=password_hash,
        password_changed_at=password_changed_at,
    )
    session.add(
        credential,
    )
    session.flush()

    return credential


def get_user_password_credential(
    session: Session,
    *,
    user_id: UUID,
) -> UserPasswordCredential | None:
    return session.get(
        UserPasswordCredential,
        user_id,
    )


def replace_user_password_credential(
    session: Session,
    *,
    credential: UserPasswordCredential,
    password_hash: str,
    password_changed_at: datetime,
) -> UserPasswordCredential:
    credential.password_hash = password_hash
    credential.password_changed_at = password_changed_at
    session.flush()

    return credential
