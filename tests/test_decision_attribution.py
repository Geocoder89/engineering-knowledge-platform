import pytest
from sqlalchemy.orm import Session

from app.models.decision import Decision


def test_creating_decision_returns_creator_attribution(
    authenticated_client,
    authenticated_user,
) -> None:
    response = authenticated_client.post(
        "/decisions",
        json={
            "title": "Cooling pressure limit",
            "question": "Should the maximum cooling-system pressure be reduced?",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["created_by_user_id"] == str(authenticated_user.user.id)
    assert body["decided_by_user_id"] is None

    record_response = authenticated_client.get(
        f"/decisions/{body['id']}/record",
    )

    assert record_response.status_code == 200

    record = record_response.json()
    assert record["created_by_user_id"] == str(authenticated_user.user.id)
    assert record["decided_by_user_id"] is None


@pytest.mark.parametrize("suffix", ["", "/record"])
def test_historical_decision_returns_null_attribution(
    authenticated_client,
    authenticated_user,
    db_session: Session,
    suffix: str,
) -> None:
    decision = Decision(
        owner_user_id=authenticated_user.user.id,
        created_by_user_id=None,
        decided_by_user_id=None,
        title="Historical decision",
        question="Should the operating pressure be reduced?",
    )
    db_session.add(decision)
    db_session.flush()

    response = authenticated_client.get(
        f"/decisions/{decision.id}{suffix}",
    )

    assert response.status_code == 200

    body = response.json()
    assert body["created_by_user_id"] is None
    assert body["decided_by_user_id"] is None
