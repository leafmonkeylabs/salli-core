"""The MCP tools for tax rules: an AI client researches, drafts, validates,
proposes, diffs and evaluates, and has no way to activate."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salli.application.permissions import TAX_ACTIVATE
from salli.application.services.tax_rule_service import RuleSetDocumentError, RuleSetStateError
from salli.domain.taxrules.common import Problem
from salli.interfaces.api import mcp_server

pytestmark = pytest.mark.asyncio

VERSION = {
    "id": "v1",
    "rule_set_id": "rs1",
    "version": 1,
    "status": "draft",
    "created_at": datetime(2031, 2, 1, tzinfo=UTC),
    "content": {"schema": "salli.tax/1"},
    "validation": {"ok": False, "errors": [], "warnings": [], "examples": []},
}


@pytest.fixture
def services():
    services = MagicMock()
    services.tax_rules = AsyncMock()
    services.tax_rules.schema = MagicMock(return_value={"title": "Salli tax rule set"})
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


async def test_there_is_no_tool_that_activates(services):
    names = {tool.name for tool in await _server(services).list_tools()}
    assert not [name for name in names if "activ" in name]
    assert {
        "get_tax_rule_schema",
        "list_tax_rule_sets",
        "get_tax_rule_set",
        "draft_tax_rule_set",
        "validate_tax_rule_set",
        "propose_tax_rule_set",
        "diff_tax_rule_set_versions",
        "evaluate_tax_rule_set",
    } <= names


async def test_a_draft_is_recorded_as_the_agent_s_and_audited(services):
    services.tax_rules.draft.return_value = VERSION
    result = await _call(services, "draft_tax_rule_set", {"document": "{}", "note": "first try"})
    assert result["id"] == "v1" and result["created_at"] == "2031-02-01T00:00:00+00:00"
    actor = services.tax_rules.draft.await_args.args[0]
    assert (actor.user_id, actor.kind, actor.name) == ("u1", "agent", "Claude")
    assert not actor.may(TAX_ACTIVATE)
    services.audit.log.assert_awaited_once()
    assert services.audit.log.await_args.args[1] == "draft_tax_rule_set"


async def test_a_refusal_lists_its_problems_for_the_agent_to_fix(services):
    services.tax_rules.draft.side_effect = RuleSetDocumentError(
        "This is not a rule set Salli can read", [Problem("$", "Not valid JSON")]
    )
    result = await _call(services, "draft_tax_rule_set", {"document": "{"})
    assert result == {
        "error": "This is not a rule set Salli can read",
        "problems": [{"path": "$", "message": "Not valid JSON", "snippet": None}],
    }
    services.audit.log.assert_not_awaited()


async def test_proposing_tells_the_agent_that_only_the_user_activates(services):
    services.tax_rules.propose.return_value = {**VERSION, "status": "proposed"}
    result = await _call(services, "propose_tax_rule_set", {"version_id": "v1"})
    assert result["status"] == "proposed"
    assert "Only the user can activate it" in result["next"]
    services.tax_rules.propose.side_effect = RuleSetStateError("can't be proposed: examples")
    assert await _call(services, "propose_tax_rule_set", {"version_id": "v1"}) == {
        "error": "can't be proposed: examples"
    }


async def test_evaluating_runs_salli_s_engine_on_the_user_s_ledger(services):
    services.tax_rules.evaluate.return_value = {"tax_payable": "3000", "lines": []}
    result = await _call(
        services, "evaluate_tax_rule_set", {"version_id": "v1", "answers": {"status": "single"}}
    )
    assert result["tax_payable"] == "3000"
    services.tax_rules.evaluate.assert_awaited_once_with(
        "u1", "v1", {"status": "single"}, year_label=None
    )


async def test_the_research_prompt_keeps_the_agent_to_official_sources_and_proposals():
    server = mcp_server.build_mcp_server(MagicMock(), "https://api.test")
    result = await server.get_prompt("research_tax_rules", {"country": "XZ", "year": "2031"})
    text = result.messages[0].content.text  # type: ignore[union-attr]
    for phrase in (
        "XZ, tax year 2031",
        "official sources only",
        "Cite every figure",
        "Never invent an example",
        "until there are no errors and every example passes",
        "propose_tax_rule_set",
        "activate it myself in Salli",
        "Never compute tax yourself",
    ):
        assert phrase in text, phrase
