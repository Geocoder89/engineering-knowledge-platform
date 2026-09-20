import logging
from datetime import timedelta

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Response,
    status,
)

from app.api.dependencies import (
    EmailVerificationSenderDependency,
    RateLimiterDependency,
    SessionDependency,
    SessionTokenCookie,
)
from app.config import settings
from app.domain.user import normalize_user_email
from app.models.user import User
from app.notifications.base import EmailVerificationDeliveryError
from app.schemas.authentication import (
    AuthenticatedUserResponse,
    EmailVerificationRequest,
    EmailVerificationResendRequest,
    LoginRequest,
    RegistrationRequest,
)
from app.security.csrf import generate_csrf_token
from app.services import authentication as authentication_service
from app.services import email_verification as email_verification_service
from app.services import user_registration as user_registration_service
from app.services.rate_limiting import RateLimiter

REGISTRATION_EMAIL_RATE_LIMIT = 3
REGISTRATION_IP_RATE_LIMIT = 5
REGISTRATION_RATE_LIMIT_WINDOW = timedelta(hours=1)

LOGIN_EMAIL_RATE_LIMIT = 5
LOGIN_IP_RATE_LIMIT = 20
LOGIN_RATE_LIMIT_WINDOW = timedelta(minutes=15)

RESEND_VERIFICATION_EMAIL_RATE_LIMIT = 3
RESEND_VERIFICATION_IP_RATE_LIMIT = 10
RESEND_VERIFICATION_RATE_LIMIT_WINDOW = timedelta(hours=1)

VERIFY_EMAIL_IP_RATE_LIMIT = 20
VERIFY_EMAIL_RATE_LIMIT_WINDOW = timedelta(minutes=15)


def _enforce_rate_limit(
    *,
    rate_limiter: RateLimiter,
    scope: str,
    raw_key: str,
    limit: int,
    window: timedelta,
) -> None:
    decision = rate_limiter.check(
        scope=scope,
        raw_key=raw_key,
        limit=limit,
        window=window,
    )

    if decision.allowed:
        return

    retry_after_seconds = decision.retry_after_seconds

    if retry_after_seconds is None:
        raise RuntimeError(
            "Rejected rate-limit decision requires Retry-After",
        )

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests",
        headers={
            "Retry-After": str(retry_after_seconds),
        },
    )


def _get_client_host(
    request: Request,
) -> str:
    if request.client is None:
        return "unknown"

    return request.client.host


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
    http_request: Request,
    registration_request: RegistrationRequest,
    session: SessionDependency,
    email_verification_sender: EmailVerificationSenderDependency,
    rate_limiter: RateLimiterDependency,
) -> User:

    client_host = _get_client_host(http_request)
    normalized_email = normalize_user_email(
        registration_request.email,
    )

    _enforce_rate_limit(
        rate_limiter=rate_limiter,
        scope="authentication.registration.ip",
        raw_key=client_host,
        limit=REGISTRATION_IP_RATE_LIMIT,
        window=REGISTRATION_RATE_LIMIT_WINDOW,
    )
    _enforce_rate_limit(
        rate_limiter=rate_limiter,
        scope="authentication.registration.email",
        raw_key=normalized_email,
        limit=REGISTRATION_EMAIL_RATE_LIMIT,
        window=REGISTRATION_RATE_LIMIT_WINDOW,
    )
    try:
        registration = user_registration_service.register_user(
            session,
            email=normalized_email,
            display_name=registration_request.display_name,
            password=registration_request.password,
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
    http_request: Request,
    credentials: LoginRequest,
    response: Response,
    session: SessionDependency,
    rate_limiter: RateLimiterDependency,
) -> User:
    client_host = _get_client_host(http_request)
    _enforce_rate_limit(
        rate_limiter=rate_limiter,
        scope="authentication.login.ip",
        raw_key=client_host,
        limit=LOGIN_IP_RATE_LIMIT,
        window=LOGIN_RATE_LIMIT_WINDOW,
    )
    normalized_email = normalize_user_email(credentials.email)

    _enforce_rate_limit(
        rate_limiter=rate_limiter,
        scope="authentication.login.email",
        raw_key=normalized_email,
        limit=LOGIN_EMAIL_RATE_LIMIT,
        window=LOGIN_RATE_LIMIT_WINDOW,
    )
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

    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=generate_csrf_token(),
        max_age=int(
            authentication_service.SESSION_DURATION.total_seconds(),
        ),
        httponly=False,
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

    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=False,
        samesite=settings.session_cookie_samesite,
    )


@router.post(
    "/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
)
def verify_email(
    http_request: Request,
    verification_request: EmailVerificationRequest,
    session: SessionDependency,
    rate_limiter: RateLimiterDependency,
) -> None:
    _enforce_rate_limit(
        rate_limiter=rate_limiter,
        scope="authentication.verify_email.ip",
        raw_key=_get_client_host(http_request),
        limit=VERIFY_EMAIL_IP_RATE_LIMIT,
        window=VERIFY_EMAIL_RATE_LIMIT_WINDOW,
    )
    try:
        email_verification_service.verify_email(
            session,
            verification_token=verification_request.verification_token,
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
    http_request: Request,
    resend_request: EmailVerificationResendRequest,
    session: SessionDependency,
    email_verification_sender: EmailVerificationSenderDependency,
    rate_limiter: RateLimiterDependency,
) -> Response:
    client_host = _get_client_host(http_request)
    normalized_email = normalize_user_email(
        resend_request.email,
    )

    _enforce_rate_limit(
        rate_limiter=rate_limiter,
        scope="authentication.resend_verification.ip",
        raw_key=client_host,
        limit=RESEND_VERIFICATION_IP_RATE_LIMIT,
        window=RESEND_VERIFICATION_RATE_LIMIT_WINDOW,
    )
    _enforce_rate_limit(
        rate_limiter=rate_limiter,
        scope="authentication.resend_verification.email",
        raw_key=normalized_email,
        limit=RESEND_VERIFICATION_EMAIL_RATE_LIMIT,
        window=RESEND_VERIFICATION_RATE_LIMIT_WINDOW,
    )
    verification = email_verification_service.request_email_verification(
        session,
        email=normalized_email,
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
