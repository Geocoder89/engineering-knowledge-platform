from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.decision import (
    DecisionReviewRequirementsNotMet,
    DecisionStatus,
    InvalidDecisionStatusTransition,
    validate_decision_status_transition,
    validate_decision_submission,
)
from app.models.decision import Decision
from app.models.decision_alternative import DecisionAlternative
from app.models.decision_evidence import DecisionEvidence
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion
from app.services import (
    decision_review as decision_review_service,
)


def create_reviewable_decision(
    session: Session,
) -> Decision:
    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    session.add(decision)
    session.flush()

    alternatives = [
        DecisionAlternative(
            decision_id=decision.id,
            title="Keep the existing limit",
            description=("Retain the currently approved maximum pressure."),
            position=0,
        ),
        DecisionAlternative(
            decision_id=decision.id,
            title="Reduce the pressure limit",
            description=(
                "Lower the approved maximum pressure to improve the safety margin."
            ),
            position=1,
        ),
    ]
    session.add_all(alternatives)
    session.flush()

    document = Document(
        title="Cooling system",
        file_name="cooling-design.pdf",
        status="ready",
    )
    session.add(document)
    session.flush()

    document_version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_name="cooling-design.pdf",
        content_type="application/pdf",
        size_bytes=100,
        checksum_sha256="b" * 64,
        storage_key=f"{document.id}/version-1",
    )
    session.add(document_version)
    session.flush()

    page_text = (
        "Reducing maximum operating pressure increases the available safety margin."
    )
    document_page = DocumentPage(
        document_version_id=document_version.id,
        page_number=4,
        text=page_text,
    )
    session.add(document_page)
    session.flush()

    document_chunk = DocumentChunk(
        document_page_id=document_page.id,
        chunk_index=0,
        text=page_text,
        start_offset=0,
        end_offset=len(page_text),
    )
    session.add(document_chunk)
    session.flush()

    evidence = DecisionEvidence(
        decision_alternative_id=alternatives[1].id,
        document_chunk_id=document_chunk.id,
        evidence_type="supporting",
        relevance_note=("This source supports reducing the limit."),
    )
    session.add(evidence)
    session.flush()

    return decision


@pytest.mark.parametrize(
    (
        "current_status",
        "target_status",
    ),
    [
        (
            DecisionStatus.DRAFT,
            DecisionStatus.IN_REVIEW,
        ),
        (
            DecisionStatus.DRAFT,
            DecisionStatus.CANCELLED,
        ),
        (
            DecisionStatus.IN_REVIEW,
            DecisionStatus.DECIDED,
        ),
        (
            DecisionStatus.IN_REVIEW,
            DecisionStatus.CANCELLED,
        ),
        (
            DecisionStatus.DECIDED,
            DecisionStatus.SUPERSEDED,
        ),
    ],
)
def test_allows_valid_decision_status_transition(
    current_status: DecisionStatus,
    target_status: DecisionStatus,
) -> None:
    validate_decision_status_transition(
        current_status,
        target_status,
    )


@pytest.mark.parametrize(
    (
        "current_status",
        "target_status",
    ),
    [
        (
            DecisionStatus.DRAFT,
            DecisionStatus.DRAFT,
        ),
        (
            DecisionStatus.DRAFT,
            DecisionStatus.DECIDED,
        ),
        (
            DecisionStatus.IN_REVIEW,
            DecisionStatus.DRAFT,
        ),
        (
            DecisionStatus.DECIDED,
            DecisionStatus.IN_REVIEW,
        ),
        (
            DecisionStatus.DECIDED,
            DecisionStatus.CANCELLED,
        ),
        (
            DecisionStatus.CANCELLED,
            DecisionStatus.IN_REVIEW,
        ),
        (
            DecisionStatus.SUPERSEDED,
            DecisionStatus.DRAFT,
        ),
    ],
)
def test_rejects_invalid_decision_status_transition(
    current_status: DecisionStatus,
    target_status: DecisionStatus,
) -> None:
    with pytest.raises(
        InvalidDecisionStatusTransition,
        match=(
            "Cannot transition decision from "
            f"'{current_status.value}' to "
            f"'{target_status.value}'"
        ),
    ):
        validate_decision_status_transition(
            current_status,
            target_status,
        )


