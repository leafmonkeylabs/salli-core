"""
The MCP tools and prompts that let a user's own AI client (Claude or ChatGPT,
on the user's plan) work with Salli: read insights and the forecast, sort
what was imported, and teach Salli rules. Salli computes; the client reasons.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salli.domain.parsing.models import ParsedTransaction, RawRow
from salli.domain.rules.engine import InvalidRule
from salli.interfaces.api import mcp_server

pytestmark = pytest.mark.asyncio


@pytest.fixture
def services():
    services = MagicMock()
    for name in ("insights", "parsing", "rules", "fi", "ledger"):
        setattr(services, name, AsyncMock())
    # The audit log is written through the ledger's unit of work.
    audit = SimpleNamespace(log=AsyncMock())
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=SimpleNamespace(audit_log=audit))
    uow.__aexit__ = AsyncMock(return_value=False)
    services.ledger._uow_factory = MagicMock(return_value=uow)
    services.audit = audit
    return services


async def _call(services, tool: str, args: dict):
    server = mcp_server.build_mcp_server(services, "https://api.test")
    with patch.object(mcp_server, "_current_user_id", return_value="u1"):
        _, structured = await server.call_tool(tool, args)
    return structured


async def test_insights_and_the_forecast_are_salli_s_numbers(services):
    services.insights.forecast.return_value = {"currency": "USD", "lowest": "240.00"}
    assert await _call(services, "get_cash_forecast", {"days": 9999}) == {
        "currency": "USD",
        "lowest": "240.00",
    }
    services.insights.forecast.assert_awaited_once_with("u1", 366)  # at most a year

    services.insights.spending.return_value = {"lines": []}
    await _call(services, "get_spending", {"months": 6, "by": "need"})
    services.insights.spending.assert_awaited_once_with("u1", 6, "need")
    assert await _call(services, "get_spending", {"by": "mood"}) == {
        "error": "by is category, account or need"
    }


async def test_pending_transactions_say_what_is_decided_and_what_is_not(services):
    services.parsing.get_pending.return_value = [
        ParsedTransaction(
            raw=RawRow("2026-10-05", "WHOLE FOODS", Decimal("84.17"), False, "USD"),
            debit_account_id="",
            credit_account_id="checking",
            id="t1",
            statement_id="s1",
            account_id="checking",
        )
    ]
    [txn] = (await _call(services, "list_pending_transactions", {}))["transactions"]
    assert (txn["id"], txn["amount"], txn["money_in"]) == ("t1", "84.17", False)
    assert (txn["statement_account_id"], txn["debit_account_id"]) == ("checking", None)


async def test_choices_are_validated_by_salli_and_audited(services):
    services.parsing.categorize.return_value = ["t1"]
    result = await _call(
        services,
        "categorize_transactions",
        {"choices": [{"transaction_id": "t1", "account_id": "food", "need": "essential"}]},
    )
    assert result == {"updated": ["t1"]}
    services.parsing.categorize.assert_awaited_once_with(
        "u1", [{"transaction_id": "t1", "account_id": "food", "need": "essential"}]
    )
    services.audit.log.assert_awaited()

    services.parsing.categorize.side_effect = ValueError("No active account 'made-up'")
    refused = await _call(
        services,
        "categorize_transactions",
        {"choices": [{"transaction_id": "t1", "account_id": "made-up"}]},
    )
    assert refused == {"error": "No active account 'made-up'"}


async def test_posting_books_exactly_what_was_approved(services):
    services.parsing.post_approved.return_value = ["e1"]
    result = await _call(services, "post_transactions", {"transaction_ids": ["t1"]})
    assert result == {"posted": 1, "entry_ids": ["e1"]}
    services.parsing.post_approved.assert_awaited_once_with("u1", ["t1"])


async def test_a_rule_is_a_description_and_an_account(services):
    services.rules.create.return_value = "r1"
    result = await _call(
        services,
        "create_rule",
        {"name": "Uber", "description_contains": "uber", "account_id": "transport"},
    )
    assert result == {"rule_id": "r1"}
    [user_id, rule] = services.rules.create.await_args.args
    assert user_id == "u1"
    assert rule["conditions"] == [{"field": "description", "operator": "contains", "value": "uber"}]
    assert rule["actions"] == {"account_id": "transport"}

    services.rules.create.side_effect = InvalidRule("The rule's account doesn't exist")
    refused = await _call(
        services, "create_rule", {"name": "x", "description_contains": "x", "account_id": "no"}
    )
    assert refused == {"error": "The rule's account doesn't exist"}


async def test_the_prompts_lean_on_salli_s_tools_not_the_model_s_arithmetic():
    server = mcp_server.build_mcp_server(MagicMock(), "https://api.test")
    review = await server.get_prompt("review_my_month", {"month": "October"})
    text = review.messages[0].content.text  # type: ignore[union-attr]
    assert "October" in text and "get_cash_forecast" in text and "never compute" in text

    afford = await server.get_prompt("can_i_afford", {"amount": "2000 USD", "what": "a trip"})
    text = afford.messages[0].content.text  # type: ignore[union-attr]
    assert "simulate_purchase" in text and "never your own arithmetic" in text

    sort = await server.get_prompt("sort_pending_transactions", {})
    text = sort.messages[0].content.text  # type: ignore[union-attr]
    assert "Only after I approve" in text and "never invent" in text
