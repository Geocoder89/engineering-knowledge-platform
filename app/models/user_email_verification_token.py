from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserEmailVerificationToken(Base):
    __tablename__ = "user_email_verification_tokens"
    __table_args__ = (
        UniqueConstraint(
            "token_hash",
            name="uq_user_email_verification_tokens_token_hash",
        ),
        CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'",
            name="ck_user_email_verification_tokens_token_hash_format",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_user_email_verification_tokens_expiry_after_creation",
        ),
        CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= created_at",
            name="ck_user_email_verification_tokens_consumption_after_creation",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
