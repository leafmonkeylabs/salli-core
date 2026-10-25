"""
What an agent needs over MCP alone, again: every write that adds kept once
under its client_ref (and a statement once under its file), every list in
pages, and the monthly budget and debts written as the API writes them.
"""

from __future__ import annotations

import base64
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from salli.interfaces.api import mcp_server
from tests.unit.api.test_mcp_round7 import _call, services  # noqa: F401 -- the fixture

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("experimental_on")]

STATEMENT = base64.b64encode(b"date,description,amount\n2031-01-02,Rent,-900.00\n").decode()

#: A write, the arguments it takes, and the service call it makes.
WRITES: list[tuple[str, dict[str, Any], str]] = [
    (
        "recategorise_entry",
        {
            "entry_id": "e1",
            "posting_id": "p1",
            "account_id": "a2",
            "reason": "Groceries, not dining",
            "confirmed_by_user": True,
        },
        "ledger.recategorise_entry",
    ),
    ("update_document", {"doc_id": "d1", "title": "Lease"}, "documents.update_document"),
    ("save_memory", {"slug": "accountant", "value": "Ana"}, "documents.save_memory"),
    (
        "create_rule",
        {"name": "Rent", "description_contains": "RENT", "account_id": "a1"},
        "rules.create",
    ),
    (
        "import_statement",
        {"file_base64": STATEMENT, "confirmed_by_user": True, "format": "csv"},
        "parsing.parse_statement",
    ),
    (
        "set_monthly_budget",
        {
            "lines": [{"account_id": "a1", "limit_amount": "400.00"}],
            "confirmed_by_user": True,
        },
        "budget.set_monthly_lines",
    ),
    (
        "add_debt",
        {
            "name": "Card",
            "principal": "1200.00",
            "apr": "0.19",
            "minimum_payment": "35.00",
            "confirmed_by_user": True,
        },
        "debt.add_debt",
    ),
    (
        "update_debt",
        {"debt_id": "d1", "apr": "0.17", "confirmed_by_user": True},
        "debt.update_debt",
    ),
]


@pytest.fixture
def ready(services):  # noqa: F811 -- the fixture
    for name in ("rules", "budget", "debt"):
        setattr(services, name, AsyncMock())
    services.ledger.recategorise_entry.return_value = {"reversed_by": "e2", "entry_id": "e3"}
    services.rules.create.return_value = "r1"
    services.parsing.parse_statement.return_value = AsyncMock(
        statement_id="s1", transactions=[], errors=[]
    )
    services.budget.set_monthly_lines.return_value = {"currency": "EUR", "lines": []}
    services.debt.add_debt.return_value = "d1"
    services.debt.get_debt.return_value = {"id": "d1"}
    return services


def _service(of: Any, path: str) -> AsyncMock:
    owner, method = path.split(".")
    return getattr(getattr(of, owner), method)


@pytest.mark.parametrize(("tool", "args", "service"), WRITES)
async def test_each_write_sent_again_with_its_client_ref_is_made_once(ready, tool, args, service):
    sent = {**args, "client_ref": "ref-1"}
    first = await _call(ready, tool, sent)
    again = await _call(ready, tool, sent)
    assert again["already_done"] is True and "already_done" not in first
    _service(ready, service).assert_awaited_once()


async def test_a_statement_sent_again_without_a_ref_is_imported_once(ready):
    args = {"file_base64": STATEMENT, "confirmed_by_user": True}
    await _call(ready, "import_statement", args)
    again = await _call(ready, "import_statement", {**args, "client_ref": "another"})
    assert again["already_done"] is True and again["statement_id"] == "s1"
    ready.parsing.parse_statement.assert_awaited_once()
    # the same file for another account is another statement
    await _call(ready, "import_statement", {**args, "account_id": "a9"})
    assert ready.parsing.parse_statement.await_count == 2


async def test_every_list_tool_comes_in_pages(services):  # noqa: F811 -- the fixture
    server = mcp_server.build_mcp_server(services, "https://api.test", experimental_tools=True)
    lists = [t for t in await server.list_tools() if t.name.startswith("list_")]
    assert len(lists) >= 14
    for tool in lists:
        assert {"limit", "cursor"} <= set(tool.inputSchema["properties"]), tool.name


async def test_a_list_pages_its_items_and_keeps_the_rest(ready):
    ready.principles = AsyncMock()
    ready.principles.list.return_value = {"principles": [{"id": str(i)} for i in range(3)]}
    ready.principles.figures = lambda: {"figures": ["emergency_months"]}
    page = await _call(ready, "list_principles", {"limit": 2})
    assert [p["id"] for p in page["principles"]] == ["0", "1"] and page["next_cursor"] == "2"
    assert page["figures"] == ["emergency_months"]
    rest = await _call(ready, "list_principles", {"limit": 2, "cursor": "2"})
    assert [p["id"] for p in rest["principles"]] == ["2"] and rest["next_cursor"] is None


async def test_the_budget_and_debts_are_written_as_the_api_writes_them(ready):
    await _call(ready, "set_monthly_budget", dict(WRITES[5][1]))
    ready.budget.set_monthly_lines.assert_awaited_once_with(
        "u1", [{"account_id": "a1", "limit_amount": "400.00", "rollover": False}]
    )
    assert await _call(ready, "add_debt", dict(WRITES[6][1])) == {"debt_id": "d1"}
    added = ready.debt.add_debt.await_args.args[1]
    assert added["principal"] == Decimal("1200.00") and added["account_id"] is None
    changed = await _call(ready, "update_debt", dict(WRITES[7][1]))
    assert changed == {"debt_id": "d1", "updated": ["apr"]}
    ready.debt.update_debt.assert_awaited_once_with("u1", "d1", {"apr": Decimal("0.17")})
    ready.debt.get_debt.return_value = None
    with pytest.raises(mcp_server.ToolFailure, match="Debt not found"):
        await _call(ready, "update_debt", dict(WRITES[7][1]))


async def test_the_budget_and_debt_writes_need_the_person_s_yes_and_the_planning_part():
    for tool in ("set_monthly_budget", "add_debt", "update_debt"):
        assert mcp_server.WRITE_PARTS[tool] == "mcp:planning"
    server = mcp_server.build_mcp_server(AsyncMock(), "https://api.test")
    listed = {t.name: t for t in await server.list_tools()}
    for tool in ("set_monthly_budget", "add_debt", "update_debt"):
        assert "confirmed_by_user" in listed[tool].inputSchema["required"], tool
