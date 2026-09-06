from typing import Annotated, TypeAlias

from fastapi import (
    Cookie,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.embeddings.base import EmbeddingProvider
from app.embeddings.dependencies import get_embedding_provider
from app.services import authentication as authentication_service


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
