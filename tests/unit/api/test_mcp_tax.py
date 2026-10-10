"""The MCP tax tools: the user's tax from their own active rules, each line
explained, and a rule set's suggested accounts. There is no built-in
country, no pack to list and no band to explain."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salli.application.services.tax_rule_service import RuleSetStateError
from salli.application.services.tax_service import ADD_RULES, NoTaxRulesError
from salli.domain.taxrules.explain import UnknownLine
from salli.interfaces.api import mcp_server
from tests.tax_views import computation_view

pytestmark = pytest.mark.asyncio


@pytest.fixture
def services():
    services = MagicMock()
    services.tax = AsyncMock()
    services.tax_rules = AsyncMock()
    services.mcp_oauth = AsyncMock()
    services.mcp_oauth.client_name.return_value = "Claude"
    services.ledger = AsyncMock()
    audit = SimpleNamespace(log=AsyncMock())
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=SimpleNamespace(audit_log=audit))
    uow.__aexit__ = AsyncMock(return_value=False)
    services.ledger._uow_factory = MagicMock(return_value=uow)
    services.audit = audit
    return services


def _server(services):
    return mcp_server.build_mcp_server(services, "https://api.test")


async def _call(services, tool: str, args: dict):
    with (
        patch.object(mcp_server, "_current_user_id", return_value="u1"),
        patch.object(mcp_server, "_current_client_id", return_value="client-9"),
    ):
        _, structured = await _server(services).call_tool(tool, args)
    return structured


async def test_the_tax_tools_are_the_users_own_and_nothing_built_in(services):
    names = {tool.name for tool in await _server(services).list_tools()}
    assert {"get_tax_computation", "explain_tax_line", "suggested_tax_accounts"} <= names
    assert not names & {"list_tax_packs", "explain_tax_band"}


async def test_the_computation_is_read_only_lines_with_their_sources(services):
    services.tax.compute_tax.return_value = computation_view()

    result = await _call(services, "get_tax_computation", {"year": "2031", "country": "XZ"})

    services.tax.compute_tax.assert_awaited_once_with(
        "u1", country="XZ", region=None, year="2031", answers=None, persist=False
    )
    assert result["rule_set_version"] == 2
    assert result["tax_payable"] == "3000.00"
    assert {line["key"] for line in result["lines"]} >= {"allowance", "tax", "balance"}
    assert "Never recompute" in result["how_to_read"]


async def test_no_active_rules_is_an_answer_saying_what_to_do(services):
    services.tax.compute_tax.side_effect = NoTaxRulesError(
        "no_rule_set", "You have no tax rules for the United Kingdom. " + ADD_RULES
    )
    result = await _call(services, "get_tax_computation", {})
    assert "research_tax_rules" in result["error"]
    assert "salli tax rules create" in result["error"]


async def test_a_line_is_explained_or_the_lines_there_are_are_named(services):
    services.tax.explain.return_value = {"line": {"key": "tax", "amount": "3000"}}
    assert (await _call(services, "explain_tax_line", {"line_key": "tax"}))["line"]["key"] == "tax"

    services.tax.explain.side_effect = UnknownLine("band", ["allowance", "tax"])
    result = await _call(services, "explain_tax_line", {"line_key": "band"})
    assert "no line 'band'" in result["error"] and "allowance, tax" in result["error"]


async def test_suggested_accounts_are_shown_then_applied_and_audited(services):
    services.tax_rules.suggested_accounts.return_value = {
        "rule_set_id": "rs1",
        "version_id": "v1",
        "version": 1,
        "applied": False,
        "accounts": [],
    }
    await _call(services, "suggested_tax_accounts", {"rule_set_id": "rs1"})
    actor = services.tax_rules.suggested_accounts.await_args.args[0]
    assert (actor.kind, actor.name) == ("agent", "Claude")
    assert services.tax_rules.suggested_accounts.await_args.kwargs["apply"] is False
    services.audit.log.assert_not_awaited()

    await _call(services, "suggested_tax_accounts", {"rule_set_id": "rs1", "apply": True})
    assert services.tax_rules.suggested_accounts.await_args.kwargs["apply"] is True
    assert services.audit.log.await_args.args[1] == "suggested_tax_accounts"


async def test_a_refused_suggestion_is_explained(services):
    services.tax_rules.suggested_accounts.side_effect = RuleSetStateError("Version 1 was superseded")
    result = await _call(services, "suggested_tax_accounts", {"rule_set_id": "rs1"})
    assert result == {"error": "Version 1 was superseded"}
