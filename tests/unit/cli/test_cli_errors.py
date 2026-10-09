"""What the `salli` command says when something is missing or did not happen."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from salli.application.ports import ProfileMissing
from salli.interfaces.cli import main as cli_main


def _run(monkeypatch, services, *argv: str) -> int:
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
