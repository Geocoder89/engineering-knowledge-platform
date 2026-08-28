from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.models.decision_alternative import DecisionAlternative


def create_decision_alternative(
    session: Session,
    *,
    decision_id: UUID,
    title: str,
    description: str,
) -> DecisionAlternative:
    decision_lock_statement = (
        select(Decision.id).where(Decision.id == decision_id).with_for_update()
    )
    session.execute(
        decision_lock_statement,
    ).one()

    maximum_position_statement = select(
        func.max(DecisionAlternative.position),
    ).where(
        DecisionAlternative.decision_id == decision_id,
    )
    maximum_position = session.scalar(
        maximum_position_statement,
    )
    next_position = maximum_position + 1 if maximum_position is not None else 0

    alternative = DecisionAlternative(
        decision_id=decision_id,
        title=title,
        description=description,
        position=next_position,
    )

    session.add(alternative)
    session.flush()

    return alternative


def list_decision_alternatives(
    session: Session,
    *,
    decision_id: UUID,
) -> list[DecisionAlternative]:
    statement = (
        select(DecisionAlternative)
        .where(
            DecisionAlternative.decision_id == decision_id,
        )
        .order_by(
            DecisionAlternative.position,
            DecisionAlternative.id,
        )
    )

    return list(
        session.scalars(statement).all(),
    )


def count_decision_alternatives(
    session: Session,
    *,
    decision_id: UUID,
) -> int:
    statement = (
        select(func.count())
        .select_from(DecisionAlternative)
        .where(
            DecisionAlternative.decision_id == decision_id,
        )
    )

    return session.scalar(statement) or 0


def get_decision_alternative_by_id(
    session: Session,
    *,
    decision_id: UUID,
    alternative_id: UUID,
) -> DecisionAlternative | None:
    statement = select(
        DecisionAlternative,
    ).where(
        DecisionAlternative.id == alternative_id,
        DecisionAlternative.decision_id == decision_id,
    )

    return session.scalar(statement)


def update_decision_alternative(
    session: Session,
    *,
    alternative: DecisionAlternative,
    title: str | None = None,
    description: str | None = None,
) -> DecisionAlternative:
    if title is not None:
        alternative.title = title

    if description is not None:
        alternative.description = description

    session.flush()

    return alternative


def delete_decision_alternative(
    session: Session,
    *,
    alternative: DecisionAlternative,
) -> None:
    decision_id = alternative.decision_id
    deleted_position = alternative.position

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

    session.delete(alternative)
    session.flush()

    later_alternatives_statement = (
        select(DecisionAlternative)
        .where(
            DecisionAlternative.decision_id == decision_id,
            DecisionAlternative.position > deleted_position,
        )
        .order_by(
            DecisionAlternative.position,
            DecisionAlternative.id,
        )
    )
    later_alternatives = list(
        session.scalars(
            later_alternatives_statement,
        ).all(),
    )

    for later_alternative in later_alternatives:
        later_alternative.position -= 1
        session.flush()
