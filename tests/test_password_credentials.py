from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.password import (
    InvalidPassword,
    validate_password,
)
from app.models.user import User
from app.models.user_password_credential import (
    UserPasswordCredential,
)
from app.repositories import (
    user_password_credential as user_password_credential_repository,
)
from app.security.password import (
    hash_password,
    verify_password,
)
from app.services import user_password as user_password_service


@pytest.mark.parametrize(
    "password",
    [
        "correct horse battery staple",
        "twelve-chars",
        " leading and trailing spaces ",
    ],
)
def test_accepts_valid_password(
    password: str,
) -> None:
    validate_password(
        password,
    )


@pytest.mark.parametrize(
    (
        "password",
        "expected_message",
    ),
    [
        (
            "",
            "Password cannot be blank",
        ),
        (
            "            ",
            "Password cannot be blank",
        ),
        (
            "too-short",
            "Password must contain at least 12 characters",
        ),
        (
            "x" * 129,
            "Password cannot exceed 128 characters",
        ),
    ],
)
def test_rejects_invalid_password(
    password: str,
    expected_message: str,
) -> None:
    with pytest.raises(
        InvalidPassword,
        match=expected_message,
    ):
        validate_password(
            password,
        )


def test_hashes_and_verifies_password() -> None:
    password = "correct horse battery staple"

    password_hash = hash_password(
        password=password,
    )

    assert password_hash != password
    assert password not in password_hash
    assert password_hash.startswith("$argon2")
    assert verify_password(
        password=password,
        password_hash=password_hash,
    )
    assert not verify_password(
        password="incorrect password",
        password_hash=password_hash,
    )


def test_password_hashing_enforces_password_policy() -> None:
    with pytest.raises(
        InvalidPassword,
        match="Password must contain at least 12 characters",
    ):
        hash_password(
            password="too-short",
        )


def test_database_persists_user_password_credential(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    password = "correct horse battery staple"
    password_hash = hash_password(
        password=password,
    )
    password_changed_at = datetime(
        2026,
        8,
        29,
        20,
        0,
        tzinfo=timezone.utc,
    )
    credential = UserPasswordCredential(
        user_id=user.id,
        password_hash=password_hash,
        password_changed_at=password_changed_at,
    )
    db_session.add(
        credential,
    )
    db_session.flush()
    db_session.expire_all()

    persisted_credential = db_session.get(
        UserPasswordCredential,
        user.id,
    )

    assert persisted_credential is not None
    assert persisted_credential.user_id == user.id
    assert persisted_credential.password_hash == password_hash
    assert persisted_credential.password_hash != password
    assert persisted_credential.password_changed_at == password_changed_at
    assert persisted_credential.created_at is not None
    assert persisted_credential.updated_at is not None


def test_repository_creates_and_retrieves_password_credential(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    password = "correct horse battery staple"
    password_changed_at = datetime(
        2026,
        8,
        29,
        21,
        0,
        tzinfo=timezone.utc,
    )
    credential = user_password_credential_repository.create_user_password_credential(
        db_session,
        user_id=user.id,
        password_hash=hash_password(
            password=password,
        ),
        password_changed_at=password_changed_at,
    )

    persisted_credential = (
        user_password_credential_repository.get_user_password_credential(
            db_session,
            user_id=user.id,
        )
    )

    assert persisted_credential is credential
    assert persisted_credential.password_changed_at == password_changed_at
    assert verify_password(
        password=password,
        password_hash=persisted_credential.password_hash,
    )


def test_repository_returns_none_for_unknown_password_credential(
    db_session: Session,
) -> None:
    credential = user_password_credential_repository.get_user_password_credential(
        db_session,
        user_id=uuid4(),
    )

    assert credential is None


def test_repository_replaces_password_credential(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    original_password = "correct horse battery staple"
    credential = user_password_credential_repository.create_user_password_credential(
        db_session,
        user_id=user.id,
        password_hash=hash_password(
            password=original_password,
        ),
        password_changed_at=datetime(
            2026,
            8,
            29,
            21,
            0,
            tzinfo=timezone.utc,
        ),
    )

    replacement_password = "a completely different secure password"
    replacement_time = datetime(
        2026,
        8,
        29,
        22,
        0,
        tzinfo=timezone.utc,
    )
    replaced_credential = (
        user_password_credential_repository.replace_user_password_credential(
            db_session,
            credential=credential,
            password_hash=hash_password(
                password=replacement_password,
            ),
            password_changed_at=replacement_time,
        )
    )

    assert replaced_credential is credential
    assert replaced_credential.password_changed_at == replacement_time
    assert verify_password(
        password=replacement_password,
        password_hash=replaced_credential.password_hash,
    )
    assert not verify_password(
        password=original_password,
        password_hash=replaced_credential.password_hash,
    )


def test_service_sets_and_replaces_user_password(
    db_session: Session,
    monkeypatch,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    initial_changed_at = datetime(
        2026,
        8,
        29,
        21,
        0,
        tzinfo=timezone.utc,
    )
    replacement_changed_at = datetime(
        2026,
        8,
        29,
        22,
        0,
        tzinfo=timezone.utc,
    )
    timestamps = iter(
        [
            initial_changed_at,
            replacement_changed_at,
        ]
    )
    monkeypatch.setattr(
        user_password_service,
        "utc_now",
        lambda: next(timestamps),
    )

    original_password = "correct horse battery staple"
    credential = user_password_service.set_user_password(
        db_session,
        user=user,
        password=original_password,
    )

    assert credential.password_changed_at == initial_changed_at
    assert credential.password_hash != original_password
    assert verify_password(
        password=original_password,
        password_hash=credential.password_hash,
    )

    replacement_password = "a completely different secure password"
    replaced_credential = user_password_service.set_user_password(
        db_session,
        user=user,
        password=replacement_password,
    )

    assert replaced_credential is credential
    assert replaced_credential.password_changed_at == replacement_changed_at
    assert replacement_password not in replaced_credential.password_hash
    assert verify_password(
        password=replacement_password,
        password_hash=replaced_credential.password_hash,
    )
    assert not verify_password(
        password=original_password,
        password_hash=replaced_credential.password_hash,
    )


def test_database_rejects_non_argon2_password_hash(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    credential = UserPasswordCredential(
        user_id=user.id,
        password_hash="plaintext-password",
        password_changed_at=datetime(
            2026,
            8,
            29,
            23,
            0,
            tzinfo=timezone.utc,
        ),
    )
    db_session.add(
        credential,
    )

    with pytest.raises(
        IntegrityError,
    ):
        db_session.flush()


def test_database_rejects_multiple_password_credentials_for_user(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    user_password_credential_repository.create_user_password_credential(
        db_session,
        user_id=user.id,
        password_hash=hash_password(
            password="correct horse battery staple",
        ),
        password_changed_at=datetime(
            2026,
            8,
            29,
            21,
            0,
            tzinfo=timezone.utc,
        ),
    )

    duplicate_statement = insert(
        UserPasswordCredential,
    ).values(
        user_id=user.id,
        password_hash=hash_password(
            password="another sufficiently secure password",
        ),
        password_changed_at=datetime(
            2026,
            8,
            29,
            22,
            0,
            tzinfo=timezone.utc,
        ),
    )

    with pytest.raises(
        IntegrityError,
    ):
        db_session.execute(
            duplicate_statement,
        )
