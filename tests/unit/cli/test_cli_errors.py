"""What the `salli` command says when something is missing or did not happen."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from salli.interfaces.cli import main as cli_main


def _run(monkeypatch, services, *argv: str) -> int:
    monkeypatch.setenv("SALLI_USER_ID", "u1")
    monkeypatch.setattr(cli_main, "_services", lambda: services)
    monkeypatch.setattr(sys, "argv", ["salli", *argv])
    with pytest.raises(SystemExit) as exited:
        cli_main.main()
    return int(exited.value.code or 0)


def test_mcp_revoke_says_when_nothing_was_disconnected(monkeypatch, capsys):
    oauth = SimpleNamespace(
        list_connections=AsyncMock(return_value=[{"token_id": "tok-123456789"}]),
        revoke_connection=AsyncMock(return_value=False),
    )
    code = _run(monkeypatch, SimpleNamespace(mcp_oauth=oauth), "mcp", "revoke", "tok-1234")
    assert code == 1
    assert "Disconnected" not in capsys.readouterr().out
    oauth.revoke_connection.assert_awaited_once_with("u1", "tok-123456789")


def test_mcp_revoke_reports_success(monkeypatch, capsys):
    oauth = SimpleNamespace(
        list_connections=AsyncMock(return_value=[{"token_id": "tok-123456789"}]),
        revoke_connection=AsyncMock(return_value=True),
    )
    assert _run(monkeypatch, SimpleNamespace(mcp_oauth=oauth), "mcp", "revoke", "tok-1234") == 0
    assert "Disconnected" in capsys.readouterr().out
