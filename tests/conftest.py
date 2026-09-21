from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.orm import Session, sessionmaker

from app.api import dependencies as api_dependencies
from app.config import settings
from app.database import engine, get_session
from app.main import app
from app.models.document import Document
from app.models.user import User
from app.models.user_session import UserSession
from app.services import authentication as authentication_service
from app.services.rate_limiting import DatabaseRateLimiter
from app.storage.dependencies import get_document_storage
from app.storage.local import LocalDocumentStorage


@dataclass(frozen=True)
class SentEmailVerification:
    recipient_email: str
    recipient_display_name: str
    verification_token: str


@dataclass
class FakeEmailVerificationSender:
    sent_verifications: list[SentEmailVerification] = field(
        default_factory=list,
    )

    def send_email_verification(
        self,
        *,
        recipient_email: str,
        recipient_display_name: str,
        verification_token: str,
    ) -> None:
        self.sent_verifications.append(
            SentEmailVerification(
                recipient_email=recipient_email,
                recipient_display_name=recipient_display_name,
                verification_token=verification_token,
            ),
        )


@pytest.fixture
def email_verification_sender() -> FakeEmailVerificationSender:
    return FakeEmailVerificationSender()


@pytest.fixture
def database_connection() -> Generator[Connection, None, None]:
    connection = engine.connect()
    outer_transaction = connection.begin()

    try:
        yield connection
    finally:
        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()


@pytest.fixture
def db_session(
    database_connection: Connection,
) -> Generator[Session, None, None]:
    with Session(
        bind=database_connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session


@pytest.fixture
def persisted_document_factory() -> Callable[..., Document]:
    def create_persisted_document(
        session: Session,
        *,
        title: str = "Cooling system",
        file_name: str = "cooling-design.pdf",
        status: str = "pending",
    ) -> Document:
        owner = User(
            email=f"document-owner-{uuid4()}@example.com",
            display_name="Document Owner",
        )
        session.add(owner)
        session.flush()

        document = Document(
            owner_user_id=owner.id,
            title=title,
            file_name=file_name,
            status=status,
        )
        session.add(document)
        session.flush()

        return document

    return create_persisted_document


@pytest.fixture
def authenticated_user(
    db_session: Session,
) -> authentication_service.AuthenticatedUser:
    current_time = datetime.now(
        timezone.utc,
    )

    user = User(
        email="authenticated@example.com",
        display_name="Authenticated User",
        email_verified_at=current_time,
    )
    db_session.add(user)
    db_session.flush()

    user_session = UserSession(
        user_id=user.id,
        token_hash="0" * 64,
        expires_at=current_time
        + timedelta(
            hours=12,
        ),
    )
    db_session.add(user_session)
    db_session.flush()

    return authentication_service.AuthenticatedUser(
        user=user,
        user_session=user_session,
    )


@pytest.fixture
def authenticated_client(
    client: TestClient,
    authenticated_user: authentication_service.AuthenticatedUser,
) -> Generator[TestClient, None, None]:
    def override_authenticated_user() -> authentication_service.AuthenticatedUser:
        return authenticated_user

    app.dependency_overrides[api_dependencies.require_authenticated_user] = (
        override_authenticated_user
    )

    try:
        yield client
    finally:
        app.dependency_overrides.pop(
            api_dependencies.require_authenticated_user,
            None,
        )


@pytest.fixture
def document_storage_path(tmp_path: Path) -> Path:
    return tmp_path / "document-storage"


@pytest.fixture
def client(
    document_storage_path: Path,
    database_connection: Connection,
    email_verification_sender: FakeEmailVerificationSender,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(
        settings,
        "session_cookie_secure",
        True,
    )

    monkeypatch.setattr(
        settings,
        "csrf_trusted_origins",
        frozenset(
            {
                "https://testserver",
            },
        ),
    )

    rate_limit_session_factory = sessionmaker(
        bind=database_connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    rate_limiter = DatabaseRateLimiter(
        session_factory=rate_limit_session_factory,
    )

    def override_rate_limiter() -> DatabaseRateLimiter:
        return rate_limiter

    def override_email_verification_sender() -> FakeEmailVerificationSender:
        return email_verification_sender

    def override_get_document_storage() -> LocalDocumentStorage:
        return LocalDocumentStorage(
            root_path=document_storage_path,
        )

    def override_get_session() -> Generator[Session, None, None]:
        with Session(
            bind=database_connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_document_storage] = override_get_document_storage
    app.dependency_overrides[api_dependencies.provide_email_verification_sender] = (
        override_email_verification_sender
    )
    app.dependency_overrides[api_dependencies.provide_rate_limiter] = (
        override_rate_limiter
    )
    try:
        with TestClient(
            app,
            base_url="https://testserver",
            headers={
                "Origin": "https://testserver",
            },
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(
            get_session,
            None,
        )
        app.dependency_overrides.pop(
            get_document_storage,
            None,
        )

        app.dependency_overrides.pop(
            api_dependencies.provide_email_verification_sender, None
        )
        app.dependency_overrides.pop(
            api_dependencies.provide_rate_limiter,
            None,
        )
