import hmac
import secrets
from collections.abc import Collection

CSRF_TOKEN_RANDOM_BYTES = 32


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(
        CSRF_TOKEN_RANDOM_BYTES,
    )


def csrf_tokens_match(
    *,
    cookie_token: str | None,
    header_token: str | None,
) -> bool:
    if not cookie_token or not header_token:
        return False

    return hmac.compare_digest(
        cookie_token,
        header_token,
    )


def is_trusted_request_origin(
    *,
    origin: str | None,
    trusted_origins: Collection[str],
) -> bool:
    if origin is None:
        return False

    return origin in trusted_origins
