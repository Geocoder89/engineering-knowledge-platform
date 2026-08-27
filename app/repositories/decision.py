from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
