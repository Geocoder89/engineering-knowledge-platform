from enum import StrEnum


class DecisionStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    DECIDED = "decided"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class DecisionNotEditable(ValueError):
    def __init__(self) -> None:
        super().__init__("Decision can only be modified while in draft")


def validate_decision_is_editable(
    status: DecisionStatus,
) -> None:
    if status != DecisionStatus.DRAFT:
        raise DecisionNotEditable()


class SelectedAlternativeNotPartOfDecision(ValueError):
    def __init__(self) -> None:
        super().__init__("Selected alternative does not belong to decision")


ALLOWED_DECISION_STATUS_TRANSITIONS: dict[
    DecisionStatus,
    frozenset[DecisionStatus],
] = {
    DecisionStatus.DRAFT: frozenset(
        {
            DecisionStatus.IN_REVIEW,
            DecisionStatus.CANCELLED,
        }
    ),
    DecisionStatus.IN_REVIEW: frozenset(
        {
            DecisionStatus.DECIDED,
            DecisionStatus.CANCELLED,
        }
    ),
    DecisionStatus.DECIDED: frozenset(
        {
            DecisionStatus.SUPERSEDED,
        }
    ),
    DecisionStatus.CANCELLED: frozenset(),
    DecisionStatus.SUPERSEDED: frozenset(),
}


class InvalidDecisionStatusTransition(ValueError):
    def __init__(
        self,
        current_status: DecisionStatus,
        target_status: DecisionStatus,
    ) -> None:
        super().__init__(
            "Cannot transition decision from "
            f"'{current_status.value}' to "
            f"'{target_status.value}'"
        )


class DecisionReviewRequirementsNotMet(ValueError):
    pass


def validate_decision_status_transition(
    current_status: DecisionStatus,
    target_status: DecisionStatus,
) -> None:
    allowed_targets = ALLOWED_DECISION_STATUS_TRANSITIONS[current_status]

    if target_status not in allowed_targets:
        raise InvalidDecisionStatusTransition(
            current_status,
            target_status,
        )


def validate_decision_submission(
    *,
    current_status: DecisionStatus,
    alternative_count: int,
    evidence_count: int,
) -> None:
    validate_decision_status_transition(
        current_status,
        DecisionStatus.IN_REVIEW,
    )

    if alternative_count < 2:
        raise DecisionReviewRequirementsNotMet(
            "Decision requires at least 2 alternatives before review"
        )

    if evidence_count < 1:
        raise DecisionReviewRequirementsNotMet(
            "Decision requires at least 1 evidence link before review"
        )
