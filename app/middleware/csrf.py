from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings
from app.security.csrf import (
    csrf_tokens_match,
    is_trusted_request_origin,
)

UNSAFE_HTTP_METHODS = frozenset(
    {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    },
)

CSRF_TOKEN_EXEMPT_PATHS = frozenset(
    {
        "/auth/login",
        "/auth/register",
        "/auth/verify-email",
        "/auth/resend-verification",
    },
)

CSRF_HEADER_NAME = "X-CSRF-Token"


class CsrfProtectionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        application_settings: Settings,
    ) -> None:
        self._app = app
        self._application_settings = application_settings

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self._app(
                scope,
                receive,
                send,
            )
            return

        request = Request(scope)

        if request.method not in UNSAFE_HTTP_METHODS:
            await self._app(
                scope,
                receive,
                send,
            )
            return

        if not is_trusted_request_origin(
            origin=request.headers.get("Origin"),
            trusted_origins=self._application_settings.csrf_trusted_origins,
        ):
            response = JSONResponse(
                status_code=403,
                content={
                    "detail": "Request origin is not allowed",
                },
            )
            await response(
                scope,
                receive,
                send,
            )
            return

        session_token = request.cookies.get(
            self._application_settings.session_cookie_name,
        )
        csrf_protection_required = (
            session_token is not None
            and request.url.path not in CSRF_TOKEN_EXEMPT_PATHS
        )

        if csrf_protection_required and not csrf_tokens_match(
            cookie_token=request.cookies.get(
                self._application_settings.csrf_cookie_name,
            ),
            header_token=request.headers.get(
                CSRF_HEADER_NAME,
            ),
        ):
            response = JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF token is invalid",
                },
            )
            await response(
                scope,
                receive,
                send,
            )
            return

        await self._app(
            scope,
            receive,
            send,
        )
