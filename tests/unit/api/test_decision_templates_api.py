"""
Decision templates over HTTP (`/v1/decisions/templates`,
`/v1/decisions/start`): the real services over the household ledger, held
as the caller's. A template's defaults are the caller's own; starting a
decision runs every option and records nothing; answers Salli can't use are
a 422 with each problem's path; and nothing that comes back ranks.
"""

from __future__ import annotations

import datetime as dt

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.decision_service import DecisionService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.scenario_service import ScenarioService
from salli.application.services.template_service import TemplateService
from tests.fakes import FakeUoW
from tests.golden import household as h
from tests.guardrails import assert_never_ranks
from tests.unit.api.conftest import AUTH
from tests.unit.api.test_baseline_api import USER, _household_of

pytestmark = pytest.mark.asyncio

AFFORD = {
    "template": "afford-it",
    "answers": {
        "price": "2400.00",
        "what": "Laptop",
        "date": "2026-11-02",
        "account": "chk",
        "instalment_months": 12,
        "instalment_rate": "0.069",
    },
}


@pytest.fixture
def uow(mock_services) -> FakeUoW:
    books = _household_of(USER)
    baselines = BaselineService(books.factory(), fx=h.fx(), today=lambda: h.AS_OF)
    scenarios = ScenarioService(books.factory(), baselines=baselines)
    principles = PrincipleService(books.factory(), scenarios)
    mock_services.principles = principles
    mock_services.templates = TemplateService(scenarios, principles)
    mock_services.decisions = DecisionService(
        books.factory(),
        scenarios,
        principles,
        now=lambda: dt.datetime(2026, 10, 11, 9, tzinfo=dt.UTC),
    )
    return books


async def test_the_templates_are_listed_in_brief(client, uow):
    r = await client.get("/v1/decisions/templates", headers=AUTH)
    assert r.status_code == 200, r.text
    listed = r.json()["templates"]
    assert [t["id"] for t in listed] == [
        "afford-it",
        "debt-or-invest",
        "windfall",
        "big-change",
        "borrow",
        "emergency-fund",
        "rent-or-buy",
    ]
    assert set(listed[0]) == {"schema", "id", "title", "summary", "builds"}
    assert_never_ranks(r.json())


async def test_a_templates_defaults_are_the_callers_own(client, uow):
    await client.post(
        "/v1/principles",
        json={"label": "Six months in cash", "check": "emergency_months >= 6"},
        headers=AUTH,
    )
    r = await client.get("/v1/decisions/templates/emergency-fund", headers=AUTH)
    assert r.status_code == 200, r.text
    questions = {q["id"]: q for q in r.json()["questions"]}
    assert questions["target_months"]["default"] == {
        "value": "6",
        "source": "your_principles",
        "note": "from your principle “Six months in cash”",
    }
    assert questions["start"]["default"]["value"] == "2026-11-01"
    assert questions["set_aside"]["default"] is None and questions["set_aside"]["required"]

    borrow = (await client.get("/v1/decisions/templates/borrow", headers=AUTH)).json()
    schema = borrow["answers_schema"]["properties"]
    # The household has two debts: neither is assumed, and both are named.
    assert schema["debt"]["enum"] == ["debt-car", "debt-student"]
    assert {q["id"]: q["default"] for q in borrow["questions"]}["debt"] is None
    assert schema["into"]["enum"] == ["chk", "sav"]
    assert_never_ranks(borrow)

    r = await client.get("/v1/decisions/templates/lease-or-own", headers=AUTH)
    assert r.status_code == 404
    assert "afford-it" in r.json()["detail"]


async def test_starting_a_decision_runs_every_option_and_records_nothing(client, uow):
    r = await client.post("/v1/decisions/start", json=AFFORD, headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["schema"] == "salli.decision-start/1"
    assert body["template"] == {"id": "afford-it", "title": "Afford it"}
    assert [o["label"] for o in body["options"]] == ["Pay cash", "Spread over 12 months"]
    assert body["comparison"]["labels"] == ["Pay cash", "Spread over 12 months"]
    assert body["comparison"]["options"][0]["cash"]["lowest"]["scenario"] == "11598.91"
    assert [o["label"] for o in body["principles"]["options"]] == body["comparison"]["labels"]
    assert body["cover"] is None
    assert body["placeholders"] == [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "drawdown_horizon",
        "inflation",
    ]
    assert_never_ranks(body)
    # Nothing was recorded.
    assert (await client.get("/v1/decisions", headers=AUTH)).json()["decisions"] == []

    # What recording needs is in the result: one step, once the person has
    # chosen and given their reasons.
    record = body["record"]
    recorded = await client.post(
        "/v1/decisions",
        json={
            "question": record["question"],
            "options": record["options"],
            "chosen": "Pay cash",
            "reasons": "I'd rather not owe anything.",
            "review_on": "2027-04-11",
        },
        headers=AUTH,
    )
    assert recorded.status_code == 201, recorded.text
    entry = recorded.json()["entry"]
    assert [o["scenario_hash"] for o in entry["options"]] == [
        o["scenario_hash"] for o in body["options"]
    ]


async def test_answers_salli_cant_use_are_a_422_with_paths(client, uow):
    r = await client.post(
        "/v1/decisions/start",
        json={"template": "afford-it", "answers": {"price": 2400, "instalment_months": 12}},
        headers=AUTH,
    )
    assert r.status_code == 422
    assert r.json()["type"].endswith("invalid-answers")
    assert sorted(p["loc"] for p in r.json()["detail"]) == [
        ["body", "answers", "instalment_rate"],
        ["body", "answers", "price"],
    ]
    r = await client.post(
        "/v1/decisions/start", json={**AFFORD, "as_of": "2026-10-12"}, headers=AUTH
    )
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "as_of"]
    r = await client.post("/v1/decisions/start", json={"template": "nope"}, headers=AUTH)
    assert r.status_code == 404


async def test_an_emergency_fund_says_when_cash_covers_the_target(client, uow):
    r = await client.post(
        "/v1/decisions/start",
        json={
            "template": "emergency-fund",
            "answers": {"target_months": "9", "set_aside": ["200.00", "500.00"]},
        },
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    cover = r.json()["cover"]
    assert (cover["target"], cover["now"]) == ("17084.88", "8.32")
    assert [(o["option"], o["month"]) for o in cover["options"]] == [
        ("As things are", None),
        ("Set aside 200.00 a month", "2027-05"),
        ("Set aside 500.00 a month", "2027-01"),
    ]


async def test_the_holding_question_lists_the_callers_own_and_picks_none(client, uow):
    """The household holds one fund it calls "My world fund": it is listed,
    and still not assumed (decision lab 3b, decision 21)."""
    from tests.unit.api.test_holding_scenarios_api import _holding

    _holding(uow, "mine", USER, "brk")
    _holding(uow, "theirs", "someone-else", None)
    r = await client.get("/v1/decisions/templates/debt-or-invest", headers=AUTH)
    assert r.status_code == 200, r.text
    question = next(q for q in r.json()["questions"] if q["id"] == "holding")
    assert (question["type"], question["default"], question["required"]) == (
        "holding",
        None,
        False,
    )
    assert r.json()["answers_schema"]["properties"]["holding"]["enum"] == ["mine"]
    assert_never_ranks(r.json())
