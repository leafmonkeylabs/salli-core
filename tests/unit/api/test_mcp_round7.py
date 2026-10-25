"""
What an agent needs over MCP alone: the portfolio's performance, pages of
the longer lists, a statement imported for review, and a write that is not
made twice when sent again with the same client_ref.
"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salli.interfaces.api import mcp_server

pytestmark = pytest.mark.asyncio


class _Refs:
    """mcp_client_refs in memory."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str], dict[str, Any] | None] = {}

    async def claim(self, user_id: str, tool: str, ref: str) -> dict[str, Any] | None:
        key = (user_id, tool, ref)
        if key in self.rows:
            return self.rows[key] or {}
        self.rows[key] = None
        return None

    async def settle(self, user_id: str, tool: str, ref: str, result: dict[str, Any]) -> None:
        self.rows[(user_id, tool, ref)] = result

    async def release(self, user_id: str, tool: str, ref: str) -> None:
        self.rows.pop((user_id, tool, ref), None)


@pytest.fixture
def services():
    services = MagicMock()
    for name in ("ledger", "reminders", "portfolio", "decisions", "parsing", "documents"):
        setattr(services, name, AsyncMock())
    services.refs = _Refs()
    unit = MagicMock()
    unit.__aenter__ = AsyncMock(
        return_value=SimpleNamespace(
            audit_log=SimpleNamespace(log=AsyncMock()), client_refs=services.refs
        )
    )
    unit.__aexit__ = AsyncMock(return_value=False)
    services.ledger._uow_factory = MagicMock(return_value=unit)
    return services


async def _call(services: Any, tool: str, args: dict[str, Any]) -> Any:
    server = mcp_server.build_mcp_server(services, "https://api.test")
    with (
        patch.object(mcp_server, "_current_user_id", return_value="u1"),
        patch.object(mcp_server, "_current_client_id", return_value="claude-1"),
        patch.object(mcp_server, "_current_scopes", return_value=["mcp:write"]),
    ):
        _, structured = await server.call_tool(tool, args)
    return structured


async def test_a_write_sent_again_with_its_client_ref_is_made_once(services):
    services.reminders.create_reminder.return_value = "r1"
    args = {"description": "Renew the lease", "due_date": "2031-03-01", "client_ref": "abc"}
    first = await _call(services, "create_reminder", args)
    again = await _call(services, "create_reminder", args)
    assert first["reminder_id"] == again["reminder_id"] == "r1"
    assert again["already_done"] is True and "already_done" not in first
    services.reminders.create_reminder.assert_awaited_once()
    await _call(services, "create_reminder", {**args, "client_ref": "def"})
    assert services.reminders.create_reminder.await_count == 2


async def test_a_failed_write_frees_its_client_ref(services):
    services.ledger.base_currency.return_value = "EUR"
    services.ledger.add_account.side_effect = [ValueError("code taken"), "a1"]
    args = {"code": "1000", "name": "Bank", "account_type": "asset", "client_ref": "x"}
    with pytest.raises(mcp_server.ToolFailure):
        await _call(services, "create_account", args)
    assert (await _call(services, "create_account", args))["account_id"] == "a1"


async def test_the_longer_lists_come_in_pages(services):
    services.decisions.list.return_value = {"decisions": [{"id": str(i)} for i in range(5)]}
    first = await _call(services, "list_decisions", {"limit": 2})
    assert [d["id"] for d in first["decisions"]] == ["0", "1"] and first["next_cursor"] == "2"
    last = await _call(services, "list_decisions", {"limit": 2, "cursor": "4"})
    assert [d["id"] for d in last["decisions"]] == ["4"] and last["next_cursor"] is None


async def test_portfolio_performance_is_salli_s(services):
    services.portfolio.get_performance.return_value = {"portfolio": {"return": "0.05"}}
    got = await _call(services, "get_portfolio_performance", {"from_date": "2031-01-01"})
    assert got == {"portfolio": {"return": "0.05"}}
    services.portfolio.get_performance.assert_awaited_once_with(
        "u1", "2031-01-01", None, None, benchmark=None, cash_yield=None
    )


async def test_a_statement_is_imported_for_review_only_once_the_user_said_yes(services):
    raw = SimpleNamespace(
        date="2031-03-02",
        description="Corner Bakery",
        amount="8.40",
        currency="EUR",
        credit_flag=False,
    )
    services.parsing.parse_statement.return_value = SimpleNamespace(
        statement_id="s1",
        errors=[],
        transactions=[SimpleNamespace(id="t1", raw=raw, duplicate_of=None)],
    )
    data = base64.b64encode(b"date,amount\n").decode()
    got = await _call(
        services,
        "import_statement",
        {"file_base64": data, "format": "csv", "confirmed_by_user": True},
    )
    assert got["statement_id"] == "s1" and got["parsed"] == 1
    assert got["transactions"][0]["description"] == {"untrusted_text": "Corner Bakery"}
    kwargs = services.parsing.parse_statement.await_args.kwargs
    assert kwargs["filename"] == "statement.csv" and kwargs["file_bytes"] == b"date,amount\n"
