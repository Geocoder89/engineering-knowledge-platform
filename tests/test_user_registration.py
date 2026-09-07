import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.user import UserStatus
from app.models.user import User
from app.models.user_password_credential import UserPasswordCredential
from app.repositories import user as user_repository
from app.repositories import (
    user_password_credential as user_password_credential_repository,
)
from app.security.password import verify_password
from app.services import user_registration as user_registration_service


def test_service_registers_user_with_password_credential(
    db_session: Session,
) -> None:
    password = "correct horse battery staple"

    registration = user_registration_service.register_user(
        db_session,
        email="  Engineer@Example.COM  ",
        display_name="  Engineering Reviewer  ",
        password=password,
    )

    registered_user = registration.user

    assert registered_user.email == "engineer@example.com"
    assert registered_user.display_name == "Engineering Reviewer"
    assert registered_user.status == UserStatus.ACTIVE.value

    persisted_user = user_repository.get_user_by_email(
        db_session,
        email="engineer@example.com",
    )

    assert persisted_user is not None
    assert persisted_user.id == registered_user.id

    credential = user_password_credential_repository.get_user_password_credential(
        db_session,
        user_id=registered_user.id,
    )

    assert credential is not None
    assert credential.password_hash != password
    assert verify_password(
        password=password,
        password_hash=credential.password_hash,
    )


def test_service_rejects_duplicate_email_without_changing_existing_password(
    db_session: Session,
) -> None:
    original_password = "correct horse battery staple"
    replacement_password = "a completely different password"

    existing_registration = user_registration_service.register_user(
        db_session,
        email="engineer@example.com",
        display_name="Engineering Reviewer",
        password=original_password,
    )
    existing_user = existing_registration.user

    with pytest.raises(
        user_registration_service.UserAlreadyExistsError,
        match="User registration could not be completed",
    ):
        user_registration_service.register_user(
            db_session,
            email="  Engineer@Example.COM  ",
            display_name="Another Person",
            password=replacement_password,
        )

    persisted_user = user_repository.get_user_by_email(
        db_session,
        email="engineer@example.com",
    )

    assert persisted_user is not None
    assert persisted_user.id == existing_user.id
    assert persisted_user.display_name == "Engineering Reviewer"

    credential = user_password_credential_repository.get_user_password_credential(
        db_session,
        user_id=existing_user.id,
    )

    assert credential is not None
    assert verify_password(
        password=original_password,
        password_hash=credential.password_hash,
    )
    assert not verify_password(
        password=replacement_password,
        password_hash=credential.password_hash,
    )


def test_registers_user_with_password_credential(
    client: TestClient,
    db_session: Session,
) -> None:
    password = "correct horse battery staple"

    response = client.post(
        "/auth/register",
        json={
            "email": "  Engineer@Example.COM  ",
            "display_name": "  Engineering Reviewer  ",
            "password": password,
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "email": "engineer@example.com",
        "display_name": "Engineering Reviewer",
        "status": UserStatus.ACTIVE.value,
    }
    assert "set-cookie" not in response.headers

    registered_user = user_repository.get_user_by_email(
        db_session,
        email="engineer@example.com",
    )

    assert registered_user is not None
    assert str(registered_user.id) == response.json()["id"]

    credential = user_password_credential_repository.get_user_password_credential(
        db_session,
        user_id=registered_user.id,
    )

    assert credential is not None
    assert verify_password(
        password=password,
        password_hash=credential.password_hash,
    )


def test_rejects_duplicate_registration_without_changing_existing_account(
    client: TestClient,
    db_session: Session,
) -> None:
    original_password = "correct horse battery staple"
    replacement_password = "a completely different password"

    first_response = client.post(
        "/auth/register",
        json={
            "email": "engineer@example.com",
            "display_name": "Engineering Reviewer",
            "password": original_password,
        },
    )

    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/auth/register",
        json={
            "email": "  Engineer@Example.COM  ",
            "display_name": "Another Person",
            "password": replacement_password,
        },
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "User registration could not be completed",
    }
    assert "set-cookie" not in duplicate_response.headers

    persisted_user = user_repository.get_user_by_email(
        db_session,
        email="engineer@example.com",
    )

    assert persisted_user is not None
    assert persisted_user.display_name == "Engineering Reviewer"

    credential = user_password_credential_repository.get_user_password_credential(
        db_session,
        user_id=persisted_user.id,
    )

    assert credential is not None
    assert verify_password(
        password=original_password,
        password_hash=credential.password_hash,
    )
    assert not verify_password(
        password=replacement_password,
        password_hash=credential.password_hash,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "email": "   ",
            "display_name": "Engineering Reviewer",
            "password": "correct horse battery staple",
        },
        {
            "email": "engineer@example.com",
            "display_name": "   ",
            "password": "correct horse battery staple",
        },
        {
            "email": "engineer@example.com",
            "display_name": "Engineering Reviewer",
            "password": "too-short",
        },
        {
            "email": "engineer@example.com",
            "display_name": "Engineering Reviewer",
            "password": "            ",
        },
        {
            "email": "engineer@example.com",
            "display_name": "Engineering Reviewer",
            "password": "correct horse battery staple",
            "role": "administrator",
        },
    ],
)
def test_rejects_invalid_registration_without_persisting_identity(
    client: TestClient,
    db_session: Session,
    payload: dict[str, object],
) -> None:
    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 422

    user_count = db_session.scalar(
        select(func.count()).select_from(User),
    )
    credential_count = db_session.scalar(
        select(func.count()).select_from(UserPasswordCredential),
    )

    assert user_count == 0
    assert credential_count == 0


