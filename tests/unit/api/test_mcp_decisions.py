"""
The MCP tools for principles and the decision journal, over the household
ledger: an agent can't store a principle, record a decision or a review
without the person's confirmation in the call; what it records is marked
as recorded through it; and the journal's guardrails are in the tools'
own descriptions.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from salli.application.services.baseline_service import BaselineService
from salli.application.services.decision_service import DecisionService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.scenario_service import ScenarioService
from salli.domain import canonical
from salli.interfaces.api import mcp_server
from tests.golden import household as h
from tests.unit.api.test_baseline_api import USER, _household_of

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("experimental_on")]

CASH = {
    "schema": "salli.scenario/1",
    "label": "Pay cash",
    "changes": [
        {
            "type": "one_off",
            "date": "2026-11-02",
            "amount": "-2400.00",
            "account": "chk",
            "label": "Laptop",
        }
    ],
}
WAIT = {"schema": "salli.scenario/1", "label": "Wait"}
TOOLS = (
    "list_principles",
    "add_principle",
    "check_principles",
    "record_decision",
    "list_decisions",
    "get_decision",
    "list_due_reviews",
    "review_decision",
)


class Clock:
    today = h.AS_OF


@pytest.fixture
def services() -> Any:
    books = _household_of(USER)
    Clock.today = h.AS_OF
    baselines = BaselineService(books.factory(), fx=h.fx(), today=lambda: Clock.today)
    scenarios = ScenarioService(books.factory(), baselines=baselines)
    principles = PrincipleService(books.factory(), scenarios)
    services = MagicMock()
    services.scenarios = scenarios
    services.principles = principles
    services.decisions = DecisionService(
        books.factory(),
        scenarios,
        principles,
        now=lambda: dt.datetime(2026, 10, 11, 9, tzinfo=dt.UTC),
    )
    services.mcp_oauth.client_name = AsyncMock(return_value="Claude")
    services.ledger._uow_factory = books.factory()
    return services


async def _call(services: Any, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    server = mcp_server.build_mcp_server(services, "https://api.test")
    with (
        patch.object(mcp_server, "_current_user_id", return_value=USER),
        patch.object(mcp_server, "_current_client_id", return_value="client-1"),
    ):
        _, structured = await server.call_tool(tool, args)
    return structured


async def _tools(services: Any) -> dict[str, Any]:
    server = mcp_server.build_mcp_server(services, "https://api.test")
    return {t.name: t for t in await server.list_tools()}


async def test_the_tools_carry_their_guardrails(services):
    tools = await _tools(services)
    for name in TOOLS:
        assert name in tools
    for name in ("add_principle", "record_decision", "review_decision"):
        schema = tools[name].inputSchema
        assert "confirmed_by_user" in schema["required"]
        assert schema["properties"]["confirmed_by_user"]["const"] is True
    record = " ".join((tools["record_decision"].description or "").split())
    assert "Never record a decision they haven't confirmed" in record
    assert "THEIR words" in record
    assert "never choose for them" in record
    assert "$ref" not in str(tools["record_decision"].inputSchema)
    assert "Never a ranking" in " ".join((tools["check_principles"].description or "").split())


async def test_without_the_persons_confirmation_nothing_is_stored(services):
    for tool, args in (
        ("add_principle", {"label": "x", "check": "emergency_months >= 6"}),
        (
            "record_decision",
            {
                "question": "Q?",
                "options": [CASH],
                "chosen": "Pay cash",
                "reasons": "R.",
                "review_on": "2027-04-11",
            },
        ),
    ):
        for confirmed in ({}, {"confirmed_by_user": False}):
            with pytest.raises(ToolError):
                await _call(services, tool, {**args, **confirmed})
    assert (await services.principles.list(USER))["principles"] == []
    assert (await services.decisions.list(USER))["decisions"] == []


async def test_a_principle_the_person_confirmed_is_marked_as_the_agents(services, refused):
    added = await _call(
        services,
        "add_principle",
        {"label": "Six months", "check": "emergency_months >= 6", "confirmed_by_user": True},
    )
    assert (added["author"], added["agent"]) == ("agent", "Claude")
    listed = await _call(services, "list_principles", {})
    assert [p["label"] for p in listed["principles"]] == [{"untrusted_text": "Six months"}]
    assert "emergency_months" in {f["name"] for f in listed["figures"]}
    unknown = await refused(
        _call(
            services,
            "add_principle",
            {"label": "x", "check": "emergency_month >= 6", "confirmed_by_user": True},
        )
    )
    assert unknown["problems"][0]["path"] == "check"


async def test_checking_and_recording_a_decision(services):
    checked = await _call(services, "check_principles", {"options": [CASH, WAIT]})
    assert [o["label"] for o in checked["options"]] == [{"untrusted_text": "Pay cash"}, "Wait"]
    recorded = await _call(
        services,
        "record_decision",
        {
            "question": "Laptop: now or later?",
            "options": [CASH, WAIT],
            "chosen": "Pay cash",
            "reasons": "The old one is dying.",
            "review_on": "2027-04-11",
            "agent_summary": "Paying cash costs no interest.",
            "confirmed_by_user": True,
        },
    )
    entry = recorded["entry"]
    assert canonical.digest(entry) == recorded["hash"]
    assert entry["recorded_via"] == {
        "channel": "mcp",
        "client": "Claude",
        "confirmed_by_user": True,
    }
    assert entry["agent_summary"]["agent"] == "Claude"
    listed = await _call(services, "list_decisions", {})
    assert [d["id"] for d in listed["decisions"]] == [recorded["id"]]
    read = await _call(services, "get_decision", {"decision_id": recorded["id"]})
    assert read["verified"] is True


async def test_a_due_review_is_pulled_and_recorded_with_the_persons_reflection(services):
    recorded = await _call(
        services,
        "record_decision",
        {
            "question": "Laptop?",
            "options": [CASH],
            "chosen": "Pay cash",
            "reasons": "Needed it.",
            "review_on": "2027-04-11",
            "confirmed_by_user": True,
        },
    )
    assert (await _call(services, "list_due_reviews", {}))["reviews"] == []
    Clock.today = dt.date(2027, 4, 12)
    [due] = (await _call(services, "list_due_reviews", {}))["reviews"]
    assert due["id"] == recorded["id"] and due["comparison"]["option"] == {
        "untrusted_text": "Pay cash"
    }
    with pytest.raises(ToolError):
        await _call(
            services, "review_decision", {"decision_id": recorded["id"], "reflection": "Fine."}
        )
    reviewed = await _call(
        services,
        "review_decision",
        {"decision_id": recorded["id"], "reflection": "Fine.", "confirmed_by_user": True},
    )
    assert (reviewed["review"]["author"], reviewed["review"]["agent"]) == ("agent", "Claude")
    assert (await _call(services, "list_due_reviews", {}))["reviews"] == []
