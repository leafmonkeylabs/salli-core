"""What the `salli` command says when something is missing or did not happen."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from salli.application.ports import ProfileMissing
from salli.interfaces.cli import main as cli_main


def _run(monkeypatch, services, *argv: str) -> int:
    from salli.interfaces.cli import support

    # --json switches the process into JSON mode for good, and points the
    # console at stderr: both undone after. The console's own file is None
    # (whatever sys.stdout is at the time), never a captured stream.
    monkeypatch.setattr(support, "_json_mode", False)
    monkeypatch.setattr(support.console, "_file", None)
    monkeypatch.setenv("SALLI_USER_ID", "u1")
    monkeypatch.setattr(cli_main, "_services", lambda: services)
    monkeypatch.setattr(sys, "argv", ["salli", *argv])
    with pytest.raises(SystemExit) as exited:
        cli_main.main()
    return int(exited.value.code or 0)


@pytest.mark.parametrize(
    "argv",
    [("mcp", "enable"), ("mcp", "disable")],
)
def test_a_write_without_a_profile_says_to_onboard(monkeypatch, capsys, argv):
    # The repository raised ValueError("A new profile needs a base_currency"),
    # which the "no profile" handler did not catch: a traceback.
    oauth = SimpleNamespace(set_mcp_enabled=AsyncMock(side_effect=ProfileMissing("u1")))
    code = _run(monkeypatch, SimpleNamespace(mcp_oauth=oauth), *argv)
    out = capsys.readouterr().out
    assert code == 1
    assert "has no profile" in out and "salli onboarding complete" in out


def test_mcp_revoke_says_when_nothing_was_disconnected(monkeypatch, capsys):
    oauth = SimpleNamespace(
        list_connections=AsyncMock(return_value=[{"token_id": "connection-1"}]),
        revoke_connection=AsyncMock(return_value=False),
    )
    code = _run(monkeypatch, SimpleNamespace(mcp_oauth=oauth), "mcp", "revoke", "connection")
    assert code == 1
    assert "Disconnected" not in capsys.readouterr().out
    oauth.revoke_connection.assert_awaited_once_with("u1", "connection-1")


def test_mcp_revoke_reports_success(monkeypatch, capsys):
    oauth = SimpleNamespace(
        list_connections=AsyncMock(return_value=[{"token_id": "connection-1"}]),
        revoke_connection=AsyncMock(return_value=True),
    )
    assert _run(monkeypatch, SimpleNamespace(mcp_oauth=oauth), "mcp", "revoke", "connection") == 0
    assert "Disconnected" in capsys.readouterr().out


def test_parse_upload_says_why_it_was_refused(monkeypatch, capsys, tmp_path):
    # A non-money account, a currency mismatch or the usage meter ended in a
    # traceback.
    statement = tmp_path / "s.csv"
    statement.write_bytes(b"Date,Description,Amount\n13/10/2026,Coffee,-4.50\n")
    parsing = SimpleNamespace(
        parse_statement=AsyncMock(side_effect=ValueError("Food is an expense account."))
    )
    code = _run(monkeypatch, SimpleNamespace(parsing=parsing), "parse", "upload", str(statement))
    assert code == 1
    assert "Food is an expense account." in capsys.readouterr().out


def test_parse_pending_json_has_the_apis_field_names(monkeypatch, capsys):
    import json
    from decimal import Decimal

    from salli.domain.parsing.models import ParsedTransaction, RawRow

    row = RawRow("2026-10-13", "AMZN MKTP US*2K4", Decimal("12.00"), False, "USD")
    txn = ParsedTransaction(row, "", "checking", description="Amazon", id="t1")
    parsing = SimpleNamespace(get_pending=AsyncMock(return_value=[txn]))
    assert _run(monkeypatch, SimpleNamespace(parsing=parsing), "parse", "pending", "--json") == 0
    [shown] = json.loads(capsys.readouterr().out)
    assert (shown["description"], shown["description_override"]) == ("AMZN MKTP US*2K4", "Amazon")
