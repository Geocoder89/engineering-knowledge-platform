import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.user import (
    InvalidUserEmail,
    UserStatus,
    normalize_user_email,
)
from app.models.user import User
from app.repositories import user as user_repository


@pytest.mark.parametrize(
    (
        "email",
        "expected_email",
    ),
    [
        (
            "engineer@example.com",
            "engineer@example.com",
        ),
        (
            "Engineer@Example.COM",
            "engineer@example.com",
        ),
        (
            "  engineer@example.com  ",
            "engineer@example.com",
        ),
    ],
)
def test_normalizes_user_email(
    email: str,
    expected_email: str,
) -> None:
    assert normalize_user_email(email) == expected_email


@pytest.mark.parametrize(
    "email",
    [
        "",
        " ",
        "   ",
    ],
)
def test_rejects_blank_user_email(
    email: str,
) -> None:
    with pytest.raises(
        InvalidUserEmail,
        match="User email cannot be blank",
    ):
        normalize_user_email(email)


def test_defines_supported_user_statuses() -> None:
    assert {status.value for status in UserStatus} == {
        "active",
        "disabled",
    }


def test_database_persists_active_user_identity(
    db_session: Session,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(user)
    db_session.flush()

    user_id = user.id
    db_session.expunge_all()

    persisted_user = db_session.get(
        User,
        user_id,
    )

    assert persisted_user is not None
    assert persisted_user.id == user_id
    assert persisted_user.email == "engineer@example.com"
    assert persisted_user.display_name == "Engineering Reviewer"
    assert persisted_user.status == "active"
    assert persisted_user.created_at is not None
    assert persisted_user.updated_at is not None


def test_database_rejects_duplicate_user_email(
    db_session: Session,
) -> None:
    first_user = User(
        email="engineer@example.com",
        display_name="First Engineer",
    )
    db_session.add(first_user)
    db_session.flush()

    duplicate_user = User(
        email="engineer@example.com",
        display_name="Second Engineer",
    )
    db_session.add(duplicate_user)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize(
    (
        "email",
        "display_name",
        "status",
    ),
    [
        (
            "Engineer@Example.com",
            "Engineering Reviewer",
            "active",
        ),
        (
            "",
            "Engineering Reviewer",
            "active",
        ),
        (
            "engineer@example.com",
            " ",
            "active",
        ),
        (
            "engineer@example.com",
            "Engineering Reviewer",
            "unknown",
        ),
    ],
)
def test_database_rejects_invalid_user_identity(
    db_session: Session,
    email: str,
    display_name: str,
    status: str,
) -> None:
    user = User(
        email=email,
        display_name=display_name,
        status=status,
    )
    db_session.add(user)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_repository_creates_and_retrieves_normalized_user_identity(
    db_session: Session,
) -> None:
    created_user = user_repository.create_user(
        db_session,
        email="  Engineer@Example.COM  ",
        display_name="Engineering Reviewer",
    )
    user_id = created_user.id

    assert created_user.email == "engineer@example.com"
    assert created_user.display_name == "Engineering Reviewer"
    assert created_user.status == "active"

    db_session.expunge_all()

    retrieved_by_id = user_repository.get_user_by_id(
        db_session,
        user_id,
    )
    retrieved_by_email = user_repository.get_user_by_email(
        db_session,
        email=" ENGINEER@example.com ",
    )

    assert retrieved_by_id is not None
    assert retrieved_by_id.id == user_id
    assert retrieved_by_id.email == "engineer@example.com"

    assert retrieved_by_email is not None
    assert retrieved_by_email.id == user_id


def test_repository_returns_none_for_unknown_user_identity(
    db_session: Session,
) -> None:
    retrieved_user = user_repository.get_user_by_email(
        db_session,
        email="unknown@example.com",
    )

    assert retrieved_user is None


def test_repository_disables_user_without_deleting_identity(
    db_session: Session,
) -> None:
    user = user_repository.create_user(
        db_session,
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    user_id = user.id

    disabled_user = user_repository.set_user_status(
        db_session,
        user=user,
        status=UserStatus.DISABLED,
    )

    assert disabled_user.id == user_id
    assert disabled_user.status == "disabled"

    db_session.expunge_all()

    persisted_user = user_repository.get_user_by_id(
        db_session,
        user_id,
    )

    assert persisted_user is not None
    assert persisted_user.status == "disabled"
