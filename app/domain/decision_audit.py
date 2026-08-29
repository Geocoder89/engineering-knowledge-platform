from enum import StrEnum


class DecisionAuditEventType(StrEnum):
    DECISION_CREATED = "decision_created"
    ALTERNATIVE_ADDED = "alternative_added"
    ALTERNATIVE_UPDATED = "alternative_updated"
    ALTERNATIVE_REMOVED = "alternative_removed"
    EVIDENCE_ADDED = "evidence_added"
    EVIDENCE_REMOVED = "evidence_removed"
    DECISION_SUBMITTED = "decision_submitted"
    DECISION_FINALIZED = "decision_finalized"
    DECISION_CANCELLED = "decision_cancelled"
    DECISION_SUPERSEDED = "decision_superseded"
