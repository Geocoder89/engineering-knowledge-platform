from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.database import engine
from app.models.decision import Decision
from app.models.decision_alternative import DecisionAlternative
from app.repositories import (
    decision_alternative as decision_alternative_repository,
)


def test_database_persists_decision_alternative() -> None:
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

            alternative = DecisionAlternative(
                decision_id=decision.id,
                title="Reduce the pressure limit",
                description=(
                    "Lower the approved maximum pressure to improve the safety margin."
                ),
                position=0,
            )
            session.add(alternative)
            session.flush()

            assert alternative.id is not None
            assert alternative.decision_id == decision.id
            assert alternative.title == "Reduce the pressure limit"
            assert alternative.description == (
                "Lower the approved maximum pressure to improve the safety margin."
            )
            assert alternative.position == 0
            assert alternative.created_at is not None
            assert alternative.updated_at is not None
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_repository_appends_and_lists_decision_alternatives() -> None:
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

            first_alternative = (
                decision_alternative_repository.create_decision_alternative(
                    session,
                    decision_id=decision.id,
                    title="Keep the existing limit",
                    description=("Retain the currently approved maximum pressure."),
                )
            )
            second_alternative = (
                decision_alternative_repository.create_decision_alternative(
                    session,
                    decision_id=decision.id,
                    title="Reduce the pressure limit",
                    description=(
                        "Lower the maximum pressure to increase the safety margin."
                    ),
                )
            )

            alternatives = decision_alternative_repository.list_decision_alternatives(
                session,
                decision_id=decision.id,
            )

            assert first_alternative.position == 0
            assert second_alternative.position == 1
            assert [alternative.id for alternative in alternatives] == [
                first_alternative.id,
                second_alternative.id,
            ]
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


def test_adds_alternative_to_decision(client) -> None:
    decision_response = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert decision_response.status_code == 201

    decision = decision_response.json()
    payload = {
        "title": "Reduce the pressure limit",
        "description": (
            "Lower the approved maximum pressure to improve the safety margin."
        ),
    }

    response = client.post(
        (f"/decisions/{decision['id']}/alternatives"),
        json=payload,
    )

    body = response.json()

    assert response.status_code == 201
    assert body["decision_id"] == decision["id"]
    assert body["title"] == payload["title"]
    assert body["description"] == payload["description"]
    assert body["position"] == 0
    assert (
        datetime.fromisoformat(
            body["created_at"],
        ).tzinfo
        is not None
    )
    assert (
        datetime.fromisoformat(
            body["updated_at"],
        ).tzinfo
        is not None
    )

    UUID(body["id"])


def test_lists_decision_alternatives_in_position_order(
    client,
) -> None:
    decision_response = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert decision_response.status_code == 201

    decision = decision_response.json()
    created_alternatives = []

    for payload in (
        {
            "title": "Keep the existing limit",
            "description": ("Retain the currently approved maximum pressure."),
        },
        {
            "title": "Reduce the pressure limit",
            "description": (
                "Lower the maximum pressure to increase the safety margin."
            ),
        },
    ):
        response = client.post(
            (f"/decisions/{decision['id']}/alternatives"),
            json=payload,
        )

        assert response.status_code == 201
        created_alternatives.append(
            response.json(),
        )

    response = client.get(
        (f"/decisions/{decision['id']}/alternatives"),
    )

    assert response.status_code == 200

    alternatives = response.json()

    assert [alternative["id"] for alternative in alternatives] == [
        alternative["id"] for alternative in created_alternatives
    ]
    assert [alternative["position"] for alternative in alternatives] == [0, 1]


