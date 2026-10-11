"""
`POST /v1/scenarios/run` and `/v1/scenarios/compare` over HTTP: the real
service over the household ledger (tests/golden/household.py), held as the
caller's, beside another user's account and debt in the same store.
"""

from __future__ import annotations

from typing import Any

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.scenario_service import ScenarioService
from salli.domain.accounting.models import Account
from salli.interfaces.api.contract import OPERATION_IDS
from tests.fakes import FakeUoW
from tests.golden import household as h
from tests.unit.api.conftest import AUTH
from tests.unit.api.test_baseline_api import USER, _household_of

pytestmark = pytest.mark.asyncio

OTHER = "someone-else"
LAPTOP = {
    "type": "one_off",
    "date": "2026-11-02",
    "amount": "-2400.00",
    "account": "chk",
    "label": "Laptop",
}


@pytest.fixture
def uow(mock_services) -> FakeUoW:
    books = _household_of(USER)
    # Another user's account and debt, in the same store.
    books.ledger.accounts.append(
        Account(
            id="theirs",
            user_id=OTHER,
            code="1000",
            name="Their checking",
            type="asset",
            currency="EUR",
        )
    )
    books.debts.rows["their-debt"] = {
        **books.debts.rows["debt-student"],
        "id": "their-debt",
        "user_id": OTHER,
    }
    baselines = BaselineService(books.factory(), fx=h.fx(), today=lambda: h.AS_OF)
    mock_services.scenarios = ScenarioService(books.factory(), baselines=baselines)
    return books


def _doc(*changes: dict[str, Any], **more: Any) -> dict[str, Any]:
    return {"schema": "salli.scenario/1", "changes": list(changes), **more}


async def test_a_scenario_runs_with_every_figure_against_the_baseline(client, uow):
    r = await client.post("/v1/scenarios/run", json=_doc(LAPTOP, label="Laptop"), headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["schema"], body["as_of"], body["currency"], body["horizon_years"]) == (
        "salli.scenario/1",
        "2026-10-11",
        "EUR",
        20,
    )
    chk = next(a for a in body["cash"]["accounts"] if a["account_id"] == "chk")
    assert chk["lowest"] == {"baseline": "6063.46", "scenario": "4883.77", "delta": "-1179.69"}
    assert chk["lowest_date"] == {
        "baseline": "2026-10-15",
        "scenario": "2026-11-15",
        "delta_days": 31,
    }
    assert body["cash"]["at_end"]["delta"] == "-2400.00"
    assert [p["years"] for p in body["monthly"]] == [1, 5, 10, 20]
    assert body["monthly"][0]["net_worth"]["delta"] == "-2400.00"
    assert body["fi"]["fi_month"] == {
        "baseline": "2047-05",
        "scenario": "2047-06",
        "delta_months": 1,
    }
    assert body["fi"]["months_gained"] == -1
    assert body["resilience"]["lowest"] == {
        "baseline": "8.29",
        "scenario": "7.94",
        "delta": "-0.35",
    }
    # Recorded with it: the assumptions, the versions, the as-of date, a hash.
    assert body["placeholders"] == ["real_return", "safe_withdrawal_rate", "inflation"]
    assert body["assumptions"]["status"] == "placeholder"
    assert body["versions"]["schema"] == "salli.scenario/1"
    assert body["versions"]["fi_assumptions"].startswith("sha256:")
    assert body["versions"]["rule_sets"] == []
    assert body["hash"].startswith("sha256:") and body["baseline_fingerprint"].startswith("sha256:")
    assert body["scenario"]["as_of"] == "2026-10-11"
    assert (body["data_as_of"], body["is_stale"]) == ("2026-10-09", False)
    # Nothing is stored.
    assert uow.fi_scores.rows == []


async def test_the_same_inputs_give_the_same_hash(client, uow):
    first = (await client.post("/v1/scenarios/run", json=_doc(LAPTOP), headers=AUTH)).json()
    reordered = {"changes": [dict(reversed(list(LAPTOP.items())))], "schema": "salli.scenario/1"}
    reordered["changes"][0]["amount"] = "-2400"
    again = (await client.post("/v1/scenarios/run", json=reordered, headers=AUTH)).json()
    assert again["hash"] == first["hash"]


