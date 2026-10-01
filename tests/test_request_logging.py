import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

from app.main import app
from app.middleware.request_logging import (
    RequestLogFormatter,
    RequestLoggingMiddleware,
    configure_request_logging,
    logger,
    unhandled_error_response,
)


@pytest.fixture
def request_logs(caplog):
    # The dedicated JSON logger does not propagate to the root/server logger.
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)


@pytest.fixture
def observed_app() -> FastAPI:
    application = FastAPI(exception_handlers={Exception: unhandled_error_response})
    application.add_middleware(RequestLoggingMiddleware)

    @application.get("/items/{item_id}")
    def item(item_id: int) -> dict:
        return {"id": item_id}

    @application.get("/handled-error")
    def handled_error() -> None:
        raise HTTPException(status_code=409, detail="Conflict")

    @application.get("/unexpected-error")
    def unexpected_error() -> None:
        raise RuntimeError("private-error-content")

    @application.get("/stream")
    def stream() -> StreamingResponse:
        return StreamingResponse(iter([b"first", b"second"]))

    return application


def formatted_records(request_logs) -> list[dict]:
    formatter = RequestLogFormatter()
    return [
        json.loads(formatter.format(record))
        for record in request_logs.records
        if record.name == logger.name
    ]


def test_response_id_matches_one_structured_log(request_logs) -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "caller-chosen-id"})

    request_id = response.headers["X-Request-ID"]
    assert UUID(request_id).version == 4
    assert request_id != "caller-chosen-id"
    [entry] = formatted_records(request_logs)
    assert entry["request_id"] == request_id
    assert entry["method"] == "GET"
    assert entry["path"] == "/health"
    assert entry["status_code"] == 200
    assert entry["duration_ms"] >= 0
    assert entry["error_type"] is None
    assert entry["level"] == "INFO"


@pytest.mark.parametrize(
    ("path", "expected_status", "expected_route"),
    [
        ("/items/12345", 200, "/items/{item_id}"),
        ("/items/private-invalid-id", 422, "/items/{item_id}"),
        ("/private-unknown-path", 404, "<unmatched>"),
        ("/handled-error", 409, "/handled-error"),
        ("/unexpected-error", 500, "/unexpected-error"),
    ],
)
def test_request_logs_omit_sensitive_request_data(
    observed_app, request_logs, path, expected_status, expected_route
) -> None:
    with TestClient(observed_app, raise_server_exceptions=False) as client:
        response = client.request(
            "GET",
            path + "?token=private-query-token",
            headers={
                "Authorization": "Bearer private-authorization",
                "Cookie": "session=private-session-cookie",
                "X-Request-ID": "private-caller-id",
            },
            content="private-document-content",
        )

    assert response.status_code == expected_status
    [entry] = formatted_records(request_logs)
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["path"] == expected_route
    assert entry["status_code"] == expected_status
    assert "private-" not in json.dumps(entry)
    assert "12345" not in entry["path"]
    if expected_status == 500:
        assert response.text == "Internal Server Error"
        assert entry["error_type"] == "RuntimeError"
        assert entry["level"] == "ERROR"


def test_csrf_rejection_has_request_id_and_log(request_logs) -> None:
    with TestClient(app) as client:
        response = client.post("/decisions", json={"title": "private-title"})

    assert response.status_code == 403
    [entry] = formatted_records(request_logs)
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["status_code"] == 403
    assert entry["path"] == "<unmatched>"
    assert "private-title" not in json.dumps(entry)


def test_streaming_response_is_preserved_and_logged_once(
    observed_app, request_logs
) -> None:
    with TestClient(observed_app) as client:
        response = client.get("/stream")

    assert response.content == b"firstsecond"
    [entry] = formatted_records(request_logs)
    assert entry["status_code"] == 200
    assert entry["request_id"] == response.headers["X-Request-ID"]


def test_unhandled_errors_still_propagate_to_server(observed_app, request_logs) -> None:
    with TestClient(observed_app) as client:
        with pytest.raises(RuntimeError, match="private-error-content"):
            client.get("/unexpected-error")

    [entry] = formatted_records(request_logs)
    assert entry["status_code"] == 500
    assert entry["error_type"] == "RuntimeError"


def test_concurrent_requests_have_distinct_matching_ids(request_logs) -> None:
    def request_id(_index: int) -> str:
        with TestClient(app) as client:
            return client.get("/health").headers["X-Request-ID"]

    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = list(executor.map(request_id, range(8)))

    entries = formatted_records(request_logs)
    assert len(set(ids)) == 8
    assert len(entries) == 8
    assert {entry["request_id"] for entry in entries} == set(ids)


def test_configuring_request_logging_does_not_duplicate_handlers() -> None:
    before = len(logger.handlers)
    configure_request_logging()
    configure_request_logging()
    assert len(logger.handlers) == before
