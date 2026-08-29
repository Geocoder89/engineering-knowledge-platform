from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.decision_evidence import DecisionEvidenceCitation
from app.models.decision import Decision
from app.models.decision_alternative import DecisionAlternative
from app.repositories import decision as decision_repository
from app.repositories import decision_alternative as decision_alternative_repository
from app.repositories import (
    decision_audit as decision_audit_repository,
)
from app.repositories import decision_evidence as decision_evidence_repository


@dataclass(frozen=True)
class DecisionRecord:
    decision: Decision
    alternatives: list[DecisionAlternative]
    evidence_by_alternative_id: dict[
        UUID,
        list[DecisionEvidenceCitation],
    ]
    history_total: int


def get_decision_record(
    session: Session,
    *,
    decision_id: UUID,
) -> DecisionRecord | None:
    decision = decision_repository.get_decision_by_id(
        session,
        decision_id,
    )

    if decision is None:
        return None

    alternatives = decision_alternative_repository.list_decision_alternatives(
        session,
        decision_id=decision.id,
    )
    evidence = decision_evidence_repository.list_decision_evidence_for_decision(
        session,
        decision_id=decision.id,
    )
    history_total = decision_audit_repository.count_decision_audit_events(
        session,
        decision_id=decision.id,
    )

    evidence_by_alternative_id: dict[
        UUID,
        list[DecisionEvidenceCitation],
    ] = {alternative.id: [] for alternative in alternatives}

    for citation in evidence:
        evidence_by_alternative_id.setdefault(
            citation.decision_alternative_id,
            [],
        ).append(citation)

    return DecisionRecord(
        decision=decision,
        alternatives=alternatives,
        evidence_by_alternative_id=evidence_by_alternative_id,
        history_total=history_total,
    )