def test_service_handles_duplicate_email_created_during_registration(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_password = "correct horse battery staple"
    replacement_password = "a completely different password"

    existing_registration = user_registration_service.register_user(
        db_session,
        email="engineer@example.com",
        display_name="Engineering Reviewer",
        password=original_password,
    )

    existing_user = existing_registration.user

    monkeypatch.setattr(
        user_registration_service.user_repository,
        "get_user_by_email",
        lambda session, *, email: None,
    )

    with pytest.raises(
        user_registration_service.UserAlreadyExistsError,
        match="User registration could not be completed",
    ):
        user_registration_service.register_user(
            db_session,
            email="engineer@example.com",
            display_name="Another Person",
            password=replacement_password,
        )

    persisted_user = db_session.get(
        User,
        existing_user.id,
    )

    assert persisted_user is not None
    assert persisted_user.display_name == "Engineering Reviewer"

    credential = user_password_credential_repository.get_user_password_credential(
        db_session,
        user_id=existing_user.id,
    )

    assert credential is not None
    assert verify_password(
        password=original_password,
        password_hash=credential.password_hash,
    )
    assert not verify_password(
        password=replacement_password,
        password_hash=credential.password_hash,
    )


def test_service_rolls_back_user_when_password_credential_creation_fails(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_set_password(
        *args: object,
        **kwargs: object,
    ) -> None:
        raise RuntimeError(
            "Credential storage failed",
        )

    monkeypatch.setattr(
        user_registration_service.user_password_service,
        "set_user_password",
        fail_to_set_password,
    )

    with pytest.raises(
        RuntimeError,
        match="Credential storage failed",
    ):
        user_registration_service.register_user(
            db_session,
            email="engineer@example.com",
            display_name="Engineering Reviewer",
            password="correct horse battery staple",
        )

    persisted_user = user_repository.get_user_by_email(
        db_session,
        email="engineer@example.com",
    )
    credential_count = db_session.scalar(
        select(func.count()).select_from(UserPasswordCredential),
    )

    assert persisted_user is None
    assert credential_count == 0


def test_registered_user_cannot_log_in_before_email_verification(
    client: TestClient,
) -> None:
    password = "correct horse battery staple"

    registration_response = client.post(
        "/auth/register",
        json={
            "email": "engineer@example.com",
            "display_name": "Engineering Reviewer",
            "password": password,
        },
    )

    assert registration_response.status_code == 201
    assert client.cookies.get("decision_session") is None

    login_response = client.post(
        "/auth/login",
        json={
            "email": "  Engineer@Example.COM  ",
            "password": password,
        },
    )

    assert login_response.status_code == 401
    assert login_response.json() == {
        "detail": "Invalid email or password",
    }
    assert client.cookies.get("decision_session") is None
