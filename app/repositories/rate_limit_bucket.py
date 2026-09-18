from datetime import datetime

from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.rate_limit_bucket import RateLimitBucket


def increment_rate_limit_bucket(
    session: Session,
    *,
    scope: str,
    key_hash: str,
    current_time: datetime,
    new_window_started_at: datetime,
    new_window_expires_at: datetime,
) -> RateLimitBucket:
    insert_statement = insert(RateLimitBucket).values(
        scope=scope,
        key_hash=key_hash,
        window_started_at=new_window_started_at,
        window_expires_at=new_window_expires_at,
        request_count=1,
    )

    existing_window_expired = RateLimitBucket.window_expires_at <= current_time

    statement = insert_statement.on_conflict_do_update(
        constraint="uq_rate_limit_buckets_scope_key_hash",
        set_={
            "request_count": case(
                (
                    existing_window_expired,
                    1,
                ),
                else_=RateLimitBucket.request_count + 1,
            ),
            "window_started_at": case(
                (
                    existing_window_expired,
                    new_window_started_at,
                ),
                else_=RateLimitBucket.window_started_at,
            ),
            "window_expires_at": case(
                (
                    existing_window_expired,
                    new_window_expires_at,
                ),
                else_=RateLimitBucket.window_expires_at,
            ),
        },
    ).returning(RateLimitBucket)

    return session.scalars(
        statement,
        execution_options={
            "populate_existing": True,
        },
    ).one()
