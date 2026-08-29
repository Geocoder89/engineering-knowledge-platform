from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.user import UserStatus, normalize_user_email
from app.models.user import User


def create_user(
    session: Session,
    *,
    email: str,
    display_name: str,
) -> User:
    user = User(
        email=normalize_user_email(email),
        display_name=display_name.strip(),
    )
    session.add(user)
    session.flush()

    return user


def get_user_by_id(
    session: Session,
    user_id: UUID,
) -> User | None:
    return session.get(
        User,
        user_id,
    )


def get_user_by_email(
    session: Session,
    *,
    email: str,
) -> User | None:
    normalized_email = normalize_user_email(
        email,
    )
    statement = select(
        User,
    ).where(
        User.email == normalized_email,
    )

    return session.scalar(
        statement,
    )


def set_user_status(
    session: Session,
    *,
    user: User,
    status: UserStatus,
) -> User:
    user.status = status.value
    session.flush()

    return user
