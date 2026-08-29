from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.decision_audit import DecisionAuditEventType
from app.domain.decision_evidence import DecisionEvidenceCitation
from app.models.decision import Decision
from app.models.decision_alternative import DecisionAlternative
from app.models.decision_audit_event import DecisionAuditEvent
from app.repositories import (
    decision_audit as decision_audit_repository,
)


def record_decision_created(
    session: Session,
    *,
    decision: Decision,
) -> DecisionAuditEvent:
    return decision_audit_repository.append_decision_audit_event(
        session,
        decision_id=decision.id,
        event_type=DecisionAuditEventType.DECISION_CREATED,
        event_data={
            "title": decision.title,
            "question": decision.question,
            "status": decision.status,
        },
    )


def record_decision_alternative_added(
    session: Session,
    *,
    alternative: DecisionAlternative,
) -> DecisionAuditEvent:
    return decision_audit_repository.append_decision_audit_event(
        session,
        decision_id=alternative.decision_id,
        event_type=DecisionAuditEventType.ALTERNATIVE_ADDED,
        event_data={
            "alternative_id": str(
                alternative.id,
            ),
            "title": alternative.title,
            "description": alternative.description,
            "position": alternative.position,
        },
    )


def record_decision_alternative_updated(
    session: Session,
    *,
    alternative: DecisionAlternative,
    previous_values: dict[str, object],
    new_values: dict[str, object],
) -> DecisionAuditEvent:
    return decision_audit_repository.append_decision_audit_event(
        session,
        decision_id=alternative.decision_id,
        event_type=DecisionAuditEventType.ALTERNATIVE_UPDATED,
        event_data={
            "alternative_id": str(
                alternative.id,
            ),
            "previous": previous_values,
            "new": new_values,
        },
    )


def record_decision_alternative_removed(
    session: Session,
    *,
    decision_id: UUID,
    alternative_id: UUID,
    title: str,
    description: str,
    position: int,
    remaining_alternative_order: list[UUID],
) -> DecisionAuditEvent:
    return decision_audit_repository.append_decision_audit_event(
        session,
        decision_id=decision_id,
        event_type=DecisionAuditEventType.ALTERNATIVE_REMOVED,
        event_data={
            "alternative_id": str(
                alternative_id,
            ),
            "title": title,
            "description": description,
            "position": position,
            "remaining_alternative_order": [
                str(remaining_alternative_id)
                for remaining_alternative_id in remaining_alternative_order
            ],
        },
    )


def build_decision_evidence_event_data(
    citation: DecisionEvidenceCitation,
) -> dict[str, object]:
    return {
        "evidence_id": str(
            citation.decision_evidence_id,
        ),
        "alternative_id": str(
            citation.decision_alternative_id,
        ),
        "document_chunk_id": str(
            citation.document_chunk_id,
        ),
        "evidence_type": citation.evidence_type,
        "relevance_note": citation.relevance_note,
        "citation": {
            "document_id": str(
                citation.document_id,
            ),
            "document_version_id": str(
                citation.document_version_id,
            ),
            "document_page_id": str(
                citation.document_page_id,
            ),
            "document_title": citation.document_title,
            "file_name": citation.file_name,
            "version_number": citation.version_number,
            "page_number": citation.page_number,
            "chunk_index": citation.chunk_index,
            "text": citation.text,
            "start_offset": citation.start_offset,
            "end_offset": citation.end_offset,
        },
    }


def record_decision_evidence_added(
    session: Session,
    *,
    decision_id: UUID,
    citation: DecisionEvidenceCitation,
) -> DecisionAuditEvent:
    return decision_audit_repository.append_decision_audit_event(
        session,
        decision_id=decision_id,
        event_type=DecisionAuditEventType.EVIDENCE_ADDED,
        event_data=build_decision_evidence_event_data(
            citation,
        ),
    )


def record_decision_evidence_removed(
    session: Session,
    *,
    decision_id: UUID,
    citation: DecisionEvidenceCitation,
) -> DecisionAuditEvent:
    return decision_audit_repository.append_decision_audit_event(
        session,
        decision_id=decision_id,
        event_type=DecisionAuditEventType.EVIDENCE_REMOVED,
        event_data=build_decision_evidence_event_data(
            citation,
        ),
    )


def record_decision_submitted(
    session: Session,
    *,
    decision: Decision,
    previous_status: str,
    submitted_at: datetime,
) -> DecisionAuditEvent:
    return decision_audit_repository.append_decision_audit_event(
        session,
        decision_id=decision.id,
        event_type=DecisionAuditEventType.DECISION_SUBMITTED,
        event_data={
            "previous_status": previous_status,
            "new_status": decision.status,
            "submitted_at": submitted_at.isoformat(),
        },
    )


def record_decision_finalized(
    session: Session,
    *,
    decision: Decision,
    previous_status: str,
    selected_alternative_id: UUID,
    rationale: str,
    decided_at: datetime,
) -> DecisionAuditEvent:
    return decision_audit_repository.append_decision_audit_event(
        session,
        decision_id=decision.id,
        event_type=DecisionAuditEventType.DECISION_FINALIZED,
        event_data={
            "previous_status": previous_status,
            "new_status": decision.status,
            "selected_alternative_id": str(
                selected_alternative_id,
            ),
            "rationale": rationale,
            "decided_at": decided_at.isoformat(),
        },
    )


def record_decision_cancelled(
    session: Session,
    *,
    decision: Decision,
    previous_status: str,
    rationale: str,
    cancelled_at: datetime,
) -> DecisionAuditEvent:
    return decision_audit_repository.append_decision_audit_event(
        session,
        decision_id=decision.id,
        event_type=DecisionAuditEventType.DECISION_CANCELLED,
        event_data={
            "previous_status": previous_status,
            "new_status": decision.status,
            "rationale": rationale,
            "cancelled_at": cancelled_at.isoformat(),
        },
    )
