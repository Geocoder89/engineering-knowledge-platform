from enum import StrEnum


class DecisionStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    DECIDED = "decided"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"
