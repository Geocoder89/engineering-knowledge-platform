from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_password_credential import (
    UserPasswordCredential,
)
from app.repositories import (
    user_password_credential as user_password_credential_repository,
)
from app.security.password import hash_password


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc,
    )


def set_user_password(
    session: Session,
    *,
    user: User,
    password: str,
) -> UserPasswordCredential:
    password_hash = hash_password(
        password=password,
    )
    password_changed_at = utc_now()

    credential = user_password_credential_repository.get_user_password_credential(
        session,
        user_id=user.id,
    )

    if credential is None:
        return user_password_credential_repository.create_user_password_credential(
            session,
            user_id=user.id,
            password_hash=password_hash,
            password_changed_at=password_changed_at,
        )

    return user_password_credential_repository.replace_user_password_credential(
        session,
        credential=credential,
        password_hash=password_hash,
        password_changed_at=password_changed_at,
    )
