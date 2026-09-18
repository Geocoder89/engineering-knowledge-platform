from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import Connection, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database import SessionLocal
from app.models.rate_limit_bucket import RateLimitBucket
from app.repositories import rate_limit_bucket as rate_limit_bucket_repository
from app.security.rate_limiting import hash_rate_limit_key
from app.services.rate_limiting import DatabaseRateLimiter


def test_hashes_rate_limit_keys_deterministically_without_exposing_raw_value() -> None:
    scope = "authentication.login.ip"
    raw_key = "203.0.113.10"

    first_hash = hash_rate_limit_key(
        scope=scope,
        raw_key=raw_key,
    )
    second_hash = hash_rate_limit_key(
        scope=scope,
        raw_key=raw_key,
    )

    assert first_hash == second_hash
    assert len(first_hash) == 64
    assert first_hash == first_hash.lower()
    assert all(character in "0123456789abcdef" for character in first_hash)
    assert raw_key not in first_hash


def test_rate_limit_key_hash_is_scoped() -> None:
    raw_key = "engineer@example.com"

    login_hash = hash_rate_limit_key(
        scope="authentication.login.email",
        raw_key=raw_key,
    )
    registration_hash = hash_rate_limit_key(
        scope="authentication.registration.email",
        raw_key=raw_key,
    )

    assert login_hash != registration_hash


def test_database_persists_rate_limit_bucket(
    db_session: Session,
) -> None:
    window_started_at = datetime.now(
        timezone.utc,
    )
    key_hash = hash_rate_limit_key(
        scope="authentication.login.ip",
        raw_key="203.0.113.10",
    )
    bucket = RateLimitBucket(
        scope="authentication.login.ip",
        key_hash=key_hash,
        window_started_at=window_started_at,
        window_expires_at=window_started_at
        + timedelta(
            minutes=15,
        ),
        request_count=1,
    )

    db_session.add(
        bucket,
    )
    db_session.flush()

    bucket_id = bucket.id
    db_session.expunge_all()

    persisted_bucket = db_session.get(
        RateLimitBucket,
        bucket_id,
    )

    assert persisted_bucket is not None
    assert persisted_bucket.scope == "authentication.login.ip"
    assert persisted_bucket.key_hash == key_hash
    assert persisted_bucket.request_count == 1
    assert persisted_bucket.window_started_at == window_started_at
    assert persisted_bucket.window_expires_at == (
        window_started_at
        + timedelta(
            minutes=15,
        )
    )


def test_repository_creates_and_increments_active_rate_limit_bucket(
    db_session: Session,
) -> None:
    window_started_at = datetime.now(timezone.utc)
    window_expires_at = window_started_at + timedelta(minutes=15)
    key_hash = hash_rate_limit_key(
        scope="authentication.login.ip",
        raw_key="203.0.113.10",
    )

    created_bucket = rate_limit_bucket_repository.increment_rate_limit_bucket(
        db_session,
        scope="authentication.login.ip",
        key_hash=key_hash,
        current_time=window_started_at,
        new_window_started_at=window_started_at,
        new_window_expires_at=window_expires_at,
    )

    bucket_id = created_bucket.id

    assert created_bucket.request_count == 1
    assert created_bucket.window_started_at == window_started_at
    assert created_bucket.window_expires_at == window_expires_at

    incremented_bucket = rate_limit_bucket_repository.increment_rate_limit_bucket(
        db_session,
        scope="authentication.login.ip",
        key_hash=key_hash,
        current_time=window_started_at + timedelta(minutes=1),
        new_window_started_at=window_started_at + timedelta(minutes=1),
        new_window_expires_at=window_expires_at + timedelta(minutes=1),
    )

    assert incremented_bucket.id == bucket_id
    assert incremented_bucket.request_count == 2

    # An active bucket keeps its original fixed-window boundaries.
    assert incremented_bucket.window_started_at == window_started_at
    assert incremented_bucket.window_expires_at == window_expires_at


def test_repository_resets_expired_rate_limit_bucket(
    db_session: Session,
) -> None:
    first_window_started_at = datetime.now(timezone.utc)
    first_window_expires_at = first_window_started_at + timedelta(minutes=15)
    key_hash = hash_rate_limit_key(
        scope="authentication.login.ip",
        raw_key="203.0.113.10",
    )

    existing_bucket = rate_limit_bucket_repository.increment_rate_limit_bucket(
        db_session,
        scope="authentication.login.ip",
        key_hash=key_hash,
        current_time=first_window_started_at,
        new_window_started_at=first_window_started_at,
        new_window_expires_at=first_window_expires_at,
    )

    bucket_id = existing_bucket.id

    rate_limit_bucket_repository.increment_rate_limit_bucket(
        db_session,
        scope="authentication.login.ip",
        key_hash=key_hash,
        current_time=first_window_started_at + timedelta(minutes=1),
        new_window_started_at=first_window_started_at + timedelta(minutes=1),
        new_window_expires_at=first_window_expires_at + timedelta(minutes=1),
    )

    second_window_started_at = first_window_expires_at
    second_window_expires_at = second_window_started_at + timedelta(minutes=15)

    reset_bucket = rate_limit_bucket_repository.increment_rate_limit_bucket(
        db_session,
        scope="authentication.login.ip",
        key_hash=key_hash,
        current_time=second_window_started_at,
        new_window_started_at=second_window_started_at,
        new_window_expires_at=second_window_expires_at,
    )

    assert reset_bucket.id == bucket_id
    assert reset_bucket.request_count == 1
    assert reset_bucket.window_started_at == second_window_started_at
    assert reset_bucket.window_expires_at == second_window_expires_at


