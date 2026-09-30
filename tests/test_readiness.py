from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, TimeoutError

from app.main import app
from app.services import readiness as readiness_service


def test_readiness_can_query_real_database(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert response.headers["Cache-Control"] == "no-store"


def test_readiness_executes_probe_and_releases_connection(monkeypatch) -> None:
    connect = MagicMock()
    connection = connect.return_value.__enter__.return_value
    connection.scalar.return_value = 1
    monkeypatch.setattr(readiness_service.readiness_engine, "connect", connect)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert str(connection.scalar.call_args.args[0]) == "SELECT 1"
    connect.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        OperationalError("SELECT 1", {}, Exception("private-database-password")),
        TimeoutError("private-database-host"),
    ],
)
def test_readiness_reports_unavailable_without_connection_details(
    monkeypatch, error
) -> None:
    monkeypatch.setattr(
        readiness_service.readiness_engine,
        "connect",
        MagicMock(side_effect=error),
    )

    with TestClient(app) as client:
        response = client.get("/ready")
        health = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"]
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_readiness_handles_query_failure_and_releases_connection(monkeypatch) -> None:
    connect = MagicMock()
    connect.return_value.__enter__.return_value.scalar.side_effect = OperationalError(
        "SELECT 1", {}, Exception("query timed out")
    )
    monkeypatch.setattr(readiness_service.readiness_engine, "connect", connect)

    assert readiness_service.is_database_ready() is False
    connect.return_value.__exit__.assert_called_once()


def test_liveness_does_not_connect_to_database(monkeypatch) -> None:
    connect = MagicMock(side_effect=AssertionError("Must not access database"))
    monkeypatch.setattr(readiness_service.readiness_engine, "connect", connect)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    connect.assert_not_called()
