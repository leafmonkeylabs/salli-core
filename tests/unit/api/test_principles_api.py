"""
`/v1/principles` over HTTP: the real services over the household ledger
(tests/golden/household.py), held as the caller's, beside another user's
account in the same store.
"""

from __future__ import annotations

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.scenario_service import ScenarioService
from salli.domain.accounting.models import Account
from salli.interfaces.api.contract import OPERATION_IDS
from tests.fakes import FakeUoW
from tests.golden import household as h
from tests.unit.api.conftest import AUTH
from tests.unit.api.test_baseline_api import USER, _household_of

pytestmark = pytest.mark.asyncio

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


@pytest.fixture
def uow(mock_services) -> FakeUoW:
    books = _household_of(USER)
    books.ledger.accounts.append(
        Account(
            id="theirs",
            user_id="someone-else",
            code="1000",
            name="Theirs",
            type="asset",
            currency="EUR",
        )  # fmt: skip
    )
    baselines = BaselineService(books.factory(), fx=h.fx(), today=lambda: h.AS_OF)
    scenarios = ScenarioService(books.factory(), baselines=baselines)
    mock_services.principles = PrincipleService(books.factory(), scenarios)
    return books


async def test_every_route_is_named():
    for route in [
        ("GET", "/principles"),
        ("POST", "/principles"),
        ("GET", "/principles/figures"),
        ("POST", "/principles/check"),
        ("PATCH", "/principles/{principle_id}"),
        ("POST", "/principles/{principle_id}/archive"),
    ]:
        assert route in OPERATION_IDS


async def test_add_list_edit_and_archive(client, uow):
    r = await client.post(
        "/v1/principles",
        json={"label": "Six months of essentials", "check": "emergency_months >= 6"},
        headers=AUTH,
    )
    assert r.status_code == 201, r.text
    added = r.json()
    assert (added["schema"], added["version"], added["status"]) == (
        "salli.principle/1",
        1,
        "active",
    )
    r = await client.patch(
        f"/v1/principles/{added['id']}", json={"check": "emergency_months >= 4"}, headers=AUTH
    )
    assert r.status_code == 200, r.text
    assert (r.json()["version"], r.json()["label"]) == (2, "Six months of essentials")
    r = await client.post(f"/v1/principles/{added['id']}/archive", headers=AUTH)
    assert r.json()["status"] == "archived"
    assert (await client.get("/v1/principles", headers=AUTH)).json() == {"principles": []}
    every = await client.get("/v1/principles", params={"include_archived": "true"}, headers=AUTH)
    assert [p["id"] for p in every.json()["principles"]] == [added["id"]]


async def test_a_check_salli_cant_use_is_refused_with_each_problems_path(client, uow):
    r = await client.post(
        "/v1/principles",
        json={"label": "Low", "check": "account_lowest >= 2000 and emergency_month > 1"},
        headers=AUTH,
    )
    assert r.status_code == 422
    body = r.json()
    assert body["type"].endswith("invalid-principle")
    [problem] = body["detail"]
    assert problem["loc"] == ["body", "check"] and "emergency_months" in problem["msg"]
    assert "^" in problem["snippet"]


async def test_another_users_account_is_not_found(client, uow):
    r = await client.post(
        "/v1/principles",
        json={"label": "x", "check": "account_lowest >= 0", "account": "theirs"},
        headers=AUTH,
    )
    assert r.status_code == 404
    r = await client.patch("/v1/principles/nope", json={"label": "x"}, headers=AUTH)
    assert r.status_code == 404 and "Principle not found" in r.json()["detail"]


async def test_the_figures_are_documented(client, uow):
    r = await client.get("/v1/principles/figures", headers=AUTH)
    figures = {f["name"]: f for f in r.json()["figures"]}
    assert figures["emergency_months"]["unit"] == "months of spending"
    assert figures["net_worth_10y"]["terms"] == "real"
    assert figures["lowest_cash"]["terms"] == "nominal"
    assert figures["max_debt_rate_while_investing"]["kind"] == "rate"


async def test_checking_options_against_principles(client, uow):
    await client.post(
        "/v1/principles",
        json={"label": "Checking above 5,000", "check": "account_lowest >= 5000", "account": "chk"},
        headers=AUTH,
    )
    r = await client.post("/v1/principles/check", json={"options": [CASH]}, headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["baseline"]["results"][0]["status"] == "keeps"
    [option] = body["options"]
    assert option["label"] == "Pay cash"
    assert option["results"][0] == {
        "principle_id": body["principles"][0]["id"],
        "label": "Checking above 5,000",
        "status": "breaks",
        "reason": "account_lowest >= 5000 doesn't hold: account_lowest is 4883.77.",
        "figures": {"account_lowest": "4883.77"},
    }
    assert option["figures"]["lowest_cash"] == "11598.91"
    # With no options, the baseline alone.
    alone = await client.post("/v1/principles/check", json={}, headers=AUTH)
    assert alone.json()["options"] == []