async def test_options_compare_side_by_side_with_the_trade_and_break_evens(
    client, uow, mock_services
):
    purchase = {"type": "one_off", "date": "2026-11-02", "amount": "-2400.00", "label": "Laptop"}
    loan = {
        "type": "loan",
        "principal": "2400.00",
        "annual_rate": "0.069",
        "term_months": 12,
        "start": "2026-11-02",
        "label": "Laptop instalments",
    }
    r = await client.post(
        "/v1/scenarios/compare",
        json={
            "options": [
                _doc(purchase, label="Pay cash"),
                _doc(purchase, loan, label="Instalments"),
            ]
        },
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["labels"] == ["Pay cash", "Instalments"]
    assert [o["label"] for o in body["options"]] == ["Pay cash", "Instalments"]
    assert body["options"][1]["changes"][1]["payment"] == "207.55"
    trade = {(t["option"], t["against"]): t for t in body["trade"]}
    gives_up = {d["figure"]: d for d in trade[("Instalments", "Pay cash")]["gives_up"]}
    assert gives_up["debts.total_interest"] == {
        "figure": "debts.total_interest",
        "unit": "amount",
        "this": "2099.93",
        "other": "2009.25",
        "delta": "90.68",
    }
    assert set(body["sensitivity"]["real_returns"]) == {"conservative", "base", "growth"}
    (rate,) = body["break_evens"]
    assert (rate["kind"], rate["option"], rate["status"], rate["value"], rate["unit"]) == (
        "loan_rate",
        "Instalments",
        "found",
        "0",
        "rate",
    )
    assert "best" not in r.text.lower()
    mock_services.usage.charge.assert_not_called()


@pytest.mark.parametrize(
    ("doc", "where"),
    [
        (_doc({**LAPTOP, "amount": -2400}), ["body", "changes", 0, "one_off", "amount"]),
        (_doc({**LAPTOP, "date": "2026-02-30"}), ["body", "changes", 0, "one_off", "date"]),
        (_doc(horizon_years=51), ["body", "horizon_years"]),
        (_doc(horizon_years=0), ["body", "horizon_years"]),
        (_doc(*[LAPTOP] * 51), ["body", "changes"]),
        (_doc({**LAPTOP, "type": "lottery"}), ["body", "changes", 0]),
        ({"changes": []}, ["body", "schema"]),
    ],
)
async def test_a_document_salli_can_t_read_is_refused_with_its_path(client, uow, doc, where):
    r = await client.post("/v1/scenarios/run", json=doc, headers=AUTH)
    assert r.status_code == 422, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    assert where in [e["loc"] for e in r.json()["detail"]]


async def test_a_scenario_salli_can_t_run_on_your_money_is_refused_with_each_path(client, uow):
    r = await client.post(
        "/v1/scenarios/run",
        json=_doc({**LAPTOP, "date": "2026-10-01"}, {**LAPTOP, "account": "brk"}),
        headers=AUTH,
    )
    assert r.status_code == 422
    body = r.json()
    assert body["type"] == "/problems/invalid-scenario"
    assert [e["loc"] for e in body["detail"]] == [
        ["body", "changes", 0, "date"],
        ["body", "changes", 1, "account"],
    ]
    later = await client.post("/v1/scenarios/run", json=_doc(as_of="2026-10-12"), headers=AUTH)
    assert later.status_code == 422
    assert later.json()["detail"] == [
        {"loc": ["body", "as_of"], "msg": "can't be after today (2026-10-11)"}
    ]


@pytest.mark.parametrize(
    ("change", "said"),
    [
        ({**LAPTOP, "account": "theirs"}, "Account not found: theirs"),
        ({**LAPTOP, "account": "nowhere"}, "Account not found: nowhere"),
        (
            {"type": "invest", "amount": "1", "date": "2026-11-02", "from": "theirs", "label": "x"},
            "Account not found: theirs",
        ),
        (
            {
                "type": "loan",
                "principal": "1",
                "annual_rate": "0",
                "term_months": 1,
                "start": "2026-11-02",
                "into": "theirs",
                "label": "x",
            },
            "Account not found: theirs",
        ),
        (
            {
                "type": "extra_debt_payment",
                "debt": "their-debt",
                "monthly": "1",
                "from": "2026-11-02",
            },
            "Debt not found: their-debt",
        ),
        (
            {"type": "extra_debt_payment", "debt": "no-debt", "monthly": "1", "from": "2026-11-02"},
            "Debt not found: no-debt",
        ),
    ],
)
async def test_another_users_account_or_debt_is_not_found(client, uow, change, said):
    """Someone else's account or debt reads exactly as one that doesn't exist."""
    for path, body in (
        ("/v1/scenarios/run", _doc(change)),
        ("/v1/scenarios/compare", {"options": [_doc(label="A"), _doc(change, label="B")]}),
    ):
        r = await client.post(path, json=body, headers=AUTH)
        assert r.status_code == 404, r.text
        assert r.json() == {
            "type": "/problems/not-found",
            "title": "Not found",
            "status": 404,
            "detail": said,
        }


async def test_a_comparison_needs_two_to_five_distinct_options_on_one_horizon(client, uow):
    async def refused(options: list[dict[str, Any]]) -> list[Any]:
        r = await client.post("/v1/scenarios/compare", json={"options": options}, headers=AUTH)
        assert r.status_code == 422, r.text
        return [e["loc"] for e in r.json()["detail"]]

    assert ["body", "options"] in await refused([_doc()])
    assert ["body", "options"] in await refused([_doc(label=str(i)) for i in range(6)])
    assert await refused([_doc(label="Same"), _doc(label="Same")]) == [
        ["body", "options", 1, "label"]
    ]
    assert await refused([_doc(label="A"), _doc(label="B", horizon_years=10)]) == [
        ["body", "options", 1, "horizon_years"]
    ]
    assert await refused(
        [_doc(label="A", as_of="2026-10-01"), _doc(label="B", as_of="2026-10-02")]
    ) == [["body", "options", 1, "as_of"]]


async def test_scenarios_need_a_signed_in_user(client, uow):
    assert (await client.post("/v1/scenarios/run", json=_doc())).status_code == 401
    assert (await client.post("/v1/scenarios/compare", json={"options": []})).status_code == 401


async def test_the_routes_are_named_in_the_contract():
    assert OPERATION_IDS[("POST", "/scenarios/run")] == "scenarios.run"
    assert OPERATION_IDS[("POST", "/scenarios/compare")] == "scenarios.compare"
    assert ("POST", "/fi/simulate-purchase") not in OPERATION_IDS
