from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DecisionAlternative(Base):
    __tablename__ = "decision_alternatives"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "position",
            name=("uq_decision_alternatives_decision_position"),
        ),
        CheckConstraint(
            "position >= 0",
            name=("ck_decision_alternatives_position_nonnegative"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    decision_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "decisions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.clock_timestamp(),
    )
