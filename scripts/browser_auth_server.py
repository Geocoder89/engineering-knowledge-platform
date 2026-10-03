"""Real API fixture for Playwright, restricted to a disposable test database.

No authentication routes are replaced or bypassed. Only fixture users are seeded;
registration and verification use the same services as the application.
"""

import os

import uvicorn
from sqlalchemy.engine import make_url

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.services.email_verification import verify_email
from app.services.user_registration import register_user


def main() -> None:
    database_name = make_url(settings.database_url).database or ""
    if os.environ.get("RUN_BROWSER_AUTH_TESTS") != "1" or not database_name.endswith(
        "_browser_test"
    ):
        raise RuntimeError(
            "Browser fixtures require RUN_BROWSER_AUTH_TESTS=1 and a disposable "
            "database whose name ends with _browser_test"
        )

    with SessionLocal() as session:
        for viewport in ("desktop", "mobile"):
            registration = register_user(
                session,
                email=f"browser-{viewport}@example.test",
                display_name=f"Browser {viewport.title()}",
                password="Browser-only-fixture-password-2026",
            )
            verify_email(
                session,
                verification_token=registration.email_verification.verification_token,
            )
        session.commit()

    uvicorn.run(app, host="127.0.0.1", port=8001, access_log=False)


if __name__ == "__main__":
    main()