def test_database_persists_decision_review_outcome_fields(
    db_session: Session,
) -> None:
    expected_columns = {
        "selected_alternative_id",
        "rationale",
        "submitted_at",
        "decided_at",
        "cancelled_at",
        "superseded_at",
    }

    assert expected_columns.issubset(
        Decision.__table__.columns.keys(),
    )

    submitted_at = datetime(
        2026,
        8,
        28,
        12,
        0,
        tzinfo=timezone.utc,
    )
    decided_at = datetime(
        2026,
        8,
        28,
        13,
        0,
        tzinfo=timezone.utc,
    )

    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    db_session.add(decision)
    db_session.flush()

    alternative = DecisionAlternative(
        decision_id=decision.id,
        title="Reduce the pressure limit",
        description=(
            "Lower the approved maximum pressure to improve the safety margin."
        ),
        position=0,
    )
    db_session.add(alternative)
    db_session.flush()

    decision.status = "decided"
    decision.selected_alternative_id = alternative.id
    decision.rationale = (
        "This alternative provides the strongest documented safety improvement."
    )
    decision.submitted_at = submitted_at
    decision.decided_at = decided_at
    db_session.flush()

    assert decision.selected_alternative_id == alternative.id
    assert decision.rationale == (
        "This alternative provides the strongest documented safety improvement."
    )
    assert decision.submitted_at == submitted_at
    assert decision.decided_at == decided_at
    assert decision.cancelled_at is None
    assert decision.superseded_at is None


def test_allows_complete_decision_to_be_submitted() -> None:
    validate_decision_submission(
        current_status=DecisionStatus.DRAFT,
        alternative_count=2,
        evidence_count=1,
    )


@pytest.mark.parametrize(
    (
        "alternative_count",
        "evidence_count",
        "expected_message",
    ),
    [
        (
            0,
            1,
            ("Decision requires at least 2 alternatives before review"),
        ),
        (
            1,
            1,
            ("Decision requires at least 2 alternatives before review"),
        ),
        (
            2,
            0,
            ("Decision requires at least 1 evidence link before review"),
        ),
    ],
)
def test_rejects_incomplete_decision_submission(
    alternative_count: int,
    evidence_count: int,
    expected_message: str,
) -> None:
    with pytest.raises(
        DecisionReviewRequirementsNotMet,
        match=expected_message,
    ):
        validate_decision_submission(
            current_status=DecisionStatus.DRAFT,
            alternative_count=alternative_count,
            evidence_count=evidence_count,
        )


def test_service_submits_complete_decision_for_review(
    monkeypatch,
) -> None:
    session = Mock(
        spec=Session,
    )
    submitted_at = datetime(
        2026,
        8,
        28,
        14,
        0,
        tzinfo=timezone.utc,
    )
    decision = Decision(
        id=uuid4(),
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
        status="draft",
    )

    count_alternatives = Mock(
        return_value=2,
    )
    count_evidence = Mock(
        return_value=1,
    )

    monkeypatch.setattr(
        (decision_review_service.decision_alternative_repository),
        "count_decision_alternatives",
        count_alternatives,
    )
    monkeypatch.setattr(
        (decision_review_service.decision_evidence_repository),
        "count_decision_evidence_for_decision",
        count_evidence,
    )
    monkeypatch.setattr(
        decision_review_service,
        "utc_now",
        lambda: submitted_at,
    )

    submitted_decision = decision_review_service.submit_decision_for_review(
        session,
        decision=decision,
    )

    count_alternatives.assert_called_once_with(
        session,
        decision_id=decision.id,
    )
    count_evidence.assert_called_once_with(
        session,
        decision_id=decision.id,
    )

    assert submitted_decision is decision
    assert submitted_decision.status == "in_review"
    assert submitted_decision.submitted_at == submitted_at
    assert submitted_decision.selected_alternative_id is None
    assert submitted_decision.rationale is None
    assert submitted_decision.decided_at is None

    session.flush.assert_called_once_with()


