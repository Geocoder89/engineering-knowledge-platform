from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (
        UniqueConstraint(
            "scope",
            "key_hash",
            name="uq_rate_limit_buckets_scope_key_hash",
        ),
        CheckConstraint(
            "length(scope) > 0",
            name="ck_rate_limit_buckets_scope_not_empty",
        ),
        CheckConstraint(
            "key_hash ~ '^[0-9a-f]{64}$'",
            name="ck_rate_limit_buckets_key_hash_format",
        ),
        CheckConstraint(
            "window_expires_at > window_started_at",
            name="ck_rate_limit_buckets_valid_window",
        ),
        CheckConstraint(
            "request_count >= 1",
            name="ck_rate_limit_buckets_positive_request_count",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    scope: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    window_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    request_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
