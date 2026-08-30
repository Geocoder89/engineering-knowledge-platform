MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


class InvalidPassword(ValueError):
    pass


def validate_password(
    password: str,
) -> None:
    if not password.strip():
        raise InvalidPassword(
            "Password cannot be blank",
        )

    if len(password) < MIN_PASSWORD_LENGTH:
        raise InvalidPassword(
            f"Password must contain at least {MIN_PASSWORD_LENGTH} characters",
        )

    if len(password) > MAX_PASSWORD_LENGTH:
        raise InvalidPassword(
            f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters",
        )
