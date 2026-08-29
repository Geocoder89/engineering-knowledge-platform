from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DecisionAuditEvent(Base):
    __tablename__ = "decision_audit_events"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "sequence_number",
            name="uq_decision_audit_events_decision_sequence",
        ),
        CheckConstraint(
            "sequence_number > 0",
            name="ck_decision_audit_events_sequence_positive",
        ),
        CheckConstraint(
            (
                "event_type IN ("
                "'decision_created', "
                "'alternative_added', "
                "'alternative_updated', "
                "'alternative_removed', "
                "'evidence_added', "
                "'evidence_removed', "
                "'decision_submitted', "
                "'decision_finalized', "
                "'decision_cancelled', "
                "'decision_superseded'"
                ")"
            ),
            name="ck_decision_audit_events_type",
        ),
        CheckConstraint(
            "jsonb_typeof(event_data) = 'object'",
            name="ck_decision_audit_events_data_object",
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
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    event_data: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
