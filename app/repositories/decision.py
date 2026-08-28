from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.decision import DecisionStatus
from app.models.decision import Decision


def create_decision(
    session: Session,
    *,
    title: str,
    question: str,
) -> Decision:
    decision = Decision(title=title, question=question)
    session.add(decision)
    session.flush()
    return decision


def list_decisions(
    session: Session,
    *,
    offset: int,
    limit: int,
) -> list[Decision]:
    statement = (
        select(Decision)
        .order_by(
            Decision.created_at.desc(),
            Decision.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(
        session.scalars(statement).all(),
    )


def count_decisions(
    session: Session,
) -> int:
    statement = select(func.count()).select_from(Decision)

    return session.scalar(statement) or 0


def get_decision_by_id(
    session: Session,
    decision_id: UUID,
) -> Decision | None:
    return session.get(Decision, decision_id)


def submit_decision_for_review(
    session: Session,
    *,
    decision: Decision,
    submitted_at: datetime,
) -> Decision:
    decision.status = DecisionStatus.IN_REVIEW.value
    decision.submitted_at = submitted_at
    decision.selected_alternative_id = None
    decision.rationale = None
    decision.decided_at = None
    decision.cancelled_at = None
    decision.superseded_at = None

    session.flush()

    return decision


def get_decision_by_id_for_update(
    session: Session,
    decision_id: UUID,
) -> Decision | None:
    statement = (
        select(Decision)
        .where(
            Decision.id == decision_id,
        )
        .with_for_update()
    )

    return session.scalar(
        statement,
    )


def finalize_decision(
    session: Session,
    *,
    decision: Decision,
    selected_alternative_id: UUID,
    rationale: str,
    decided_at: datetime,
) -> Decision:
    decision.status = DecisionStatus.DECIDED.value
    decision.selected_alternative_id = selected_alternative_id
    decision.rationale = rationale
    decision.decided_at = decided_at
    decision.cancelled_at = None
    decision.superseded_at = None

    session.flush()

    return decision


def cancel_decision(
    session: Session,
    *,
    decision: Decision,
    rationale: str,
    cancelled_at: datetime,
) -> Decision:
    decision.status = DecisionStatus.CANCELLED.value
    decision.selected_alternative_id = None
    decision.rationale = rationale
    decision.decided_at = None
    decision.cancelled_at = cancelled_at
    decision.superseded_at = None

    session.flush()

    return decision
