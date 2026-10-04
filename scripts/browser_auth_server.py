"""Real API fixture for Playwright and local onboarding checks.

Requires explicit opt-in and a disposable *_browser_test database. Only email
transport is replaced: verification links are captured in private temporary
files. No production routes, authentication checks, or rate limits are replaced.
"""

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlencode

import uvicorn
from sqlalchemy.engine import make_url

from app.api.dependencies import provide_email_verification_sender
from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.repositories.user import get_user_by_email
from app.services.email_verification import verify_email
from app.services.user_registration import register_user


def outbox_directory() -> Path:
    return Path(
        os.environ.get(
            "BROWSER_AUTH_OUTBOX_DIR",
            str(Path(tempfile.gettempdir()) / "decision-browser-outbox"),
        )
    )


def email_path(email: str) -> Path:
    key = hashlib.sha256(email.strip().lower().encode()).hexdigest()
    return outbox_directory() / f"{key}.json"


class FileEmailVerificationSender:
    def send_email_verification(
        self,
        *,
        recipient_email: str,
        recipient_display_name: str,
        verification_token: str,
    ) -> None:
        directory = outbox_directory()
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
        link = "http://127.0.0.1:5173/verify-email?" + urlencode(
            {"token": verification_token}
        )
        # Atomic writes allow parallel browser tests to read complete messages.
        with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as file:
            json.dump({"email": recipient_email, "verification_url": link}, file)
            temporary_path = Path(file.name)
        temporary_path.replace(email_path(recipient_email))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show-link", metavar="EMAIL", help="Read a captured local link"
    )
    args = parser.parse_args()
    if args.show_link:
        path = email_path(args.show_link)
        if not path.is_file():
            parser.exit(
                1, "No captured email for that address. Register or resend first.\n"
            )
        # Explicit terminal display only; the running API never logs tokens.
        print(json.loads(path.read_text())["verification_url"])
        return

    database_name = make_url(settings.database_url).database or ""
    if os.environ.get("RUN_BROWSER_AUTH_TESTS") != "1" or not database_name.endswith(
        "_browser_test"
    ):
        raise RuntimeError(
            "Browser fixtures require RUN_BROWSER_AUTH_TESTS=1 and a disposable "
            "database whose name ends with _browser_test"
        )

    sender = FileEmailVerificationSender()
    app.dependency_overrides[provide_email_verification_sender] = lambda: sender
    with SessionLocal() as session:
        for viewport in ("desktop", "mobile"):
            email = f"browser-{viewport}@example.test"
            if get_user_by_email(session, email=email) is not None:
                continue
            registration = register_user(
                session,
                email=email,
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
