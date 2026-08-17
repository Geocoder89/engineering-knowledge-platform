from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import engine, get_session
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    connection = engine.connect()
    outer_transaction = connection.begin()

    def override_get_session() -> Generator[Session, None, None]:
        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)

        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()