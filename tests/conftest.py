from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.orm import Session

from app.database import engine, get_session
from app.main import app
from app.storage.dependencies import get_document_storage
from app.storage.local import LocalDocumentStorage


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
    document_storage_path: Path, database_connection: Connection
) -> Generator[TestClient, None, None]:
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
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(
            get_document_storage,
            None,
        )
