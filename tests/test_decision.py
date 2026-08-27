from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.database import engine
from app.models.decision import Decision
from app.repositories import decision as decision_repository


def test_database_persists_draft_decision() -> None:
    connection = engine.connect()
    outer_transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            decision = Decision(
                title="Cooling pressure limit",
                question=("Should the maximum cooling-system pressure be reduced?"),
            )
            session.add(decision)
            session.flush()

            decision_id = decision.id
            session.expunge_all()

            persisted_decision = session.get(
                Decision,
                decision_id,
            )

            assert persisted_decision is not None
            assert persisted_decision.id == decision_id
            assert persisted_decision.title == "Cooling pressure limit"
            assert persisted_decision.question == (
                "Should the maximum cooling-system pressure be reduced?"
            )
            assert persisted_decision.status == "draft"
            assert persisted_decision.created_at is not None
            assert persisted_decision.updated_at is not None
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_repository_creates_and_retrieves_decision() -> None:
    connection = engine.connect()
    outer_transaction = connection.begin()

    try:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            created_decision = decision_repository.create_decision(
                session,
                title="Cooling pressure limit",
                question=("Should the maximum cooling-system pressure be reduced?"),
            )
            decision_id = created_decision.id

            session.expunge_all()

            retrieved_decision = decision_repository.get_decision_by_id(
                session,
                decision_id,
            )

            assert retrieved_decision is not None
            assert retrieved_decision.id == decision_id
            assert retrieved_decision.title == "Cooling pressure limit"
            assert retrieved_decision.question == (
                "Should the maximum cooling-system pressure be reduced?"
            )
            assert retrieved_decision.status == "draft"
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_creates_draft_decision(client) -> None:
    payload = {
        "title": "Cooling pressure limit",
        "question": ("Should the maximum cooling-system pressure be reduced?"),
    }

    response = client.post(
        "/decisions",
        json=payload,
    )

    body = response.json()

    assert response.status_code == 201
    assert response.history == []
    assert body["title"] == payload["title"]
    assert body["question"] == payload["question"]
    assert body["status"] == "draft"
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None
    assert datetime.fromisoformat(body["updated_at"]).tzinfo is not None

    UUID(body["id"])


def test_retrieves_created_decision(client) -> None:
    payload = {
        "title": "Cooling pressure limit",
        "question": ("Should the maximum cooling-system pressure be reduced?"),
    }

    create_response = client.post(
        "/decisions",
        json=payload,
    )

    assert create_response.status_code == 201

    created_decision = create_response.json()

    response = client.get(
        f"/decisions/{created_decision['id']}",
    )

    assert response.status_code == 200
    assert response.json() == created_decision


def test_returns_404_for_unknown_decision(client) -> None:
    unknown_id = uuid4()

    response = client.get(
        f"/decisions/{unknown_id}",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision not found",
    }


def test_rejects_malformed_decision_id(client) -> None:
    response = client.get(
        "/decisions/not-a-valid-uuid",
    )

    assert response.status_code == 422


def test_lists_decisions_with_pagination(client) -> None:
    payloads = [
        {
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
        {
            "title": "Electrical cable selection",
            "question": (
                "Which electrical cable specification should the project adopt?"
            ),
        },
        {
            "title": "Hydraulic pump capacity",
            "question": (
                "What hydraulic pump capacity should be used for the final design?"
            ),
        },
    ]

    created_ids = set()

    for payload in payloads:
        response = client.post(
            "/decisions",
            json=payload,
        )

        assert response.status_code == 201
        created_ids.add(response.json()["id"])

    first_response = client.get(
        "/decisions?offset=0&limit=2",
    )

    assert first_response.status_code == 200

    first_page = first_response.json()

    assert first_page["total"] == 3
    assert first_page["offset"] == 0
    assert first_page["limit"] == 2
    assert len(first_page["items"]) == 2

    second_response = client.get(
        "/decisions?offset=2&limit=2",
    )

    assert second_response.status_code == 200

    second_page = second_response.json()

    assert second_page["total"] == 3
    assert second_page["offset"] == 2
    assert second_page["limit"] == 2
    assert len(second_page["items"]) == 1

    returned_ids = {
        decision["id"] for decision in (first_page["items"] + second_page["items"])
    }

    assert returned_ids == created_ids


@pytest.mark.parametrize(
    "payload",
    [
        {
            "title": "   ",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
        {
            "title": "Cooling pressure limit",
            "question": "          ",
        },
        {
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
            "status": "decided",
        },
    ],
)
def test_rejects_invalid_decision_creation(
    client,
    payload: dict[str, str],
) -> None:
    response = client.post(
        "/decisions",
        json=payload,
    )

    assert response.status_code == 422


def test_rejects_invalid_decision_pagination(client) -> None:
    response = client.get(
        "/decisions?offset=-1&limit=0",
    )

    assert response.status_code == 422
