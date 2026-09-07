import logging

from fastapi import (
    APIRouter,
    HTTPException,
    Response,
    status,
)

from app.api.dependencies import (
    EmailVerificationSenderDependency,
    SessionDependency,
    SessionTokenCookie,
)
from app.config import settings
from app.models.user import User
from app.notifications.base import EmailVerificationDeliveryError
from app.schemas.authentication import (
    AuthenticatedUserResponse,
    EmailVerificationRequest,
    EmailVerificationResendRequest,
    LoginRequest,
    RegistrationRequest,
)
from app.services import authentication as authentication_service
from app.services import email_verification as email_verification_service
from app.services import user_registration as user_registration_service

logger = logging.getLogger(
    __name__,
)
router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


@router.post(
    "/register",
    response_model=AuthenticatedUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegistrationRequest,
    session: SessionDependency,
    email_verification_sender: EmailVerificationSenderDependency,
) -> User:
    try:
        registration = user_registration_service.register_user(
            session,
            email=request.email,
            display_name=request.display_name,
            password=request.password,
        )
    except user_registration_service.UserAlreadyExistsError as error:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    try:
        email_verification_sender.send_email_verification(
            recipient_email=registration.user.email,
            recipient_display_name=registration.user.display_name,
            verification_token=(registration.email_verification.verification_token),
        )
    except EmailVerificationDeliveryError as error:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User registration could not be completed",
        ) from error
    session.commit()

    return registration.user


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


@router.post(
    "/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
)
def verify_email(
    request: EmailVerificationRequest,
    session: SessionDependency,
) -> None:
    try:
        email_verification_service.verify_email(
            session,
            verification_token=request.verification_token,
        )
    except email_verification_service.InvalidEmailVerificationTokenError as error:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    session.commit()


@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
)
def resend_email_verification(
    request: EmailVerificationResendRequest,
    session: SessionDependency,
    email_verification_sender: EmailVerificationSenderDependency,
) -> Response:
    verification = email_verification_service.request_email_verification(
        session,
        email=request.email,
    )

    if verification is not None:
        try:
            email_verification_sender.send_email_verification(
                recipient_email=verification.user.email,
                recipient_display_name=verification.user.display_name,
                verification_token=verification.verification_token,
            )
        except EmailVerificationDeliveryError:
            session.rollback()
            logger.warning(
                "Email verification resend delivery failed",
            )

    session.commit()

    return Response(
        status_code=status.HTTP_202_ACCEPTED,
    )