def test_submits_complete_decision_for_review(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    decision = create_reviewable_decision(
        db_session,
    )
    submitted_at = datetime(
        2026,
        8,
        28,
        15,
        0,
        tzinfo=timezone.utc,
    )

    monkeypatch.setattr(
        decision_review_service,
        "utc_now",
        lambda: submitted_at,
    )

    response = client.post(
        f"/decisions/{decision.id}/submit",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == str(decision.id)
    assert body["status"] == "in_review"
    assert (
        datetime.fromisoformat(
            body["submitted_at"].replace(
                "Z",
                "+00:00",
            )
        )
        == submitted_at
    )
    assert body["selected_alternative_id"] is None
    assert body["rationale"] is None
    assert body["decided_at"] is None
    assert body["cancelled_at"] is None
    assert body["superseded_at"] is None


def test_finalizes_decision_with_selected_alternative(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    decision = create_reviewable_decision(
        db_session,
    )
    selected_alternative = db_session.scalar(
        select(DecisionAlternative).where(
            DecisionAlternative.decision_id == decision.id,
            DecisionAlternative.position == 1,
        )
    )

    assert selected_alternative is not None

    submitted_at = datetime(
        2026,
        8,
        28,
        15,
        0,
        tzinfo=timezone.utc,
    )
    decided_at = datetime(
        2026,
        8,
        28,
        16,
        0,
        tzinfo=timezone.utc,
    )
    timestamps = iter(
        [
            submitted_at,
            decided_at,
        ]
    )

    monkeypatch.setattr(
        decision_review_service,
        "utc_now",
        lambda: next(timestamps),
    )

    submit_response = client.post(
        f"/decisions/{decision.id}/submit",
    )

    assert submit_response.status_code == 200

    rationale = (
        "Reducing the pressure limit provides the "
        "strongest documented safety improvement."
    )
    response = client.post(
        f"/decisions/{decision.id}/decide",
        json={
            "selected_alternative_id": str(
                selected_alternative.id,
            ),
            "rationale": rationale,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == str(decision.id)
    assert body["status"] == "decided"
    assert body["selected_alternative_id"] == str(
        selected_alternative.id,
    )
    assert body["rationale"] == rationale
    assert (
        datetime.fromisoformat(
            body["submitted_at"].replace(
                "Z",
                "+00:00",
            )
        )
        == submitted_at
    )
    assert (
        datetime.fromisoformat(
            body["decided_at"].replace(
                "Z",
                "+00:00",
            )
        )
        == decided_at
    )
    assert body["cancelled_at"] is None
    assert body["superseded_at"] is None


def test_cancels_decision_under_review(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    decision = create_reviewable_decision(
        db_session,
    )
    submitted_at = datetime(
        2026,
        8,
        28,
        15,
        0,
        tzinfo=timezone.utc,
    )
    cancelled_at = datetime(
        2026,
        8,
        28,
        16,
        30,
        tzinfo=timezone.utc,
    )
    timestamps = iter(
        [
            submitted_at,
            cancelled_at,
        ]
    )

    monkeypatch.setattr(
        decision_review_service,
        "utc_now",
        lambda: next(timestamps),
    )

    submit_response = client.post(
        f"/decisions/{decision.id}/submit",
    )

    assert submit_response.status_code == 200

    cancellation_reason = (
        "The project requirements changed before a final alternative was selected."
    )
    response = client.post(
        f"/decisions/{decision.id}/cancel",
        json={
            "rationale": cancellation_reason,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == str(decision.id)
    assert body["status"] == "cancelled"
    assert body["selected_alternative_id"] is None
    assert body["rationale"] == cancellation_reason
    assert (
        datetime.fromisoformat(
            body["submitted_at"].replace(
                "Z",
                "+00:00",
            )
        )
        == submitted_at
    )
    assert body["decided_at"] is None
    assert (
        datetime.fromisoformat(
            body["cancelled_at"].replace(
                "Z",
                "+00:00",
            )
        )
        == cancelled_at
    )
    assert body["superseded_at"] is None


@pytest.mark.parametrize(
    "operation",
    [
        "create",
        "update",
        "delete",
    ],
)
def test_prevents_alternative_changes_after_submission(
    client,
    db_session: Session,
    operation: str,
) -> None:
    decision = create_reviewable_decision(
        db_session,
    )
    alternative = db_session.scalar(
        select(DecisionAlternative).where(
            DecisionAlternative.decision_id == decision.id,
            DecisionAlternative.position == 0,
        )
    )

    assert alternative is not None

    submit_response = client.post(
        f"/decisions/{decision.id}/submit",
    )

    assert submit_response.status_code == 200

    alternatives_url = f"/decisions/{decision.id}/alternatives"

    if operation == "create":
        response = client.post(
            alternatives_url,
            json={
                "title": "Replace the pressure system",
                "description": (
                    "Replace the existing system with a lower-pressure design."
                ),
            },
        )
    elif operation == "update":
        response = client.patch(
            f"{alternatives_url}/{alternative.id}",
            json={
                "title": "Change the existing alternative",
            },
        )
    else:
        response = client.delete(
            f"{alternatives_url}/{alternative.id}",
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": ("Decision can only be modified while in draft"),
    }


@pytest.mark.parametrize(
    "operation",
    [
        "create",
        "delete",
    ],
)
def test_prevents_evidence_changes_after_submission(
    client,
    db_session: Session,
    operation: str,
) -> None:
    decision = create_reviewable_decision(
        db_session,
    )

    existing_evidence = db_session.scalar(
        select(DecisionEvidence)
        .join(
            DecisionAlternative,
            DecisionAlternative.id == DecisionEvidence.decision_alternative_id,
        )
        .where(
            DecisionAlternative.decision_id == decision.id,
        )
    )

    assert existing_evidence is not None

    other_alternative = db_session.scalar(
        select(DecisionAlternative).where(
            DecisionAlternative.decision_id == decision.id,
            DecisionAlternative.id != existing_evidence.decision_alternative_id,
        )
    )

    assert other_alternative is not None

    submit_response = client.post(
        f"/decisions/{decision.id}/submit",
    )

    assert submit_response.status_code == 200

    if operation == "create":
        response = client.post(
            (f"/decisions/{decision.id}/alternatives/{other_alternative.id}/evidence"),
            json={
                "document_chunk_id": str(
                    existing_evidence.document_chunk_id,
                ),
                "evidence_type": "opposing",
                "relevance_note": (
                    "This source is relevant when evaluating this alternative."
                ),
            },
        )
    else:
        response = client.delete(
            (
                f"/decisions/{decision.id}"
                f"/alternatives/"
                f"{existing_evidence.decision_alternative_id}"
                f"/evidence/{existing_evidence.id}"
            ),
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Decision can only be modified while in draft",
    }


@pytest.mark.parametrize(
    (
        "alternative_count",
        "expected_detail",
    ),
    [
        (
            0,
            "Decision requires at least 2 alternatives before review",
        ),
        (
            1,
            "Decision requires at least 2 alternatives before review",
        ),
        (
            2,
            "Decision requires at least 1 evidence link before review",
        ),
    ],
)
def test_api_rejects_incomplete_decision_submission(
    client,
    db_session: Session,
    alternative_count: int,
    expected_detail: str,
) -> None:
    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    db_session.add(decision)
    db_session.flush()

    for position in range(
        alternative_count,
    ):
        db_session.add(
            DecisionAlternative(
                decision_id=decision.id,
                title=f"Alternative {position + 1}",
                description=(
                    f"Evaluate alternative {position + 1} "
                    "for the final engineering decision."
                ),
                position=position,
            )
        )

    db_session.flush()

    response = client.post(
        f"/decisions/{decision.id}/submit",
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": expected_detail,
    }

    db_session.expire_all()

    persisted_decision = db_session.get(
        Decision,
        decision.id,
    )

    assert persisted_decision is not None
    assert persisted_decision.status == "draft"
    assert persisted_decision.submitted_at is None


@pytest.mark.parametrize(
    "scenario",
    [
        "submit_twice",
        "decide_from_draft",
        "cancel_after_decision",
    ],
)
def test_api_rejects_invalid_decision_transition(
    client,
    db_session: Session,
    scenario: str,
) -> None:
    decision = create_reviewable_decision(
        db_session,
    )
    selected_alternative = db_session.scalar(
        select(DecisionAlternative).where(
            DecisionAlternative.decision_id == decision.id,
            DecisionAlternative.position == 0,
        )
    )

    assert selected_alternative is not None

    if scenario == "submit_twice":
        first_response = client.post(
            f"/decisions/{decision.id}/submit",
        )

        assert first_response.status_code == 200

        response = client.post(
            f"/decisions/{decision.id}/submit",
        )
        expected_status = "in_review"

    elif scenario == "decide_from_draft":
        response = client.post(
            f"/decisions/{decision.id}/decide",
            json={
                "selected_alternative_id": str(
                    selected_alternative.id,
                ),
                "rationale": (
                    "This alternative provides the strongest "
                    "documented engineering outcome."
                ),
            },
        )
        expected_status = "draft"

    else:
        submit_response = client.post(
            f"/decisions/{decision.id}/submit",
        )

        assert submit_response.status_code == 200

        decide_response = client.post(
            f"/decisions/{decision.id}/decide",
            json={
                "selected_alternative_id": str(
                    selected_alternative.id,
                ),
                "rationale": (
                    "This alternative provides the strongest "
                    "documented engineering outcome."
                ),
            },
        )

        assert decide_response.status_code == 200

        response = client.post(
            f"/decisions/{decision.id}/cancel",
            json={
                "rationale": (
                    "Attempt to cancel an already finalized engineering decision."
                ),
            },
        )
        expected_status = "decided"

    assert response.status_code == 409

    db_session.expire_all()

    persisted_decision = db_session.get(
        Decision,
        decision.id,
    )

    assert persisted_decision is not None
    assert persisted_decision.status == expected_status

    if scenario == "decide_from_draft":
        assert persisted_decision.selected_alternative_id is None
        assert persisted_decision.decided_at is None

    if scenario == "cancel_after_decision":
        assert persisted_decision.decided_at is not None
        assert persisted_decision.cancelled_at is None


def test_rejects_selected_alternative_from_another_decision(
    client,
    db_session: Session,
) -> None:
    decision = create_reviewable_decision(
        db_session,
    )

    other_decision = Decision(
        title="Electrical cable selection",
        question=("Which electrical cable specification should the project adopt?"),
    )
    db_session.add(other_decision)
    db_session.flush()

    foreign_alternative = DecisionAlternative(
        decision_id=other_decision.id,
        title="Use the higher-capacity cable",
        description=("Select a higher-capacity cable for the electrical installation."),
        position=0,
    )
    db_session.add(foreign_alternative)
    db_session.flush()

    submit_response = client.post(
        f"/decisions/{decision.id}/submit",
    )

    assert submit_response.status_code == 200

    response = client.post(
        f"/decisions/{decision.id}/decide",
        json={
            "selected_alternative_id": str(
                foreign_alternative.id,
            ),
            "rationale": ("This alternative appears to provide the strongest outcome."),
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Selected alternative does not belong to decision",
    }

    db_session.expire_all()

    persisted_decision = db_session.get(
        Decision,
        decision.id,
    )

    assert persisted_decision is not None
    assert persisted_decision.status == "in_review"
    assert persisted_decision.selected_alternative_id is None
    assert persisted_decision.rationale is None
    assert persisted_decision.decided_at is None


@pytest.mark.parametrize(
    (
        "operation",
        "invalid_case",
    ),
    [
        (
            "decide",
            "blank_rationale",
        ),
        (
            "decide",
            "missing_alternative",
        ),
        (
            "decide",
            "extra_field",
        ),
        (
            "cancel",
            "blank_rationale",
        ),
        (
            "cancel",
            "null_rationale",
        ),
        (
            "cancel",
            "extra_field",
        ),
    ],
)
def test_rejects_invalid_decision_review_request(
    client,
    db_session: Session,
    operation: str,
    invalid_case: str,
) -> None:
    decision = create_reviewable_decision(
        db_session,
    )
    selected_alternative = db_session.scalar(
        select(DecisionAlternative).where(
            DecisionAlternative.decision_id == decision.id,
            DecisionAlternative.position == 0,
        )
    )

    assert selected_alternative is not None

    submit_response = client.post(
        f"/decisions/{decision.id}/submit",
    )

    assert submit_response.status_code == 200

    if operation == "decide":
        payload: dict[str, object] = {
            "selected_alternative_id": str(
                selected_alternative.id,
            ),
            "rationale": (
                "This alternative provides the strongest engineering outcome."
            ),
        }
    else:
        payload = {
            "rationale": ("The project requirements changed before final approval."),
        }

    if invalid_case == "blank_rationale":
        payload["rationale"] = "   "

    elif invalid_case == "null_rationale":
        payload["rationale"] = None

    elif invalid_case == "missing_alternative":
        payload.pop(
            "selected_alternative_id",
        )

    else:
        payload["unexpected_field"] = "not allowed"

    response = client.post(
        f"/decisions/{decision.id}/{operation}",
        json=payload,
    )

    assert response.status_code == 422

    db_session.expire_all()

    persisted_decision = db_session.get(
        Decision,
        decision.id,
    )

    assert persisted_decision is not None
    assert persisted_decision.status == "in_review"
    assert persisted_decision.selected_alternative_id is None
    assert persisted_decision.rationale is None
    assert persisted_decision.decided_at is None
    assert persisted_decision.cancelled_at is None


def test_cancels_draft_decision(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    decision = Decision(
        title="Cooling pressure limit",
        question=("Should the maximum cooling-system pressure be reduced?"),
    )
    db_session.add(decision)
    db_session.flush()

    cancelled_at = datetime(
        2026,
        8,
        28,
        17,
        0,
        tzinfo=timezone.utc,
    )

    monkeypatch.setattr(
        decision_review_service,
        "utc_now",
        lambda: cancelled_at,
    )

    rationale = "The decision is no longer required because the project scope changed."
    response = client.post(
        f"/decisions/{decision.id}/cancel",
        json={
            "rationale": rationale,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "cancelled"
    assert body["rationale"] == rationale
    assert body["submitted_at"] is None
    assert body["decided_at"] is None
    assert body["cancelled_at"] is not None
    assert body["superseded_at"] is None
    assert body["selected_alternative_id"] is None

    db_session.expire_all()

    persisted_decision = db_session.get(
        Decision,
        decision.id,
    )

    assert persisted_decision is not None
    assert persisted_decision.status == "cancelled"
    assert persisted_decision.rationale == rationale
    assert persisted_decision.submitted_at is None
    assert persisted_decision.decided_at is None
    assert persisted_decision.cancelled_at == cancelled_at
    assert persisted_decision.superseded_at is None


def test_keeps_decision_context_readable_after_submission(
    client,
    db_session: Session,
) -> None:
    decision = create_reviewable_decision(
        db_session,
    )
    evidence = db_session.scalar(
        select(DecisionEvidence)
        .join(
            DecisionAlternative,
            DecisionAlternative.id == DecisionEvidence.decision_alternative_id,
        )
        .where(
            DecisionAlternative.decision_id == decision.id,
        )
    )

    assert evidence is not None

    submit_response = client.post(
        f"/decisions/{decision.id}/submit",
    )

    assert submit_response.status_code == 200

    alternatives_response = client.get(
        f"/decisions/{decision.id}/alternatives",
    )
    evidence_response = client.get(
        (
            f"/decisions/{decision.id}"
            f"/alternatives/{evidence.decision_alternative_id}"
            "/evidence"
        ),
    )

    assert alternatives_response.status_code == 200
    assert (
        len(
            alternatives_response.json(),
        )
        == 2
    )

    assert evidence_response.status_code == 200

    evidence_items = evidence_response.json()

    assert len(evidence_items) == 1
    assert evidence_items[0]["id"] == str(
        evidence.id,
    )
    assert evidence_items[0]["document_chunk_id"] == str(
        evidence.document_chunk_id,
    )
