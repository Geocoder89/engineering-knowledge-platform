from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class InvalidUserEmail(ValueError):
    def __init__(self) -> None:
        super().__init__("User email cannot be blank")


def normalize_user_email(
    email: str,
) -> str:
    normalized_email = email.strip().lower()

    if not normalized_email:
        raise InvalidUserEmail()

    return normalized_email
