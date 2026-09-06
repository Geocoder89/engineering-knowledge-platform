from hashlib import sha256
from secrets import token_urlsafe

SESSION_TOKEN_BYTES = 32


def generate_session_token() -> str:
    return token_urlsafe(
        SESSION_TOKEN_BYTES,
    )


def hash_session_token(
    token: str,
) -> str:
    return sha256(
        token.encode(
            "utf-8",
        )
    ).hexdigest()
