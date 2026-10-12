"""
Invest and sell changes on the caller's holdings over HTTP (decision lab
3b): the household (tests/golden/household.py) holds a fund it calls "My
world fund" in its brokerage, beside another user's holding in the same
store. A holding that isn't the caller's is not found, like any other id;
one that isn't linked can't be sold, at its path.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.scenario_service import ScenarioService
from salli.domain.money import to_minor
from tests.fakes import FakeUoW
from tests.golden import household as h
from tests.guardrails import assert_never_ranks
from tests.unit.api.conftest import AUTH
from tests.unit.api.test_baseline_api import USER, _household_of

pytestmark = pytest.mark.asyncio


def _holding(books: FakeUoW, id_: str, user: str, account: str | None) -> None:
    books.holdings.rows[id_] = {
        "id": id_,
        "user_id": user,
        "symbol": "WRLD",
        "name": "My world fund",
        "asset_class": "equity",
        "currency": "EUR",
        "cost_basis_minor": 0,
        "current_value_minor": 0,
        "is_active": True,
        "account_id": account,
        "created_at": "",
        "updated_at": "",
    }
    books.holding_transactions.rows[f"{id_}-buy"] = {
        **books.holding_transactions.DEFAULTS,
        "id": f"{id_}-buy",
        "user_id": user,
        "holding_id": id_,
        "kind": "buy",
        "transaction_date": "2026-04-02",
        "quantity": Decimal("50"),
        "price": Decimal("80"),
        "fees_minor": to_minor(Decimal("10"), "EUR"),
        "fx_rate": Decimal(1),
        "created_at": "",
        "updated_at": "",
    }
    books.holding_prices.rows[f"{id_}-close"] = {
        "id": f"{id_}-close",
        "user_id": user,
        "symbol": "WRLD",
        "price_date": "2026-10-09",
        "close": Decimal("100"),
        "currency": "EUR",
        "source": "user",
    }


@pytest.fixture
def uow(mock_services) -> FakeUoW:
    books = _household_of(USER)
    _holding(books, "mine", USER, "brk")
    _holding(books, "theirs", "someone-else", None)
    baselines = BaselineService(books.factory(), fx=h.fx(), today=lambda: h.AS_OF)
    mock_services.scenarios = ScenarioService(books.factory(), baselines=baselines)
    return books


def _doc(*changes: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "salli.scenario/1", "changes": list(changes)}


SALE = {"type": "sell", "holding": "mine", "quantity": "5", "date": "2026-10-12", "fees": "1.50"}


async def test_a_sale_reads_back_its_units_price_lots_and_gain(client, uow):
    """5 units at 100.00 (the close of 2026-10-09): proceeds 500.00; the
    lot's cost 4,010.00 × 5/50 = 401.00; gain 500.00 − 1.50 − 401.00 =
    97.50."""
    r = await client.post("/v1/scenarios/run", json=_doc(SALE), headers=AUTH)
    assert r.status_code == 200, r.text
    (change,) = r.json()["changes"]
    assert (change["type"], change["label"]) == ("sell", "Sell My world fund")
    trade = change["holding"]
    assert {k: trade[k] for k in ("units", "price", "value", "fees", "cost", "gain")} == {
        "units": "5",
        "price": "100",
        "value": "500.00",
        "fees": "1.50",
        "cost": "401.00",
        "gain": "97.50",
    }
    assert trade["lots"] == [
        {
            "lot_id": "mine-buy",
            "opened_on": "2026-04-02",
            "units": "5",
            "cost": "401.00",
            "cost_base": "401.00",
        }
    ]
    assert (trade["name"], trade["symbol"], trade["account_id"]) == ("My world fund", "WRLD", "brk")
    assert not any("expected" in key or "return" in key for key in trade)
    assert_never_ranks(r.json())


async def test_someone_elses_holding_is_not_found(client, uow):
    r = await client.post(
        "/v1/scenarios/run", json=_doc({**SALE, "holding": "theirs"}), headers=AUTH
    )
    assert r.status_code == 404
    assert "Holding not found: theirs" in r.text
    invest = {
        "type": "invest",
        "amount": "100.00",
        "date": "2026-10-12",
        "holding": "made-up",
        "label": "x",
    }
    r = await client.post("/v1/scenarios/run", json=_doc(invest), headers=AUTH)
    assert r.status_code == 404


async def test_an_unlinked_holding_cant_be_sold(client, uow):
    uow.holdings.rows["mine"]["account_id"] = None
    r = await client.post("/v1/scenarios/run", json=_doc(SALE), headers=AUTH)
    assert r.status_code == 422
    (problem,) = r.json()["detail"]
    assert problem["loc"] == ["body", "changes", 0, "holding"]
    assert "isn't linked to the investment account that holds it" in problem["msg"]


async def test_a_gain_goes_only_to_an_income_role(client, uow):
    uow.tax_rule_sets.role_kinds = {"pension": {"deduction"}}
    r = await client.post(
        "/v1/scenarios/run", json=_doc({**SALE, "tax_role": "pension"}), headers=AUTH
    )
    assert r.status_code == 422
    (problem,) = r.json()["detail"]
    assert problem["loc"] == ["body", "changes", 0, "tax_role"]
    assert "a sale's realised gain goes to an income role" in problem["msg"]
