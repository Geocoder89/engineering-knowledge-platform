from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DecisionEvidence(Base):
    __tablename__ = "decision_evidence"
    __table_args__ = (
        UniqueConstraint(
            "decision_alternative_id",
            "document_chunk_id",
            name=("uq_decision_evidence_alternative_chunk"),
        ),
        CheckConstraint(
            ("evidence_type IN ('supporting', 'opposing')"),
            name="ck_decision_evidence_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    decision_alternative_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "decision_alternatives.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    document_chunk_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "document_chunks.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    evidence_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    relevance_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