def test_database_rate_limiter_allows_limit_then_rejects(
    database_connection: Connection,
) -> None:
    current_time = datetime.now(timezone.utc)
    rate_limit_session_factory = sessionmaker(
        bind=database_connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    limiter = DatabaseRateLimiter(
        session_factory=rate_limit_session_factory,
        clock=lambda: current_time,
    )

    decisions = [
        limiter.check(
            scope="authentication.login.ip",
            raw_key="203.0.113.10",
            limit=2,
            window=timedelta(minutes=15),
        )
        for _ in range(3)
    ]

    assert [decision.allowed for decision in decisions] == [
        True,
        True,
        False,
    ]
    assert [decision.retry_after_seconds for decision in decisions] == [
        None,
        None,
        900,
    ]


def test_database_rate_limiter_allows_request_after_window_expires(
    database_connection: Connection,
) -> None:
    current_time = datetime.now(timezone.utc)
    rate_limit_session_factory = sessionmaker(
        bind=database_connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    limiter = DatabaseRateLimiter(
        session_factory=rate_limit_session_factory,
        clock=lambda: current_time,
    )

    first_decision = limiter.check(
        scope="authentication.login.ip",
        raw_key="203.0.113.10",
        limit=1,
        window=timedelta(minutes=15),
    )
    rejected_decision = limiter.check(
        scope="authentication.login.ip",
        raw_key="203.0.113.10",
        limit=1,
        window=timedelta(minutes=15),
    )

    assert first_decision.allowed is True
    assert rejected_decision.allowed is False
    assert rejected_decision.retry_after_seconds == 900

    current_time += timedelta(minutes=15)

    next_window_decision = limiter.check(
        scope="authentication.login.ip",
        raw_key="203.0.113.10",
        limit=1,
        window=timedelta(minutes=15),
    )

    assert next_window_decision.allowed is True
    assert next_window_decision.retry_after_seconds is None


def test_concurrent_rate_limit_increments_are_not_lost() -> None:
    scope = "test.concurrent_rate_limit"
    raw_key = f"client-{uuid4()}"
    key_hash = hash_rate_limit_key(
        scope=scope,
        raw_key=raw_key,
    )
    current_time = datetime.now(timezone.utc)
    window_expires_at = current_time + timedelta(minutes=15)
    start_barrier = Barrier(2)

    def increment_bucket() -> int:
        start_barrier.wait()

        with SessionLocal.begin() as session:
            bucket = rate_limit_bucket_repository.increment_rate_limit_bucket(
                session,
                scope=scope,
                key_hash=key_hash,
                current_time=current_time,
                new_window_started_at=current_time,
                new_window_expires_at=window_expires_at,
            )

            return bucket.request_count

    try:
        with ThreadPoolExecutor(
            max_workers=2,
        ) as executor:
            first_increment = executor.submit(
                increment_bucket,
            )
            second_increment = executor.submit(
                increment_bucket,
            )

            returned_counts = sorted(
                [
                    first_increment.result(),
                    second_increment.result(),
                ],
            )

        assert returned_counts == [
            1,
            2,
        ]

        with SessionLocal() as session:
            persisted_bucket = session.scalar(
                select(RateLimitBucket).where(
                    RateLimitBucket.scope == scope,
                    RateLimitBucket.key_hash == key_hash,
                ),
            )

            assert persisted_bucket is not None
            assert persisted_bucket.request_count == 2
    finally:
        with SessionLocal.begin() as session:
            session.execute(
                delete(RateLimitBucket).where(
                    RateLimitBucket.scope == scope,
                    RateLimitBucket.key_hash == key_hash,
                ),
            )


def test_database_rate_limiter_persists_only_hashed_key(
    database_connection: Connection,
) -> None:
    current_time = datetime.now(timezone.utc)
    scope = "test.hashed_key"
    raw_key = "Engineer@Example.COM"
    rate_limit_session_factory = sessionmaker(
        bind=database_connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    limiter = DatabaseRateLimiter(
        session_factory=rate_limit_session_factory,
        clock=lambda: current_time,
    )

    limiter.check(
        scope=scope,
        raw_key=raw_key,
        limit=5,
        window=timedelta(minutes=15),
    )

    with rate_limit_session_factory() as session:
        persisted_bucket = session.scalar(
            select(RateLimitBucket).where(
                RateLimitBucket.scope == scope,
            ),
        )

    assert persisted_bucket is not None
    assert persisted_bucket.key_hash == hash_rate_limit_key(
        scope=scope,
        raw_key=raw_key,
    )
    assert persisted_bucket.key_hash != raw_key


@pytest.mark.parametrize(
    "scenario",
    [
        "empty_scope",
        "invalid_hash",
        "invalid_window",
        "invalid_count",
    ],
)
def test_database_enforces_rate_limit_bucket_constraints(
    db_session: Session,
    scenario: str,
) -> None:
    window_started_at = datetime.now(timezone.utc)
    values = {
        "scope": "authentication.login.ip",
        "key_hash": hash_rate_limit_key(
            scope="authentication.login.ip",
            raw_key="203.0.113.10",
        ),
        "window_started_at": window_started_at,
        "window_expires_at": (window_started_at + timedelta(minutes=15)),
        "request_count": 1,
    }

    if scenario == "empty_scope":
        values["scope"] = ""
    elif scenario == "invalid_hash":
        values["key_hash"] = "not-a-valid-hash"
    elif scenario == "invalid_window":
        values["window_expires_at"] = window_started_at
    elif scenario == "invalid_count":
        values["request_count"] = 0

    invalid_bucket = RateLimitBucket(
        **values,
    )

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(invalid_bucket)
            db_session.flush()
