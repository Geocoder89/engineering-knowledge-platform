from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import user as user_repository
from app.services import user_password as user_password_service

USER_EMAIL_UNIQUE_CONSTRAINT = "uq_users_email"


def is_duplicate_user_email_error(
    error: IntegrityError,
) -> bool:
    diagnostic = getattr(
        error.orig,
        "diag",
        None,
    )
    constraint_name = getattr(
        diagnostic,
        "constraint_name",
        None,
    )

    return constraint_name == USER_EMAIL_UNIQUE_CONSTRAINT


class UserAlreadyExistsError(ValueError):
    def __init__(self) -> None:
        super().__init__(
            "User registration could not be completed",
        )


def register_user(
    session: Session,
    *,
    email: str,
    display_name: str,
    password: str,
) -> User:
    existing_user = user_repository.get_user_by_email(session, email=email)
    if existing_user is not None:
        raise UserAlreadyExistsError()

    try:
        with session.begin_nested():
            user = user_repository.create_user(
                session, email=email, display_name=display_name
            )
            user_password_service.set_user_password(
                session, user=user, password=password
            )

    except IntegrityError as error:
        if is_duplicate_user_email_error(error):
            raise UserAlreadyExistsError() from error

        raise
    return user
