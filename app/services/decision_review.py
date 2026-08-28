from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.decision import (
    DecisionStatus,
    SelectedAlternativeNotPartOfDecision,
    validate_decision_status_transition,
    validate_decision_submission,
)
from app.models.decision import Decision
from app.repositories import (
    decision as decision_repository,
)
from app.repositories import (
    decision_alternative as decision_alternative_repository,
)
from app.repositories import (
    decision_evidence as decision_evidence_repository,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def submit_decision_for_review(
    session: Session,
    *,
    decision: Decision,
) -> Decision:
    alternative_count = decision_alternative_repository.count_decision_alternatives(
        session,
        decision_id=decision.id,
    )
    evidence_count = decision_evidence_repository.count_decision_evidence_for_decision(
        session,
        decision_id=decision.id,
    )

    validate_decision_submission(
        current_status=DecisionStatus(decision.status),
        alternative_count=alternative_count,
        evidence_count=evidence_count,
    )

    return decision_repository.submit_decision_for_review(
        session,
        decision=decision,
        submitted_at=utc_now(),
    )


def finalize_decision(
    session: Session,
    *,
    decision: Decision,
    selected_alternative_id: UUID,
    rationale: str,
) -> Decision:
    validate_decision_status_transition(
        DecisionStatus(decision.status),
        DecisionStatus.DECIDED,
    )

    selected_alternative = (
        decision_alternative_repository.get_decision_alternative_by_id(
            session,
            decision_id=decision.id,
            alternative_id=selected_alternative_id,
        )
    )

    if selected_alternative is None:
        raise SelectedAlternativeNotPartOfDecision()

    return decision_repository.finalize_decision(
        session,
        decision=decision,
        selected_alternative_id=selected_alternative.id,
        rationale=rationale,
        decided_at=utc_now(),
    )


def cancel_decision(
    session: Session,
    *,
    decision: Decision,
    rationale: str,
) -> Decision:
    validate_decision_status_transition(
        DecisionStatus(decision.status),
        DecisionStatus.CANCELLED,
    )

    return decision_repository.cancel_decision(
        session,
        decision=decision,
        rationale=rationale,
        cancelled_at=utc_now(),
    )
