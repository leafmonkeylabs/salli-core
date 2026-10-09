"""`salli banks`: bank-supplied text is shown as text, and a sync of every
connection runs in one event loop."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from typer.testing import CliRunner

from salli.interfaces.cli import main

_CONNECTION = {
    "id": "c1aaaaaa",
    "provider": "simplefin",
    "name": "[bold red]Evil[/bold red] Bank",
    "status": "attention",
    "last_error": None,
    "warnings": ["[link=https://phish.test]Sign in[/link]"],
    "last_synced_at": datetime(2026, 10, 9, 8, 30, tzinfo=UTC),
    "created_at": datetime(2026, 10, 9, 8, 30, tzinfo=UTC),
    "accounts": [
        {
            "remote_id": "chk",
            "name": "[blink]Checking[/blink]",
            "institution": "",
            "currency": "USD",
            "balance": Decimal("1234.5"),
            "account_id": None,
            "notes": None,
        }
    ],
}


@pytest.fixture
def services(monkeypatch):
    loops: set[int] = set()

    async def listed(user_id):
        loops.add(id(asyncio.get_running_loop()))
        return [_CONNECTION]

    async def synced(user_id, connection_id):
        loops.add(id(asyncio.get_running_loop()))
        return {"accounts": [], "unmapped": [], "warnings": []}

    banks = SimpleNamespace(available=True, providers=["simplefin"], list=listed, sync=synced)
    ledger = SimpleNamespace(list_accounts=AsyncMock(return_value=[]))
    svc = SimpleNamespace(bank_connections=banks, ledger=ledger)
    monkeypatch.setattr(main, "_services", lambda: svc)
    monkeypatch.setattr(main, "_require_user", lambda: "u1")
    return loops


def test_bank_names_and_warnings_are_not_markup(services):
    result = CliRunner().invoke(main.app, ["banks", "list"])
    assert result.exit_code == 0, result.output
    assert "[bold red]Evil[/bold red] Bank" in result.output
    assert "[link=https://phish.test]Sign in[/link]" in result.output
    assert "1,234.50 USD" in result.output  # format_amount, as every inline amount


def test_syncing_every_connection_uses_one_event_loop(services):
    # The listing and the syncs ran in two asyncio.run calls with one
    # services object: "attached to a different loop".
    result = CliRunner().invoke(main.app, ["banks", "sync"])
    assert result.exit_code == 0, result.output
    assert len(services) == 1


def test_the_sync_help_names_commands_that_exist():
    result = CliRunner().invoke(main.app, ["banks", "sync", "--help"])
    assert "parse review" not in result.output and "parse pending" in result.output
