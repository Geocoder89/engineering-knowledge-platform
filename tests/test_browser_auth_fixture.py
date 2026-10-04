import json
import os
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts import browser_auth_server


@pytest.mark.parametrize(
    ("opt_in", "database_name"),
    [("0", "isolated_browser_test"), ("1", "normal_development")],
)
def test_browser_fixture_refuses_unsafe_database_configuration(
    monkeypatch, opt_in: str, database_name: str
) -> None:
    monkeypatch.setattr("sys.argv", ["browser_auth_server"])
    monkeypatch.setenv("RUN_BROWSER_AUTH_TESTS", opt_in)
    monkeypatch.setattr(
        browser_auth_server.settings,
        "database_url",
        f"postgresql+psycopg://localhost/{database_name}",
    )
    session_factory = Mock()
    monkeypatch.setattr(browser_auth_server, "SessionLocal", session_factory)

    with pytest.raises(RuntimeError, match="disposable database"):
        browser_auth_server.main()

    session_factory.assert_not_called()


def test_browser_mailbox_keeps_latest_link_private_and_out_of_logs(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    directory = tmp_path / "outbox"
    monkeypatch.setenv("BROWSER_AUTH_OUTBOX_DIR", str(directory))
    sender = browser_auth_server.FileEmailVerificationSender()
    for token in ("original-fixture-token", "replacement-fixture-token"):
        sender.send_email_verification(
            recipient_email="samuel@example.test",
            recipient_display_name="Samuel",
            verification_token=token,
        )

    output = capsys.readouterr()
    assert output.out == output.err == ""
    path = browser_auth_server.email_path(" SAMUEL@example.test ")
    message = json.loads(path.read_text())
    link = urlsplit(message["verification_url"])
    assert link.path == "/verify-email"
    assert parse_qs(link.query) == {"token": ["replacement-fixture-token"]}
    assert len(list(directory.iterdir())) == 1
    if os.name == "posix":
        assert directory.stat().st_mode & 0o777 == 0o700
        assert path.stat().st_mode & 0o777 == 0o600

    monkeypatch.setattr(
        "sys.argv", ["browser_auth_server", "--show-link", "samuel@example.test"]
    )
    browser_auth_server.main()
    assert capsys.readouterr().out.strip() == message["verification_url"]
