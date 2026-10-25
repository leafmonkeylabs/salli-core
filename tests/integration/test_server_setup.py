"""`salli-server secrets init`, `setup` and `members`, as the container runs
them: configuration from the environment and a secrets directory, no .env,
against a real database."""

from __future__ import annotations

import io
import json
import stat
import sys
from pathlib import Path

import pytest

from salli.interfaces.cli import main, support
from tests.integration.pg import requires_postgres, scalar

pytestmark = requires_postgres

OWNER_PASSWORD = "the owner's long password"


@pytest.fixture
def server(db, tmp_path, monkeypatch):
    """A server's environment: the scratch database, a secrets directory, and
    a working directory with no .env in it."""
    import salli.config

    secrets_dir = tmp_path / "secrets"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", db)
    monkeypatch.setenv("SALLI_SECRETS_DIR", str(secrets_dir))
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SALLI_USER_ID", raising=False)
    monkeypatch.setattr(salli.config, "_settings", None)
    monkeypatch.setattr(support, "_json_mode", False)
    monkeypatch.setattr(support.console, "_file", None)
    return secrets_dir


def run(monkeypatch, capsys, *argv: str, stdin: str = "") -> tuple[int, str, str]:
    import salli.config

    # Each command reads its settings afresh, as a new process would.
    monkeypatch.setattr(salli.config, "_settings", None)
    monkeypatch.setattr(support, "_json_mode", False)
    monkeypatch.setattr(support.console, "_file", None)
    monkeypatch.setattr(sys, "argv", ["salli-server", *argv])
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    with pytest.raises(SystemExit) as exited:
        main.main()
    out = capsys.readouterr()
    return int(exited.value.code or 0), out.out, out.err


def test_secrets_init_writes_each_secret_once_and_never_replaces_one(server, monkeypatch, capsys):
    code, out, _ = run(monkeypatch, capsys, "secrets", "init", "--json")
    assert code == 0
    written = json.loads(out)["written"]
    assert sorted(written) == [
        "byok_encryption_keys",
        "cron_secret",
        "database_password",
        "mcp_signing_secret",
    ]
    before = {p.name: p.read_text() for p in server.iterdir()}
    assert all(before.values())
    # Only the database password is readable by another user (Postgres's).
    modes = {p.name: stat.S_IMODE(p.stat().st_mode) for p in server.iterdir()}
    assert modes.pop("database_password") == 0o644
    assert set(modes.values()) == {0o600}
    # Nothing it printed is a secret.
    assert not any(value in out for value in before.values())

    code, out, _ = run(monkeypatch, capsys, "secrets", "init", "--json")
    assert code == 0 and json.loads(out)["written"] == []
    assert {p.name: p.read_text() for p in server.iterdir()} == before


def test_the_settings_read_secrets_from_the_directory_and_the_environment_wins(
    server, monkeypatch, capsys
):
    from salli.config import get_settings

    run(monkeypatch, capsys, "secrets", "init")
    import salli.config

    monkeypatch.setattr(salli.config, "_settings", None)
    settings = get_settings()
    assert settings.mcp_signing_secret == (server / "mcp_signing_secret").read_text()
    assert settings.database_password == (server / "database_password").read_text()

    monkeypatch.setenv("MCP_SIGNING_SECRET", "from-the-environment")
    monkeypatch.setattr(salli.config, "_settings", None)
    assert get_settings().mcp_signing_secret == "from-the-environment"


def test_setup_makes_the_owner_once_and_members_are_added_listed_and_reset(
    server, monkeypatch, capsys, db
):
    run(monkeypatch, capsys, "secrets", "init")
    code, out, err = run(
        monkeypatch,
        capsys,
        "setup",
        "--email",
        "Owner@Example.org",
        "--currency",
        "sek",
        "--password-stdin",
        "--json",
        stdin=OWNER_PASSWORD + "\n",
    )
    assert code == 0, err
    made = json.loads(out)
    assert made["email"] == "owner@example.org" and made["env_written"] == []
    assert not (Path.cwd() / ".env").exists()
    assert OWNER_PASSWORD not in out + err
    assert scalar(db, "select base_currency from user_profiles") == "SEK"
    assert scalar(db, "select count(*) from accounts") > 0

    # Again: nothing asked, nothing new, the same owner.
    code, out, err = run(monkeypatch, capsys, "setup", "--json")
    assert code == 0, err
    assert json.loads(out)["user_id"] == made["user_id"]
    assert scalar(db, "select count(*) from logins") == 1

    # A weak password makes no member.
    code, out, err = run(
        monkeypatch,
        capsys,
        "members",
        "add",
        "kid@example.org",
        "--password-stdin",
        stdin="short\n",
    )
    assert code == 1 and "12 characters" in out + err
    code, out, err = run(
        monkeypatch,
        capsys,
        "members",
        "add",
        "partner@example.org",
        "--password-stdin",
        "--json",
        stdin="the partner's password\n",
    )
    assert code == 0, err
    code, out, _ = run(monkeypatch, capsys, "members", "list", "--json")
    assert [(m["email"], m["role"]) for m in json.loads(out)] == [
        ("owner@example.org", "owner"),
        ("partner@example.org", "member"),
    ]

    code, out, err = run(
        monkeypatch,
        capsys,
        "members",
        "reset-password",
        "partner@example.org",
        "--password-stdin",
        "--sign-out-everywhere",
        "--clear-totp",
        "--json",
        stdin="a brand new password\n",
    )
    assert code == 0, err
    assert json.loads(out)["revoked"] == {
        "sessions": 0,
        "oauth_tokens": 0,
        "personal_access_tokens": 0,
    }
    # They had no two-step sign-in to turn off.
    assert json.loads(out)["totp_cleared"] is False
    code, out, err = run(
        monkeypatch,
        capsys,
        "members",
        "reset-password",
        "nobody@example.org",
        "--password-stdin",
        stdin="a brand new password\n",
    )
    assert code == 1 and "No account here" in out + err


def test_doctor_says_when_there_is_no_owner_yet(server, monkeypatch, capsys):
    run(monkeypatch, capsys, "secrets", "init")
    run(monkeypatch, capsys, "db", "upgrade")
    code, out, _ = run(monkeypatch, capsys, "doctor", "--json")
    checks = {c["name"]: c for c in json.loads(out)["checks"]}
    assert checks["Owner"]["status"] == "warn"
    assert checks["Authentication"] == {
        "name": "Authentication",
        "status": "ok",
        "detail": "Salli's own accounts",
    }
    assert code == 0
