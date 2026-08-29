from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.decision_audit import DecisionAuditEventType
from app.models.decision import Decision
from app.models.decision_audit_event import DecisionAuditEvent


def append_decision_audit_event(
    session: Session,
    *,
    decision_id: UUID,
    event_type: DecisionAuditEventType,
    event_data: dict[str, object],
) -> DecisionAuditEvent:
    decision_lock_statement = (
        select(Decision.id)
        .where(
            Decision.id == decision_id,
        )
        .with_for_update()
    )
    session.execute(
        decision_lock_statement,
    ).one()

    maximum_sequence_statement = select(
        func.max(
            DecisionAuditEvent.sequence_number,
        )
    ).where(
        DecisionAuditEvent.decision_id == decision_id,
    )
    maximum_sequence = session.scalar(
        maximum_sequence_statement,
    )
    next_sequence = maximum_sequence + 1 if maximum_sequence is not None else 1

    event = DecisionAuditEvent(
        decision_id=decision_id,
        sequence_number=next_sequence,
        event_type=event_type.value,
        event_data=event_data,
    )
    session.add(event)
    session.flush()

    return event


def list_decision_audit_events(
    session: Session,
    *,
    decision_id: UUID,
    offset: int = 0,
    limit: int = 100,
) -> list[DecisionAuditEvent]:
    statement = (
        select(DecisionAuditEvent)
        .where(
            DecisionAuditEvent.decision_id == decision_id,
        )
        .order_by(
            DecisionAuditEvent.sequence_number,
            DecisionAuditEvent.id,
        )
        .offset(offset)
        .limit(limit)
    )

    return list(
        session.scalars(statement).all(),
    )


def count_decision_audit_events(
    session: Session,
    *,
    decision_id: UUID,
) -> int:
    statement = (
        select(func.count())
        .select_from(DecisionAuditEvent)
        .where(
            DecisionAuditEvent.decision_id == decision_id,
        )
    )

    return session.scalar(statement) or 0
