from fastapi import (
    APIRouter,
    HTTPException,
    Response,
    status,
)

from app.api.dependencies import SessionDependency, SessionTokenCookie
from app.config import settings
from app.models.user import User
from app.schemas.authentication import (
    AuthenticatedUserResponse,
    LoginRequest,
)
from app.services import authentication as authentication_service

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


@router.post(
    "/login",
    response_model=AuthenticatedUserResponse,
)
def login(
    credentials: LoginRequest,
    response: Response,
    session: SessionDependency,
) -> User:
    try:
        authentication = authentication_service.authenticate_user(
            session,
            email=credentials.email,
            password=credentials.password,
        )
    except authentication_service.InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error

    session.commit()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=authentication.session_token,
        max_age=int(
            authentication_service.SESSION_DURATION.total_seconds(),
        ),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )

    return authentication.user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    response: Response,
    session: SessionDependency,
    session_token: SessionTokenCookie = None,
) -> None:
    if session_token is not None:
        authentication_service.revoke_authenticated_session(
            session,
            session_token=session_token,
        )

    session.commit()

    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )
