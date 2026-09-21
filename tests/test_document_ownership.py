from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.user import User
from app.repositories.document import create_document
from app.services.authentication import AuthenticatedUser


def test_document_creation_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required",
    }


def test_authenticated_user_owns_created_document(
    authenticated_client: TestClient,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = authenticated_client.post(
        "/documents",
        json={
            "title": "Cooling system",
            "file_name": "cooling-design.pdf",
        },
    )

    assert response.status_code == 201

    document_id = UUID(
        response.json()["id"],
    )

    db_session.expire_all()

    stored_document = db_session.get(
        Document,
        document_id,
    )

    assert stored_document is not None
    assert stored_document.owner_user_id == authenticated_user.user.id


def test_document_list_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/documents",
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required",
    }


def test_document_list_contains_only_authenticated_users_documents(
    authenticated_client: TestClient,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_document = create_document(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's document",
        file_name="other-document.pdf",
    )

    own_document_response = authenticated_client.post(
        "/documents",
        json={
            "title": "Owned document",
            "file_name": "owned-document.pdf",
        },
    )

    assert own_document_response.status_code == 201

    response = authenticated_client.get(
        "/documents",
    )

    assert response.status_code == 200

    response_body = response.json()
    returned_document_ids = {item["id"] for item in response_body["items"]}

    assert response_body["total"] == 1
    assert returned_document_ids == {
        own_document_response.json()["id"],
    }
    assert str(other_document.id) not in returned_document_ids
    assert all(item["id"] != str(other_document.id) for item in response_body["items"])
    assert authenticated_user.user.id != other_user.id


def test_document_detail_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        f"/documents/{uuid4()}",
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required",
    }


def test_authenticated_user_can_retrieve_owned_document(
    authenticated_client: TestClient,
) -> None:
    create_response = authenticated_client.post(
        "/documents",
        json={
            "title": "Owned document",
            "file_name": "owned-document.pdf",
        },
    )

    assert create_response.status_code == 201

    response = authenticated_client.get(
        f"/documents/{create_response.json()['id']}",
    )

    assert response.status_code == 200
    assert response.json()["id"] == create_response.json()["id"]


def test_other_users_document_is_not_found(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_document = create_document(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's document",
        file_name="other-document.pdf",
    )

    response = authenticated_client.get(
        f"/documents/{other_document.id}",
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found",
    }


@pytest.mark.parametrize(
    ("path_suffix", "payload"),
    [
        (
            "",
            {
                "title": "Changed title",
            },
        ),
        (
            "/status",
            {
                "status": "processing",
            },
        ),
    ],
)
def test_other_users_document_cannot_be_modified(
    authenticated_client: TestClient,
    db_session: Session,
    path_suffix: str,
    payload: dict[str, str],
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_document = create_document(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's document",
        file_name="other-document.pdf",
    )
    original_title = other_document.title
    original_status = other_document.status

    response = authenticated_client.patch(
        f"/documents/{other_document.id}{path_suffix}",
        json=payload,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found",
    }

    db_session.expire_all()

    unchanged_document = db_session.get(
        Document,
        other_document.id,
    )

    assert unchanged_document is not None
    assert unchanged_document.title == original_title
    assert unchanged_document.status == original_status


@pytest.mark.parametrize(
    ("method", "path_suffix", "request_kwargs"),
    [
        (
            "GET",
            "/versions",
            {},
        ),
        (
            "POST",
            "/versions",
            {
                "files": {
                    "file": (
                        "document.pdf",
                        b"%PDF-1.4\n",
                        "application/pdf",
                    ),
                },
            },
        ),
        (
            "GET",
            "/versions/1",
            {},
        ),
        (
            "POST",
            "/versions/1/retry",
            {},
        ),
        (
            "GET",
            "/versions/1/processing-job",
            {},
        ),
        (
            "GET",
            "/versions/1/content",
            {},
        ),
    ],
)
def test_other_users_nested_document_resources_are_not_found(
    authenticated_client: TestClient,
    db_session: Session,
    method: str,
    path_suffix: str,
    request_kwargs: dict[str, object],
) -> None:
    other_user = User(
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add(other_user)
    db_session.flush()

    other_document = create_document(
        db_session,
        owner_user_id=other_user.id,
        title="Other user's document",
        file_name="other-document.pdf",
    )

    response = authenticated_client.request(
        method,
        f"/documents/{other_document.id}{path_suffix}",
        **request_kwargs,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found",
    }
