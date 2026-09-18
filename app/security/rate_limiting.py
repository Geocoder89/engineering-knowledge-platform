from hashlib import sha256


def hash_rate_limit_key(
    *,
    scope: str,
    raw_key: str,
) -> str:
    value_to_hash = f"{scope}\0{raw_key}"

    return sha256(
        value_to_hash.encode("utf-8"),
    ).hexdigest()
