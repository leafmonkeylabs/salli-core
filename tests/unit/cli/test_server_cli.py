"""`salli-server`: the operator's command line, and the surface extensions build on."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import typer

from salli.interfaces.cli import doctor, jobs, main, support
from salli.interfaces.cli.support import leaf_commands

ROOT = Path(__file__).resolve().parents[3]


def plain_output(monkeypatch):
    # --json switches the process into JSON mode for good and points the
    # console at stderr: undo both for each test.
    monkeypatch.setattr(support, "_json_mode", False)
    monkeypatch.setattr(support.console, "_file", None)


@pytest.fixture(autouse=True)
def _plain(monkeypatch):
    plain_output(monkeypatch)


def _commands() -> set[str]:
    return {" ".join(path) for path, _ in leaf_commands(main.cli())}


class Ran(SimpleNamespace):
    exit_code: int
    stdout: str
    output: str


def _run(monkeypatch, capsys, *argv: str) -> Ran:
    """Runs the real entry point, as `salli-server ...` would: through `cli()`,
    which adds --json."""
    monkeypatch.setattr(sys, "argv", ["salli-server", *argv])
    with pytest.raises(SystemExit) as exited:
        main.main()
    captured = capsys.readouterr()
    return Ran(
        exit_code=int(exited.value.code or 0),
        stdout=captured.out,
        output=captured.out + captured.err,
    )


def test_the_only_console_script_is_salli_server():
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
    assert scripts == {"salli-server": "salli.interfaces.cli.main:main"}


def test_the_server_has_only_operator_commands():
    # A person's own finances are the TypeScript CLI's, over the API.
    assert _commands() == {
        "setup",
        "serve",
        "stats",
        "doctor",
        "db upgrade",
        "db current",
        "audit verify",
        "members add",
        "members invite",
        "members list",
        "members reset-password",
        "secrets init",
        "jobs run-advisor",
        "jobs sync-banks",
        "jobs send-digests",
        "jobs send-usage",
        "jobs recompute-tax",
    }


def test_every_command_takes_json():
    for path, command in leaf_commands(main.cli()):
        assert any(
            p.name == "json" or "--json" in getattr(p, "opts", []) for p in command.params
        ), path


def test_the_names_extensions_import_stay_put():
    # A deployment's own commands and tests import these; renaming one breaks it.
    for name in ("console", "emit", "json_mode", "require_user", "services", "leaf_commands"):
        assert callable(getattr(support, name)) or name == "console", name
    assert isinstance(main.app, typer.Typer)
    assert callable(main.cli)


def test_an_extensions_command_groups_are_mounted(monkeypatch, capsys):
    group = typer.Typer()

    @group.command("adopt")
    def adopt() -> None:
        support.emit({"adopted": True})

    spec = SimpleNamespace(name="example", cli_groups=(("example", group),))
    monkeypatch.setattr("salli.extensions.enabled_specs", lambda settings: [spec])
    before = list(main.app.registered_groups)
    try:
        main._add_extension_groups()
        assert "example adopt" in _commands()
        result = _run(monkeypatch, capsys, "example", "adopt", "--json")
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {"adopted": True}
    finally:
        main.app.registered_groups[:] = before


def test_a_command_acting_as_a_user_without_a_profile_says_what_to_do(monkeypatch, capsys):
    from salli.application.ports import ProfileMissing

    group = typer.Typer()

    @group.command("whoami")
    def whoami() -> None:
        raise ProfileMissing("u1")

    before = list(main.app.registered_groups)
    main.app.add_typer(group, name="example")
    monkeypatch.setattr(sys, "argv", ["salli-server", "example", "whoami"])
    try:
        with pytest.raises(SystemExit) as exited:
            main.main()
    finally:
        main.app.registered_groups[:] = before
    assert exited.value.code == 1
    assert "salli-server setup" in capsys.readouterr().out


# ── jobs ──────────────────────────────────────────────────────────────────────


def test_the_advisor_job_runs_for_each_due_user_and_counts_refusals(monkeypatch, capsys):
    from salli.domain.usage import AIAction, UsageLimitReached

    async def run_advisor(user_id, _, trigger):
        assert trigger == "scheduled"
        if user_id == "u2":
            raise UsageLimitReached(AIAction.ADVISOR_RUN, message="Out of advisor runs")

    advisor = SimpleNamespace(
        due_users=AsyncMock(return_value=[{"user_id": "u1"}, {"user_id": "u2"}]),
        run_advisor=run_advisor,
    )
    monkeypatch.setattr(jobs, "services", lambda: SimpleNamespace(advisor=advisor))
    result = _run(monkeypatch, capsys, "jobs", "run-advisor", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"due": 2, "ran": ["u1"], "refused": ["u2"], "failed": []}


def test_the_advisor_job_fails_when_a_run_fails_without_quoting_it(monkeypatch, capsys):
    advisor = SimpleNamespace(
        due_users=AsyncMock(return_value=[{"user_id": "u1"}]),
        run_advisor=AsyncMock(side_effect=RuntimeError("salary 5000 for Sam")),
    )
    monkeypatch.setattr(jobs, "services", lambda: SimpleNamespace(advisor=advisor))
    result = _run(monkeypatch, capsys, "jobs", "run-advisor")
    assert result.exit_code == 1
    assert "RuntimeError" in result.output and "salary" not in result.output


def test_the_bank_job_passes_the_age_and_fails_when_a_sync_failed(monkeypatch, capsys):
    import datetime

    counts = {"due": 3, "synced": 2, "failed": 1, "skipped": 0}
    banks = SimpleNamespace(sync_due=AsyncMock(return_value=counts))
    monkeypatch.setattr(jobs, "services", lambda: SimpleNamespace(bank_connections=banks))
    result = _run(monkeypatch, capsys, "jobs", "sync-banks", "--max-age-hours", "6")
    assert result.exit_code == 1
    assert "2 of 3 synced, 1 failed" in result.output
    banks.sync_due.assert_awaited_once_with(datetime.timedelta(hours=6))


def test_the_tax_job_is_a_dry_run_unless_told_to_apply(monkeypatch, capsys):
    row = {
        "user_id": "u1aaaaaaaa",
        "country": "XG",
        "region": None,
        "year": "2031/32",
        "old_version": 1,
        "new_version": 2,
        "currency": "KWD",
        "changed": True,
        "applied": False,
        "reproduces": True,
        "old_tax_payable": "5000.000",
        "new_tax_payable": "3800.000",
        "old_refund_due": "0.000",
        "new_refund_due": "0.000",
    }
    tax = SimpleNamespace(recompute_stored=AsyncMock(return_value=[row]))
    monkeypatch.setattr(jobs, "services", lambda: SimpleNamespace(tax=tax))
    result = _run(monkeypatch, capsys, "jobs", "recompute-tax")
    assert result.exit_code == 0, result.output
    assert "Dry run: nothing written" in result.output and "--apply" in result.output
    assert "XG" in result.output and "1 changed" in result.output
    tax.recompute_stored.assert_awaited_once_with(apply=False)

    assert _run(monkeypatch, capsys, "jobs", "recompute-tax", "--apply").exit_code == 0
    tax.recompute_stored.assert_awaited_with(apply=True)


def _digest_counts(**over: object) -> dict[str, object]:
    return {
        "notifier": "mailer",
        "due": 3,
        "sent": 2,
        "nothing_waiting": 1,
        "no_destination": 0,
        "failed": 0,
        "skipped": 0,
        **over,
    }


def test_the_digest_job_sends_what_is_due_and_counts_it(monkeypatch, capsys):
    notifications = SimpleNamespace(send_due=AsyncMock(return_value=_digest_counts()))
    monkeypatch.setattr(jobs, "services", lambda: SimpleNamespace(notifications=notifications))
    result = _run(monkeypatch, capsys, "jobs", "send-digests", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == _digest_counts()
    plain_output(monkeypatch)
    plain = _run(monkeypatch, capsys, "jobs", "send-digests")
    assert "Due: 3 · sent 2 · nothing waiting 1" in plain.output


def test_the_digest_job_fails_when_a_send_failed(monkeypatch, capsys):
    notifications = SimpleNamespace(send_due=AsyncMock(return_value=_digest_counts(failed=1)))
    monkeypatch.setattr(jobs, "services", lambda: SimpleNamespace(notifications=notifications))
    assert _run(monkeypatch, capsys, "jobs", "send-digests").exit_code == 1


def test_the_digest_job_without_a_notifier_says_so_and_succeeds(monkeypatch, capsys):
    counts = _digest_counts(notifier=None, due=0, sent=0, nothing_waiting=0)
    notifications = SimpleNamespace(send_due=AsyncMock(return_value=counts))
    monkeypatch.setattr(jobs, "services", lambda: SimpleNamespace(notifications=notifications))
    result = _run(monkeypatch, capsys, "jobs", "send-digests")
    assert result.exit_code == 0
    assert "No notifier is enabled" in result.output


def _notifications(name: str | None, last: object = None) -> SimpleNamespace:
    return SimpleNamespace(
        notifications=SimpleNamespace(
            sender_enabled=name is not None,
            notifier_name=name,
            last_run=AsyncMock(return_value=last),
        )
    )


def test_doctor_says_which_notifier_sends_and_whether_the_job_runs(monkeypatch):
    import datetime

    now = datetime.datetime.now(datetime.UTC)
    monkeypatch.setattr(support, "services", lambda: _notifications(None))
    none = doctor.notifications_check()
    assert (none.status, none.detail.startswith("no notifier enabled")) == ("ok", True)

    monkeypatch.setattr(support, "services", lambda: _notifications("mailer"))
    never = doctor.notifications_check()
    assert never.status == "warn"
    assert "mailer" in never.detail and "never" in never.detail
    assert "salli-server jobs send-digests" in never.detail

    stale = now - datetime.timedelta(days=2)
    monkeypatch.setattr(support, "services", lambda: _notifications("mailer", stale))
    assert doctor.notifications_check().status == "warn"

    monkeypatch.setattr(
        support, "services", lambda: _notifications("mailer", now - datetime.timedelta(hours=1))
    )
    ok = doctor.notifications_check()
    assert (ok.status, ok.detail) == (
        "ok",
        "notifier from mailer; the digest job ran in the last day",
    )


# ── doctor ────────────────────────────────────────────────────────────────────


def test_doctor_says_whether_a_secret_is_set_never_what_it_is():
    from salli.config import Settings

    secrets = {
        "mcp_signing_secret": "mcp-secret-value",
        "cron_secret": "cron-secret-value",
        "byok_encryption_keys": "1:Ynlvay1rZXktdmFsdWU=",
        "anthropic_api_key": "sk-ant-secret-value",
        "database_password": "db-password-value",
    }
    settings = Settings(_env_file=None, environment="production", **secrets)
    shown = json.dumps([c.detail for c in doctor.config_checks(settings)])
    for value in secrets.values():
        assert value not in shown
    assert all(c.status == "ok" for c in doctor.config_checks(settings))


def test_doctor_names_the_database_without_its_credentials():
    url = "postgresql+asyncpg://salli:hunter2@db.example.com:6543/salli"
    assert doctor.describe_database(url) == "postgresql+asyncpg://db.example.com:6543/salli"
    assert doctor._scrub(f"could not connect to {url} (password hunter2)", url) == (
        "could not connect to *** (password ***)"
    )


def test_doctor_warns_of_the_dev_fallback_and_a_development_environment():
    from salli.config import Settings

    def by_name(settings: Settings) -> dict[str, str]:
        return {c.name: c.status for c in doctor.config_checks(settings)}

    assert by_name(Settings(_env_file=None, environment="production"))["Authentication"] == "ok"
    dev = by_name(Settings(_env_file=None, salli_insecure_dev_auth=True))
    assert dev["Authentication"] == "warn" and dev["Environment"] == "warn"


def test_doctor_exits_non_zero_and_skips_migrations_when_the_database_is_down(monkeypatch, capsys):
    def unreachable(url):
        return doctor.Check("Database", "fail", "cannot reach it")

    monkeypatch.setattr(doctor, "database_check", unreachable)
    monkeypatch.setattr(doctor, "migration_checks", lambda settings: pytest.fail("checked"))
    result = _run(monkeypatch, capsys, "doctor", "--json")
    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["ok"] is False
    assert report["checks"][-1] == {
        "name": "Migrations",
        "status": "warn",
        "detail": "not checked: fix the database first",
    }


def test_doctor_says_whether_the_console_is_served(tmp_path):
    from salli.config import Settings

    def check(**settings: object) -> tuple[str, str]:
        result = doctor.console_check(Settings(_env_file=None, **settings))
        return result.status, result.detail

    assert check(salli_console=False) == ("ok", "switched off (SALLI_CONSOLE=false)")
    status, detail = check()
    assert status == "warn" and "SALLI_CONSOLE_DIR is not set" in detail
    status, detail = check(salli_console_dir=str(tmp_path))
    assert status == "warn" and "no index.html" in detail

    (tmp_path / "index.html").write_text("<!doctype html>")
    assert check(salli_console_dir=str(tmp_path), salli_public_url="https://money.example.org") == (
        "ok",
        "served at https://money.example.org/console",
    )
    assert check(salli_console_dir=str(tmp_path))[0] == "ok"  # localhost
    status, detail = check(salli_console_dir=str(tmp_path), salli_public_url="http://10.0.0.5:8000")
    assert status == "warn" and "HTTPS" in detail
