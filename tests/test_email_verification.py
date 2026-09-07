from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.user import UserStatus
from app.models.user import User
from app.models.user_email_verification_token import (
    UserEmailVerificationToken,
)
from app.repositories import (
    user_email_verification_token as email_verification_token_repository,
)
from app.security.email_verification import (
    generate_email_verification_token,
    hash_email_verification_token,
)
from app.services import email_verification as email_verification_service


def test_generates_unique_url_safe_email_verification_tokens() -> None:
    tokens = {generate_email_verification_token() for _ in range(10)}

    assert len(tokens) == 10

    for token in tokens:
        assert token
        assert "=" not in token
        assert "+" not in token
        assert "/" not in token


def test_hashes_email_verification_tokens_deterministically() -> None:
    token = generate_email_verification_token()

    first_hash = hash_email_verification_token(
        token,
    )
    second_hash = hash_email_verification_token(
        token,
    )

    assert first_hash == second_hash
    assert first_hash != token
    assert len(first_hash) == 64
    assert set(first_hash) <= set("0123456789abcdef")


def test_database_persists_user_with_unverified_email(
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

    user_id = user.id
    db_session.expunge_all()

    persisted_user = db_session.get(
        User,
        user_id,
    )

    assert persisted_user is not None
    assert persisted_user.email_verified_at is None


def test_database_persists_active_email_verification_token(
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

    issued_at = datetime.now(
        timezone.utc,
    )
    token_hash = hash_email_verification_token(
        generate_email_verification_token(),
    )
    verification_token = UserEmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=issued_at
        + timedelta(
            hours=24,
        ),
    )
    db_session.add(
        verification_token,
    )
    db_session.flush()

    verification_token_id = verification_token.id
    db_session.expunge_all()

    persisted_token = db_session.get(
        UserEmailVerificationToken,
        verification_token_id,
    )

    assert persisted_token is not None
    assert persisted_token.user_id == user.id
    assert persisted_token.token_hash == token_hash
    assert persisted_token.expires_at == verification_token.expires_at
    assert persisted_token.consumed_at is None
    assert persisted_token.created_at is not None


def test_repository_creates_and_retrieves_active_email_verification_token(
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

    current_time = datetime.now(
        timezone.utc,
    )
    token_hash = hash_email_verification_token(
        generate_email_verification_token(),
    )

    created_token = email_verification_token_repository.create_email_verification_token(
        db_session,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=current_time
        + timedelta(
            hours=24,
        ),
    )
    token_id = created_token.id

    db_session.expunge_all()

    retrieved_token = email_verification_token_repository.get_active_email_verification_token_by_token_hash(
        db_session,
        token_hash=token_hash,
        current_time=current_time,
    )

    assert retrieved_token is not None
    assert retrieved_token.id == token_id
    assert retrieved_token.user_id == user.id
    assert retrieved_token.token_hash == token_hash
    assert retrieved_token.consumed_at is None


def test_repository_consumes_email_verification_token(
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

    issued_at = datetime.now(
        timezone.utc,
    )
    token_hash = hash_email_verification_token(
        generate_email_verification_token(),
    )
    verification_token = (
        email_verification_token_repository.create_email_verification_token(
            db_session,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=issued_at
            + timedelta(
                hours=24,
            ),
        )
    )
    consumed_at = verification_token.created_at + timedelta(
        seconds=1,
    )

    consumed_token = (
        email_verification_token_repository.consume_email_verification_token(
            db_session,
            verification_token=verification_token,
            consumed_at=consumed_at,
        )
    )

    assert consumed_token.id == verification_token.id
    assert consumed_token.consumed_at == consumed_at

    active_token = email_verification_token_repository.get_active_email_verification_token_by_token_hash(
        db_session,
        token_hash=token_hash,
        current_time=consumed_at,
    )

    assert active_token is None

    persisted_token = db_session.get(
        UserEmailVerificationToken,
        verification_token.id,
    )

    assert persisted_token is not None
    assert persisted_token.consumed_at == consumed_at


def test_repository_returns_none_for_unknown_email_verification_token(
    db_session: Session,
) -> None:
    unknown_token_hash = hash_email_verification_token(
        generate_email_verification_token(),
    )

    verification_token = email_verification_token_repository.get_active_email_verification_token_by_token_hash(
        db_session,
        token_hash=unknown_token_hash,
        current_time=datetime.now(
            timezone.utc,
        ),
    )

    assert verification_token is None


def test_repository_does_not_return_expired_email_verification_token(
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

    issued_at = datetime.now(
        timezone.utc,
    )
    token_hash = hash_email_verification_token(
        generate_email_verification_token(),
    )
    email_verification_token_repository.create_email_verification_token(
        db_session,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=issued_at
        + timedelta(
            hours=1,
        ),
    )

    verification_token = email_verification_token_repository.get_active_email_verification_token_by_token_hash(
        db_session,
        token_hash=token_hash,
        current_time=issued_at
        + timedelta(
            hours=2,
        ),
    )

    assert verification_token is None


def test_service_issues_email_verification_token_without_persisting_raw_token(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    issued_at = datetime.now(
        timezone.utc,
    )
    monkeypatch.setattr(
        email_verification_service,
        "utc_now",
        lambda: issued_at,
    )

    issuance = email_verification_service.issue_email_verification(
        db_session,
        user=user,
    )

    assert issuance.user.id == user.id
    assert issuance.verification_token
    assert issuance.token_record.user_id == user.id
    assert issuance.token_record.expires_at == issued_at + timedelta(
        hours=24,
    )
    assert issuance.token_record.consumed_at is None
    assert issuance.token_record.token_hash != issuance.verification_token
    assert issuance.token_record.token_hash == hash_email_verification_token(
        issuance.verification_token,
    )

    persisted_token = db_session.get(
        UserEmailVerificationToken,
        issuance.token_record.id,
    )

    assert persisted_token is not None
    assert persisted_token.token_hash == issuance.token_record.token_hash
    assert persisted_token.token_hash != issuance.verification_token


def test_service_verifies_email_and_consumes_token(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    issued_at = datetime.now(
        timezone.utc,
    )
    monkeypatch.setattr(
        email_verification_service,
        "utc_now",
        lambda: issued_at,
    )
    issuance = email_verification_service.issue_email_verification(
        db_session,
        user=user,
    )

    verified_at = issuance.token_record.created_at + timedelta(
        seconds=1,
    )
    monkeypatch.setattr(
        email_verification_service,
        "utc_now",
        lambda: verified_at,
    )

    verified_user = email_verification_service.verify_email(
        db_session,
        verification_token=issuance.verification_token,
    )

    assert verified_user.id == user.id
    assert verified_user.email_verified_at == verified_at
    assert issuance.token_record.consumed_at == verified_at

    user_id = user.id
    token_id = issuance.token_record.id
    db_session.expunge_all()

    persisted_user = db_session.get(
        User,
        user_id,
    )
    persisted_token = db_session.get(
        UserEmailVerificationToken,
        token_id,
    )

    assert persisted_user is not None
    assert persisted_user.email_verified_at == verified_at
    assert persisted_token is not None
    assert persisted_token.consumed_at == verified_at

    active_token = email_verification_token_repository.get_active_email_verification_token_by_token_hash(
        db_session,
        token_hash=hash_email_verification_token(
            issuance.verification_token,
        ),
        current_time=verified_at,
    )

    assert active_token is None


@pytest.mark.parametrize(
    "scenario",
    [
        "unknown",
        "expired",
        "consumed",
    ],
)
def test_service_rejects_invalid_email_verification_token(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    issued_at = datetime.now(
        timezone.utc,
    )
    monkeypatch.setattr(
        email_verification_service,
        "utc_now",
        lambda: issued_at,
    )
    issuance = email_verification_service.issue_email_verification(
        db_session,
        user=user,
    )

    submitted_token = issuance.verification_token
    verification_time = issued_at + timedelta(
        minutes=1,
    )

    if scenario == "unknown":
        submitted_token = generate_email_verification_token()

    if scenario == "expired":
        verification_time = issuance.token_record.expires_at

    if scenario == "consumed":
        consumed_at = issuance.token_record.created_at + timedelta(
            seconds=1,
        )
        email_verification_token_repository.consume_email_verification_token(
            db_session,
            verification_token=issuance.token_record,
            consumed_at=consumed_at,
        )
        verification_time = consumed_at + timedelta(
            seconds=1,
        )

    monkeypatch.setattr(
        email_verification_service,
        "utc_now",
        lambda: verification_time,
    )

    with pytest.raises(
        email_verification_service.InvalidEmailVerificationTokenError,
        match="Invalid or expired email verification token",
    ):
        email_verification_service.verify_email(
            db_session,
            verification_token=submitted_token,
        )

    assert user.email_verified_at is None


def test_service_rolls_back_email_verification_when_token_consumption_fails(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    issued_at = datetime.now(
        timezone.utc,
    )
    monkeypatch.setattr(
        email_verification_service,
        "utc_now",
        lambda: issued_at,
    )
    issuance = email_verification_service.issue_email_verification(
        db_session,
        user=user,
    )

    verified_at = issuance.token_record.created_at + timedelta(
        seconds=1,
    )
    monkeypatch.setattr(
        email_verification_service,
        "utc_now",
        lambda: verified_at,
    )

    def fail_to_consume_token(
        *args: object,
        **kwargs: object,
    ) -> None:
        raise RuntimeError(
            "Token consumption failed",
        )

    monkeypatch.setattr(
        email_verification_service.email_verification_token_repository,
        "consume_email_verification_token",
        fail_to_consume_token,
    )

    with pytest.raises(
        RuntimeError,
        match="Token consumption failed",
    ):
        email_verification_service.verify_email(
            db_session,
            verification_token=issuance.verification_token,
        )

    persisted_user = db_session.get(
        User,
        user.id,
    )
    persisted_token = db_session.get(
        UserEmailVerificationToken,
        issuance.token_record.id,
    )

    assert persisted_user is not None
    assert persisted_user.email_verified_at is None
    assert persisted_token is not None
    assert persisted_token.consumed_at is None


def test_service_does_not_enable_disabled_user_during_email_verification(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
        status=UserStatus.DISABLED.value,
    )
    db_session.add(
        user,
    )
    db_session.flush()

    issued_at = datetime.now(
        timezone.utc,
    )
    monkeypatch.setattr(
        email_verification_service,
        "utc_now",
        lambda: issued_at,
    )
    issuance = email_verification_service.issue_email_verification(
        db_session,
        user=user,
    )

    verified_at = issuance.token_record.created_at + timedelta(
        seconds=1,
    )
    monkeypatch.setattr(
        email_verification_service,
        "utc_now",
        lambda: verified_at,
    )

    verified_user = email_verification_service.verify_email(
        db_session,
        verification_token=issuance.verification_token,
    )

    assert verified_user.email_verified_at == verified_at
    assert verified_user.status == UserStatus.DISABLED.value
    assert issuance.token_record.consumed_at == verified_at


@pytest.mark.parametrize(
    (
        "token_hash",
        "expiry_offset",
        "consumption_offset",
    ),
    [
        (
            "not-a-valid-token-hash",
            timedelta(
                hours=1,
            ),
            None,
        ),
        (
            hash_email_verification_token("expired-token"),
            timedelta(),
            None,
        ),
        (
            hash_email_verification_token("consumed-too-early-token"),
            timedelta(
                hours=1,
            ),
            timedelta(
                seconds=-1,
            ),
        ),
    ],
)
def test_database_rejects_invalid_email_verification_token(
    db_session: Session,
    token_hash: str,
    expiry_offset: timedelta,
    consumption_offset: timedelta | None,
) -> None:
    user = User(
        email="engineer@example.com",
        display_name="Engineering Reviewer",
    )
    db_session.add(
        user,
    )
    db_session.flush()

    created_at = datetime.now(
        timezone.utc,
    )
    consumed_at = (
        created_at + consumption_offset if consumption_offset is not None else None
    )
    verification_token = UserEmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        created_at=created_at,
        expires_at=created_at + expiry_offset,
        consumed_at=consumed_at,
    )
    db_session.add(
        verification_token,
    )

    with pytest.raises(
        IntegrityError,
    ):
        db_session.flush()


def test_database_rejects_duplicate_email_verification_token_hash(
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

    created_at = datetime.now(
        timezone.utc,
    )
    token_hash = hash_email_verification_token(
        "duplicate-token",
    )

    first_token = UserEmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        created_at=created_at,
        expires_at=created_at
        + timedelta(
            hours=1,
        ),
    )
    db_session.add(
        first_token,
    )
    db_session.flush()

    duplicate_token = UserEmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        created_at=created_at,
        expires_at=created_at
        + timedelta(
            hours=1,
        ),
    )
    db_session.add(
        duplicate_token,
    )

    with pytest.raises(
        IntegrityError,
    ):
        db_session.flush()
