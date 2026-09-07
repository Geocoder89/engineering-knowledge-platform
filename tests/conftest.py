from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.orm import Session

from app.api.dependencies import provide_email_verification_sender
from app.config import settings
from app.database import engine, get_session
from app.main import app
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
    app.dependency_overrides[provide_email_verification_sender] = (
        override_email_verification_sender
    )
    try:
        with TestClient(
            app,
            base_url="https://testserver",
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

        app.dependency_overrides.pop(provide_email_verification_sender, None)
