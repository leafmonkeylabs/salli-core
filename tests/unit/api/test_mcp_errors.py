"""
How an MCP tool fails: an error result (isError true) whose `error` has a
code an agent can act on, a short message, whether to try again and, for
input, the paths of the problems. A malformed amount is invalid_input naming
its field, never a crash's raw text. And the tool list stays small enough
to send on every turn.
"""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types

from salli.application.ports import AccountNotFound, FxUnavailableError
from salli.application.services.tax_rule_service import RuleSetStateError
from salli.application.services.tax_service import NoTaxRulesError
from salli.domain.accounting.models import BooksLocked
from salli.domain.scenarios.engine import ScenarioError
from salli.interfaces.api import mcp_server

pytestmark = pytest.mark.asyncio

ENTRY = {
    "entry_date": "2026-10-24",
    "description": "Corner Bakery",
    "debit_account_id": "food",
    "credit_account_id": "cash",
    "amount": "8.40",
}


@pytest.fixture
def services():
    services = MagicMock()
    services.ledger = AsyncMock()
    services.ledger.base_currency.return_value = "EUR"
    audit = SimpleNamespace(log=AsyncMock())
    unit = MagicMock()
    unit.__aenter__ = AsyncMock(return_value=SimpleNamespace(audit_log=audit))
    unit.__aexit__ = AsyncMock(return_value=False)
    services.ledger._uow_factory = MagicMock(return_value=unit)
    services.audit = audit
    return services


async def _request(services: Any, tool: str, args: dict[str, Any]) -> types.CallToolResult:
    """A tools/call as a client sends it, on a connection that may change."""
    server = mcp_server.build_mcp_server(services, "https://api.test")
    handler = server._mcp_server.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        method="tools/call", params=types.CallToolRequestParams(name=tool, arguments=args)
    )
    with (
        patch.object(mcp_server, "_current_user_id", return_value="u1"),
        patch.object(mcp_server, "_current_client_id", return_value="claude-1"),
        patch.object(mcp_server, "_current_scopes", return_value=["mcp:write"]),
    ):
        result = await handler(request)
    return result.root


def _error(result: types.CallToolResult) -> dict[str, Any]:
    assert result.isError is True
    assert result.structuredContent is not None
    [text] = result.content
    assert isinstance(text, types.TextContent)
    assert json.loads(text.text) == result.structuredContent
    return result.structuredContent["error"]


@pytest.mark.parametrize(("field", "value"), [("amount", "1O.00"), ("fx_rate", "1,2")])
async def test_a_malformed_amount_is_invalid_input_naming_its_field(services, field, value):
    error = _error(await _request(services, "post_journal_entry", {**ENTRY, field: value}))
    assert error == {
        "code": "invalid_input",
        "message": f"{field} is a decimal string, such as '1200.50', not {value!r}",
        "retryable": False,
        "problems": [{"path": field, "message": "not a decimal string"}],
    }
    services.ledger.add_entry.assert_not_called()
    assert services.audit.log.await_args.args[3] == "failed"


async def test_a_service_s_refusal_is_coded(services):
    services.ledger.add_entry.side_effect = AccountNotFound(["theirs"])
    error = _error(await _request(services, "post_journal_entry", ENTRY))
    assert (error["code"], error["message"]) == ("not_found", "Account not found: theirs")


async def test_arguments_that_do_not_fit_are_invalid_input(services):
    error = _error(await _request(services, "post_journal_entry", {"amount": "8.40"}))
    assert error["code"] == "invalid_input"
    assert {p["path"] for p in error["problems"]} >= {"entry_date", "description"}


async def test_a_tool_that_does_not_exist_is_not_found(services):
    assert _error(await _request(services, "get_everything", {}))["code"] == "not_found"


async def test_a_model_that_fails_may_be_tried_again(services):
    from salli.domain.llm import LLMError

    services.advisor = AsyncMock()
    services.advisor.run_advisor.side_effect = LLMError("The model is busy")
    error = _error(await _request(services, "run_briefing", {}))
    assert (error["code"], error["retryable"]) == ("unavailable", True)


async def test_an_answer_is_not_an_error(services):
    services.ledger.add_entry.return_value = "e1"
    result = await _request(services, "post_journal_entry", ENTRY)
    assert result.isError is False
    assert result.structuredContent == {"entry_id": "e1", "posted": True}


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (NoTaxRulesError("no_rule_set", "No tax rules"), "not_enough_data"),
        (FxUnavailableError("No EUR/NZD rate"), "not_enough_data"),
        (AccountNotFound(["x"]), "not_found"),
        (RuleSetStateError("superseded"), "refused"),
        (BooksLocked("2026-01-01", "2026-03-31"), "refused"),
        (ScenarioError([]), "invalid_input"),
        (ValueError("No"), "invalid_input"),
    ],
)
async def test_a_refusal_is_coded_by_its_kind(exc: Exception, code: str):
    with pytest.raises(mcp_server.ToolFailure) as failure:
        mcp_server._refused(exc)
    assert failure.value.code == code
    assert failure.value.retryable is False


@pytest.mark.parametrize("value", ["1O.00", "", "NaN", "Infinity", "1e", "ten"])
async def test_only_a_decimal_string_is_read_as_one(value: str):
    with pytest.raises(mcp_server.ToolFailure) as failure:
        mcp_server._decimal(value, "amount")
    assert failure.value.code == "invalid_input"
    assert failure.value.problems == [{"path": "amount", "message": "not a decimal string"}]


async def test_a_decimal_string_is_read_exactly():
    assert mcp_server._decimal("-0.10", "amount") == Decimal("-0.10")


#: What every tool's name, description and input schema cost, sent on each
#: turn (it was 119 KB, with a scenario's schema written out in four tools;
#: 40 KB until the lists of budgets, debts, goals and reminders, and entries
#: by id and their reversal, were added; 42 KB until reconciliations, 43 KB
#: until the investment policy, 44 KB until every tool carried a title, as
#: the connector directories ask; 46.5 KB until portfolio performance, statement
#: import, pages of the longer lists and client_ref on four writes; 48.5 KB
#: until recategorising an entry).
TOOL_LIST_BUDGET = 49_000


async def test_the_tool_list_stays_small(services):
    tools = await mcp_server.build_mcp_server(services, "https://api.test").list_tools()
    listed = json.dumps(
        [t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in tools]
    )
    assert len(listed.encode()) < TOOL_LIST_BUDGET
    for tool in tools:
        assert tool.outputSchema is None and "\n" not in (tool.description or ""), tool.name
        assert "title" not in tool.inputSchema, tool.name
