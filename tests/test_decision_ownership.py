from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.models.decision_alternative import DecisionAlternative
from app.models.decision_evidence import DecisionEvidence
from app.models.user import User
from app.repositories import decision as decision_repository
from app.services.authentication import AuthenticatedUser


def test_authenticated_user_owns_created_decision(
    authenticated_client: TestClient,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = authenticated_client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert response.status_code == 201

    response_body = response.json()
    persisted_decision = db_session.get(
        Decision,
        UUID(response_body["id"]),
    )

    assert persisted_decision is not None
    assert persisted_decision.owner_user_id == authenticated_user.user.id
    assert "owner_user_id" not in response_body


def test_decision_creation_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required",
    }


def test_decision_list_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/decisions",
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required",
    }


def test_decision_list_contains_only_authenticated_users_decisions(
    authenticated_client: TestClient,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    owner_first_decision = decision_repository.create_decision(
        db_session,
        owner_user_id=authenticated_user.user.id,
        title="Owner first decision",
        question="What should the owner choose first?",
    )

    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    decision_repository.create_decision(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's decision",
        question="What should the other user choose?",
    )

    owner_second_decision = decision_repository.create_decision(
        db_session,
        owner_user_id=authenticated_user.user.id,
        title="Owner second decision",
        question="What should the owner choose second?",
    )

    response = authenticated_client.get(
        "/decisions",
    )

    assert response.status_code == 200

    response_body = response.json()

    assert response_body["total"] == 2
    assert {decision["id"] for decision in response_body["items"]} == {
        str(owner_first_decision.id),
        str(owner_second_decision.id),
    }


def test_decision_detail_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        f"/decisions/{uuid4()}",
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required",
    }


