from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from app.repositories import rate_limit_bucket as rate_limit_bucket_repository
from app.security.rate_limiting import hash_rate_limit_key

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int | None


class RateLimiter(Protocol):
    def check(
        self,
        *,
        scope: str,
        raw_key: str,
        limit: int,
        window: timedelta,
    ) -> RateLimitDecision: ...


class DatabaseRateLimiter:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        clock: Clock = utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def check(
        self,
        *,
        scope: str,
        raw_key: str,
        limit: int,
        window: timedelta,
    ) -> RateLimitDecision:
        if limit < 1:
            raise ValueError("Rate limit must be positive")

        if window <= timedelta(0):
            raise ValueError("Rate limit window must be positive")

        current_time = self._clock()
        window_expires_at = current_time + window
        key_hash = hash_rate_limit_key(
            scope=scope,
            raw_key=raw_key,
        )

        with self._session_factory.begin() as session:
            bucket = rate_limit_bucket_repository.increment_rate_limit_bucket(
                session,
                scope=scope,
                key_hash=key_hash,
                current_time=current_time,
                new_window_started_at=current_time,
                new_window_expires_at=window_expires_at,
            )

            if bucket.request_count <= limit:
                return RateLimitDecision(
                    allowed=True,
                    retry_after_seconds=None,
                )

            retry_after_seconds = max(
                1,
                ceil((bucket.window_expires_at - current_time).total_seconds()),
            )

            return RateLimitDecision(
                allowed=False,
                retry_after_seconds=retry_after_seconds,
            )