def test_updates_decision_alternative(client) -> None:
    decision_response = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert decision_response.status_code == 201

    decision = decision_response.json()

    create_response = client.post(
        (f"/decisions/{decision['id']}/alternatives"),
        json={
            "title": "Reduce the pressure limit",
            "description": (
                "Lower the approved maximum pressure to improve the safety margin."
            ),
        },
    )

    assert create_response.status_code == 201

    created_alternative = create_response.json()

    response = client.patch(
        (f"/decisions/{decision['id']}/alternatives/{created_alternative['id']}"),
        json={
            "title": ("Reduce the maximum operating pressure"),
        },
    )

    assert response.status_code == 200

    updated_alternative = response.json()

    assert updated_alternative["id"] == created_alternative["id"]
    assert updated_alternative["title"] == ("Reduce the maximum operating pressure")
    assert updated_alternative["description"] == (created_alternative["description"])
    assert updated_alternative["position"] == 0


def test_deletes_and_compacts_alternative_positions(
    client,
) -> None:
    decision_response = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert decision_response.status_code == 201

    decision = decision_response.json()
    created_alternatives = []

    for title in (
        "Keep the existing limit",
        "Reduce the pressure limit",
        "Replace the pressure system",
    ):
        response = client.post(
            (f"/decisions/{decision['id']}/alternatives"),
            json={
                "title": title,
                "description": (
                    f"Evaluate whether to {title.lower()} for the final design."
                ),
            },
        )

        assert response.status_code == 201
        created_alternatives.append(
            response.json(),
        )

    removed_alternative = created_alternatives[1]

    delete_response = client.delete(
        (f"/decisions/{decision['id']}/alternatives/{removed_alternative['id']}"),
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""

    list_response = client.get(
        (f"/decisions/{decision['id']}/alternatives"),
    )

    assert list_response.status_code == 200

    remaining_alternatives = list_response.json()

    assert [alternative["id"] for alternative in remaining_alternatives] == [
        created_alternatives[0]["id"],
        created_alternatives[2]["id"],
    ]
    assert [alternative["position"] for alternative in remaining_alternatives] == [0, 1]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "title": "   ",
            "description": ("Retain the currently approved maximum pressure."),
        },
        {
            "title": "Keep the existing limit",
            "description": "   ",
        },
        {
            "title": "Keep the existing limit",
            "description": ("Retain the currently approved maximum pressure."),
            "position": 10,
        },
    ],
)
def test_rejects_invalid_decision_alternative_creation(
    client,
    payload: dict[str, object],
) -> None:
    decision_response = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert decision_response.status_code == 201

    decision = decision_response.json()

    response = client.post(
        f"/decisions/{decision['id']}/alternatives",
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "title": None,
        },
        {
            "description": "short",
        },
        {
            "position": 2,
        },
    ],
)
def test_rejects_invalid_decision_alternative_update(
    client,
    payload: dict[str, object],
) -> None:
    decision_response = client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": ("Should the maximum cooling-system pressure be reduced?"),
        },
    )

    assert decision_response.status_code == 201

    decision = decision_response.json()

    alternative_response = client.post(
        f"/decisions/{decision['id']}/alternatives",
        json={
            "title": "Keep the existing limit",
            "description": ("Retain the currently approved maximum pressure."),
        },
    )

    assert alternative_response.status_code == 201

    alternative = alternative_response.json()

    response = client.patch(
        (f"/decisions/{decision['id']}/alternatives/{alternative['id']}"),
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "method",
    [
        "patch",
        "delete",
    ],
)
def test_cannot_modify_alternative_through_another_decision(
    client,
    method: str,
) -> None:
    decisions = []

    for title in (
        "Cooling pressure limit",
        "Electrical cable selection",
    ):
        response = client.post(
            "/decisions",
            json={
                "title": title,
                "question": (f"Which outcome should be selected for {title.lower()}?"),
            },
        )

        assert response.status_code == 201
        decisions.append(response.json())

    alternative_response = client.post(
        f"/decisions/{decisions[0]['id']}/alternatives",
        json={
            "title": "Keep the existing design",
            "description": ("Retain the currently approved engineering design."),
        },
    )

    assert alternative_response.status_code == 201

    alternative = alternative_response.json()
    url = f"/decisions/{decisions[1]['id']}/alternatives/{alternative['id']}"

    if method == "patch":
        response = client.patch(
            url,
            json={
                "title": "Changed through another decision",
            },
        )
    else:
        response = client.delete(url)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Decision alternative not found",
    }
