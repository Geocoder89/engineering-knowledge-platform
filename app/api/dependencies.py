from collections.abc import Iterator
from typing import Annotated, TypeAlias

import httpx
from fastapi import (
    Cookie,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_session
from app.embeddings.base import EmbeddingProvider
from app.embeddings.dependencies import get_embedding_provider
from app.notifications.base import EmailVerificationSender
from app.notifications.dependencies import get_email_verification_sender
from app.services import authentication as authentication_service
from app.services.rate_limiting import DatabaseRateLimiter, RateLimiter


def provide_embedding_provider() -> EmbeddingProvider:
    return get_embedding_provider()


EmbeddingProviderDependency: TypeAlias = Annotated[
    EmbeddingProvider,
    Depends(provide_embedding_provider),
]

SessionDependency: TypeAlias = Annotated[
    Session,
    Depends(get_session),
]

SessionTokenCookie: TypeAlias = Annotated[
    str | None,
    Cookie(
        alias=settings.session_cookie_name,
    ),
]

rate_limiter = DatabaseRateLimiter(
    session_factory=SessionLocal,
)


def provide_rate_limiter() -> RateLimiter:
    return rate_limiter


RateLimiterDependency: TypeAlias = Annotated[
    RateLimiter,
    Depends(provide_rate_limiter),
]


def provide_email_verification_sender() -> Iterator[EmailVerificationSender]:
    if settings.resend_api_key is None:
        yield get_email_verification_sender()
        return

    with httpx.Client(
        timeout=settings.email_delivery_timeout_seconds,
    ) as http_client:
        yield get_email_verification_sender(
            http_client=http_client,
        )


EmailVerificationSenderDependency: TypeAlias = Annotated[
    EmailVerificationSender,
    Depends(provide_email_verification_sender),
]


def require_authenticated_user(
    session: SessionDependency,
    session_token: SessionTokenCookie = None,
) -> authentication_service.AuthenticatedUser:
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        return authentication_service.resolve_authenticated_user(
            session,
            session_token=session_token,
        )
    except authentication_service.InvalidSessionError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error


AuthenticatedUserDependency: TypeAlias = Annotated[
    authentication_service.AuthenticatedUser,
    Depends(require_authenticated_user),
]