def test_authenticated_user_can_retrieve_owned_decision(
    authenticated_client: TestClient,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    decision = decision_repository.create_decision(
        db_session,
        owner_user_id=authenticated_user.user.id,
        title="Cooling pressure limit",
        question="Should the maximum cooling-system pressure be reduced?",
    )

    response = authenticated_client.get(
        f"/decisions/{decision.id}",
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(decision.id)
    assert response.json()["title"] == decision.title


def test_other_users_decision_is_not_found(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_users_decision = decision_repository.create_decision(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's decision",
        question="What should the other user choose?",
    )

    response = authenticated_client.get(
        f"/decisions/{other_users_decision.id}",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }


def test_other_users_decision_cannot_receive_alternative(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_users_decision = decision_repository.create_decision(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's decision",
        question="What should the other user choose?",
    )

    response = authenticated_client.post(
        f"/decisions/{other_users_decision.id}/alternatives",
        json={
            "title": "Unauthorized alternative",
            "description": "This must not be added to another user's decision.",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }

    alternatives = list(
        db_session.scalars(
            select(DecisionAlternative).where(
                DecisionAlternative.decision_id == other_users_decision.id,
            )
        )
    )

    assert alternatives == []


def test_other_users_decision_alternative_cannot_be_updated(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_users_decision = decision_repository.create_decision(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's decision",
        question="What should the other user choose?",
    )
    original_title = "Original alternative"
    alternative = DecisionAlternative(
        decision_id=other_users_decision.id,
        title=original_title,
        description="The original description.",
        position=0,
    )
    db_session.add(alternative)
    db_session.flush()

    response = authenticated_client.patch(
        (f"/decisions/{other_users_decision.id}/alternatives/{alternative.id}"),
        json={
            "title": "Unauthorized alternative update",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }

    db_session.expire_all()

    persisted_alternative = db_session.get(
        DecisionAlternative,
        alternative.id,
    )

    assert persisted_alternative is not None
    assert persisted_alternative.title == original_title


def test_other_users_decision_alternative_cannot_be_deleted(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_users_decision = decision_repository.create_decision(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's decision",
        question="What should the other user choose?",
    )
    alternative = DecisionAlternative(
        decision_id=other_users_decision.id,
        title="Protected alternative",
        description="This alternative must not be deleted.",
        position=0,
    )
    db_session.add(alternative)
    db_session.flush()

    alternative_id = alternative.id

    response = authenticated_client.delete(
        (f"/decisions/{other_users_decision.id}/alternatives/{alternative_id}"),
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }

    db_session.expire_all()

    assert db_session.get(DecisionAlternative, alternative_id) is not None


def test_other_users_decision_cannot_receive_evidence(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_users_decision = decision_repository.create_decision(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's decision",
        question="What should the other user choose?",
    )
    alternative = DecisionAlternative(
        decision_id=other_users_decision.id,
        title="Protected alternative",
        description="Evidence must not be added by another user.",
        position=0,
    )
    db_session.add(alternative)
    db_session.flush()

    response = authenticated_client.post(
        (
            f"/decisions/{other_users_decision.id}"
            f"/alternatives/{alternative.id}/evidence"
        ),
        json={
            "document_chunk_id": str(uuid4()),
            "evidence_type": "supporting",
            "relevance_note": "This evidence must not be created.",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }

    evidence = list(
        db_session.scalars(
            select(DecisionEvidence).where(
                DecisionEvidence.decision_alternative_id == alternative.id,
            )
        )
    )

    assert evidence == []


def test_other_users_decision_evidence_cannot_be_deleted(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_users_decision = decision_repository.create_decision(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's decision",
        question="What should the other user choose?",
    )
    alternative = DecisionAlternative(
        decision_id=other_users_decision.id,
        title="Protected alternative",
        description="Its evidence must not be deleted by another user.",
        position=0,
    )
    db_session.add(alternative)
    db_session.flush()

    response = authenticated_client.delete(
        (
            f"/decisions/{other_users_decision.id}"
            f"/alternatives/{alternative.id}"
            f"/evidence/{uuid4()}"
        ),
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }


def test_other_users_decision_cannot_be_submitted_for_review(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_users_decision = decision_repository.create_decision(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's decision",
        question="What should the other user choose?",
    )
    decision_id = other_users_decision.id

    response = authenticated_client.post(
        f"/decisions/{decision_id}/submit",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }

    db_session.expire_all()

    persisted_decision = db_session.get(
        Decision,
        decision_id,
    )

    assert persisted_decision is not None
    assert persisted_decision.status == "draft"
    assert persisted_decision.submitted_at is None


def test_other_users_decision_cannot_be_finalized(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_users_decision = decision_repository.create_decision(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's decision",
        question="What should the other user choose?",
    )
    alternative = DecisionAlternative(
        decision_id=other_users_decision.id,
        title="Protected alternative",
        description="This must not be selected by another user.",
        position=0,
    )
    db_session.add(alternative)
    db_session.flush()

    decision_id = other_users_decision.id

    response = authenticated_client.post(
        f"/decisions/{decision_id}/decide",
        json={
            "selected_alternative_id": str(alternative.id),
            "rationale": "This unauthorized outcome must not be recorded.",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }

    db_session.expire_all()

    persisted_decision = db_session.get(
        Decision,
        decision_id,
    )

    assert persisted_decision is not None
    assert persisted_decision.status == "draft"
    assert persisted_decision.selected_alternative_id is None
    assert persisted_decision.rationale is None
    assert persisted_decision.decided_at is None


def test_other_users_decision_cannot_be_cancelled(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_users_decision = decision_repository.create_decision(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's decision",
        question="What should the other user choose?",
    )
    decision_id = other_users_decision.id

    response = authenticated_client.post(
        f"/decisions/{decision_id}/cancel",
        json={
            "rationale": "This unauthorized cancellation must not be recorded.",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }

    db_session.expire_all()

    persisted_decision = db_session.get(
        Decision,
        decision_id,
    )

    assert persisted_decision is not None
    assert persisted_decision.status == "draft"
    assert persisted_decision.rationale is None
    assert persisted_decision.cancelled_at is None


@pytest.mark.parametrize(
    (
        "method",
        "path",
        "payload",
    ),
    [
        (
            "POST",
            f"/decisions/{uuid4()}/alternatives",
            {
                "title": "Unauthorized alternative",
                "description": "Authentication is required.",
            },
        ),
        (
            "PATCH",
            f"/decisions/{uuid4()}/alternatives/{uuid4()}",
            {
                "title": "Unauthorized update",
            },
        ),
        (
            "DELETE",
            f"/decisions/{uuid4()}/alternatives/{uuid4()}",
            None,
        ),
        (
            "POST",
            f"/decisions/{uuid4()}/alternatives/{uuid4()}/evidence",
            {
                "document_chunk_id": str(uuid4()),
                "evidence_type": "supporting",
            },
        ),
        (
            "DELETE",
            (f"/decisions/{uuid4()}/alternatives/{uuid4()}/evidence/{uuid4()}"),
            None,
        ),
        (
            "POST",
            f"/decisions/{uuid4()}/submit",
            None,
        ),
        (
            "POST",
            f"/decisions/{uuid4()}/decide",
            {
                "selected_alternative_id": str(uuid4()),
                "rationale": "Authentication is required.",
            },
        ),
        (
            "POST",
            f"/decisions/{uuid4()}/cancel",
            {
                "rationale": "Authentication is required.",
            },
        ),
    ],
)
def test_decision_mutations_require_authentication(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, str] | None,
) -> None:
    response = client.request(
        method,
        path,
        json=payload,
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required",
    }
