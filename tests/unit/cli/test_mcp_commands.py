"""`salli mcp connections` and `salli mcp revoke` name connections by their token id."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from typer.testing import CliRunner

from salli.interfaces.cli import main

CONNECTIONS = [
    {
        "token_id": "8f2a91c4-0000-4000-8000-000000000001",
        "client_id": "c1",
        "client_name": "Claude",
        "scope": "salli",
        "connected_at": datetime(2026, 10, 9, 8, 30, tzinfo=UTC),
    }
]


@pytest.fixture
def mcp(monkeypatch):
    oauth = SimpleNamespace(
        list_connections=AsyncMock(return_value=CONNECTIONS),
        revoke_connection=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(main, "_services", lambda: SimpleNamespace(mcp_oauth=oauth))
    monkeypatch.setattr(main, "_require_user", lambda: "u1")
    return oauth


def test_connections_show_their_id_and_when_they_connected(mcp):
    result = CliRunner().invoke(main.app, ["mcp", "connections"])
    assert result.exit_code == 0, result.output
    assert "8f2a91c4" in result.output and "Claude" in result.output
    assert "2026-10-09 08:30" in result.output


def test_a_connection_is_revoked_by_a_prefix_of_its_id(mcp):
    result = CliRunner().invoke(main.app, ["mcp", "revoke", "8f2a91c4"])
    assert result.exit_code == 0, result.output
    mcp.revoke_connection.assert_awaited_once_with("u1", CONNECTIONS[0]["token_id"])
