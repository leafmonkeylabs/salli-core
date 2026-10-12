"""
Decision templates over MCP, and the prompts that walk an agent through a
decision: the tools serve the person's own defaults and Salli's figures,
record nothing, rank nothing; and the guardrails are in the prompts, where
an agent reads them.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.decision_service import DecisionService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.scenario_service import ScenarioService
from salli.application.services.template_service import TemplateService
from salli.interfaces.api import mcp_server
from tests.golden import household as h
from tests.guardrails import assert_never_ranks
from tests.unit.api.test_baseline_api import USER, _household_of

pytestmark = pytest.mark.asyncio


@pytest.fixture
def services() -> Any:
    books = _household_of(USER)
    baselines = BaselineService(books.factory(), fx=h.fx(), today=lambda: h.AS_OF)
    scenarios = ScenarioService(books.factory(), baselines=baselines)
    principles = PrincipleService(books.factory(), scenarios)
    services = MagicMock()
    services.scenarios = scenarios
    services.principles = principles
    services.templates = TemplateService(scenarios, principles)
    services.decisions = DecisionService(
        books.factory(),
        scenarios,
        principles,
        now=lambda: dt.datetime(2026, 10, 11, 9, tzinfo=dt.UTC),
    )
    services.mcp_oauth.client_name = AsyncMock(return_value="Claude")
    services.ledger._uow_factory = books.factory()
    return services


def _server(services: Any) -> Any:
    return mcp_server.build_mcp_server(services, "https://api.test")


async def _call(services: Any, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    with (
        patch.object(mcp_server, "_current_user_id", return_value=USER),
        patch.object(mcp_server, "_current_client_id", return_value="client-1"),
    ):
        _, structured = await _server(services).call_tool(tool, args)
    return structured


async def _prompt(services: Any, name: str, args: dict[str, str]) -> str:
    result = await _server(services).get_prompt(name, args)
    return " ".join(" ".join(m.content.text.split()) for m in result.messages)  # type: ignore[union-attr]


def _guarded(text: str) -> None:
    """The guardrails, as an agent reads them."""
    assert "Never compute" in text
    assert "never add, subtract, divide, project or estimate anything yourself" in text
    assert "never work out tax or what I'd keep after it" in text
    assert "Never name a specific product, provider, fund or security" in text
    assert (
        "regulated financial advice where I live (insurance, pensions, choosing investments)"
        in text
    )
    assert "suggest a licensed professional there; don't assume any country's rules" in text
    assert "Respect my principles" in text
    assert "Never rank the options or call one best, recommended or right" in text
    assert "Never record a decision I haven't confirmed" in text
    assert "with my reasons in my own words" in text


async def test_the_tools_say_what_they_do_and_dont(services):
    tools = {t.name: t for t in await _server(services).list_tools()}
    listing = " ".join((tools["list_decision_templates"].description or "").split())
    assert "Conveniences, not advice" in listing
    assert "Never fill in an answer they haven't given that has no default" in listing
    start = " ".join((tools["start_decision"].description or "").split())
    assert "It ranks nothing, and neither do you" in start
    assert "It stores nothing" in start
    assert "once they confirm" in start
    assert set(tools["start_decision"].inputSchema["required"]) == {"template"}


async def test_templates_come_with_the_persons_own_defaults(services):
    listed = await _call(services, "list_decision_templates", {})
    by_id = {t["id"]: t for t in listed["templates"]}
    assert len(by_id) == 6
    borrow = {q["id"]: q for q in by_id["borrow"]["questions"]}
    assert borrow["start"]["default"]["value"] == "2026-10-11"
    assert by_id["afford-it"]["answers_schema"]["properties"]["account"]["enum"] == ["chk", "sav"]
    assert_never_ranks(listed)


async def test_starting_a_decision_and_recording_it_in_one_step(services):
    started = await _call(
        services,
        "start_decision",
        {
            "template": "debt-or-invest",
            "answers": {
                "debt": "debt-student",
                "amount": "5000.00",
                "start": "2026-12-01",
                "horizon_years": 10,
            },
        },
    )
    assert [o["label"] for o in started["options"]] == ["Pay down Student loan", "Invest it"]
    [even] = started["comparison"]["break_evens"]
    assert even["value"] == "0.0451"
    assert_never_ranks(started)
    assert (await services.decisions.list(USER))["decisions"] == []
    record = started["record"]
    recorded = await _call(
        services,
        "record_decision",
        {
            "question": record["question"],
            "options": record["options"],
            "chosen": "Pay down Student loan",
            "reasons": "Owing less matters more to me than the last basis point.",
            "review_on": "2027-10-31",
            "confirmed_by_user": True,
        },
    )
    assert recorded["entry"]["chosen"] == "Pay down Student loan"


async def test_problems_come_back_with_their_paths(services):
    refused = await _call(
        services, "start_decision", {"template": "afford-it", "answers": {"price": "-5"}}
    )
    paths = {p["path"] for p in refused["problems"]}
    assert paths == {"answers.price"}
    unknown = await _call(services, "start_decision", {"template": "lottery"})
    assert unknown["error"].startswith("No decision template 'lottery'")


async def test_think_through_decision_walks_the_six_steps_within_the_guardrails(services):
    text = await _prompt(services, "think_through_decision", {"question": "New car or not?"})
    assert text.startswith("Help me think this decision through with Salli: New car or not?")
    steps = [
        "1. Ask what I am weighing and what matters to me",
        "2. Build the options with Salli, never by hand: pick a template",
        "3. Compare them, with the sensitivity, and check my principles",
        "4. Explain the trade-offs in plain language, quoting Salli's figures",
        "5. Say what would change the answer",
        "6. Leave the choice to me.",
    ]
    positions = [text.index(step) for step in steps]
    assert positions == sorted(positions)
    assert "say plainly which are placeholders" in text
    assert "record_decision with confirmed_by_user only after I say yes" in text
    _guarded(text)


async def test_can_i_afford_runs_the_afford_it_template_within_the_guardrails(services):
    text = await _prompt(
        services, "can_i_afford", {"amount": "2400", "when": "2026-11-02", "what": "a laptop"}
    )
    assert "start_decision with the afford-it template" in text
    assert 'price "2400", what "a laptop", date 2026-11-02' in text
    assert "Don't assume a rate or an amount: ask." in text
    _guarded(text)
