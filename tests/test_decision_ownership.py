from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.decision import Decision
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
