from hashlib import sha256
from secrets import token_urlsafe

EMAIL_VERIFICATION_TOKEN_BYTES = 32


def generate_email_verification_token() -> str:
    return token_urlsafe(
        EMAIL_VERIFICATION_TOKEN_BYTES,
    )


def hash_email_verification_token(
    token: str,
) -> str:
    return sha256(
        token.encode(
            "utf-8",
        )
    ).hexdigest()
