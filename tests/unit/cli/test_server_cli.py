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


@pytest.fixture(autouse=True)
def plain_output(monkeypatch):
    # --json switches the process into JSON mode for good and points the
    # console at stderr: undo both for each test.
    monkeypatch.setattr(support, "_json_mode", False)
    monkeypatch.setattr(support.console, "_file", None)


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
        "doctor",
        "db upgrade",
        "db current",
        "members add",
        "jobs run-advisor",
        "jobs sync-banks",
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
        "year": "2025/26",
        "changed": True,
        "applied": False,
        "old_credits": "0.00",
        "new_credits": "1200.00",
        "old_tax_payable": "5000.00",
        "new_tax_payable": "3800.00",
        "new_refund_due": "0.00",
    }
    tax = SimpleNamespace(recompute_stored=AsyncMock(return_value=[row]))
    monkeypatch.setattr(jobs, "services", lambda: SimpleNamespace(tax=tax))
    result = _run(monkeypatch, capsys, "jobs", "recompute-tax")
    assert result.exit_code == 0, result.output
    assert "Dry run: nothing written" in result.output and "--apply" in result.output
    tax.recompute_stored.assert_awaited_once_with(apply=False)

    assert _run(monkeypatch, capsys, "jobs", "recompute-tax", "--apply").exit_code == 0
    tax.recompute_stored.assert_awaited_with(apply=True)


# ── doctor ────────────────────────────────────────────────────────────────────


def test_doctor_says_whether_a_secret_is_set_never_what_it_is():
    from salli.config import Settings

    secrets = {
        "supabase_jwt_secret": "jwt-secret-value",
        "mcp_signing_secret": "mcp-secret-value",
        "cron_secret": "cron-secret-value",
        "byok_encryption_keys": "1:Ynlvay1rZXktdmFsdWU=",
        "anthropic_api_key": "sk-ant-secret-value",
    }
    settings = Settings(_env_file=None, supabase_url="https://auth.example.com", **secrets)
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


def test_doctor_fails_without_authentication():
    from salli.config import Settings

    [auth] = [
        c for c in doctor.config_checks(Settings(_env_file=None)) if c.name == "Authentication"
    ]
    assert auth.status == "fail"


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
