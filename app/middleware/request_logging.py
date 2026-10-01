import json
import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.requests")


class RequestLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Only emit explicitly selected fields, never arbitrary extras or errors.
        return json.dumps(
            {
                "timestamp": datetime.fromtimestamp(
                    record.created, tz=timezone.utc
                ).isoformat(),
                "level": record.levelname,
                "event": "http_request",
                "request_id": record.request_id,
                "method": record.method,
                "path": record.route_path,
                "status_code": record.status_code,
                "duration_ms": record.duration_ms,
                "error_type": record.error_type,
            }
        )


def configure_request_logging() -> None:
    if not any(
        isinstance(handler.formatter, RequestLogFormatter)
        for handler in logger.handlers
    ):
        handler = logging.StreamHandler()
        handler.setFormatter(RequestLogFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


async def unhandled_error_response(
    request: Request, _error: Exception
) -> PlainTextResponse:
    # Starlette creates unhandled 500 responses outside user middleware. Preserve
    # the request ID there as well, while leaving exception propagation intact.
    return PlainTextResponse(
        "Internal Server Error",
        status_code=500,
        headers={"X-Request-ID": request.state.request_id},
    )


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        # Always generate the ID ourselves; callers cannot inject log content or
        # choose an existing request's identity through an incoming header.
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started_at = perf_counter()
        status_code = 500
        error_type = None

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self._app(scope, receive, send_with_request_id)
        except Exception as error:
            error_type = type(error).__name__
            raise
        finally:
            # Route templates omit resource IDs and arbitrary user-controlled
            # paths. A rejection before routing has no safe template to log.
            route_path = getattr(scope.get("route"), "path", "<unmatched>")
            level = logging.ERROR if error_type or status_code >= 500 else logging.INFO
            logger.log(
                level,
                "http_request",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "route_path": route_path,
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                    "error_type": error_type,
                },
            )
