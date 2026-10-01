from fastapi import FastAPI

from app.api.routes import authentication, decisions, documents, health, search, users
from app.config import settings
from app.middleware.csrf import CsrfProtectionMiddleware
from app.middleware.request_logging import (
    RequestLoggingMiddleware,
    configure_request_logging,
    unhandled_error_response,
)

configure_request_logging()

app = FastAPI(exception_handlers={Exception: unhandled_error_response})

app.add_middleware(CsrfProtectionMiddleware, application_settings=settings)
# Last added is outermost: CSRF rejections also receive an ID and a log entry.
app.add_middleware(RequestLoggingMiddleware)

app.include_router(health.router)
app.include_router(authentication.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(decisions.router)
