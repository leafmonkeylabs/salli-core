"""
Holdings and the portfolio summary over HTTP.

Each typed response must carry exactly what the portfolio service returns:
values as decimal strings in the base currency's precision, and shares of the
portfolio as the decimal-string fractions they already were (not money).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.application.services.portfolio_service import PortfolioService
from tests.fakes import FakeRecordsUoW
from tests.unit.api.conftest import AUTH

USER = "test-user-1"
FUND = {
    "symbol": "VOO",
    "name": "S&P 500 fund",
    "asset_class": "equity",
    "cost_basis": 10000,
    "current_value": 12500,
}
BONDS = {
    "symbol": "BND",
    "name": "Bond fund",
    "asset_class": "bond",
    "cost_basis": 5000,
    "current_value": 4800.55,
}


def _uow(mock_services) -> FakeRecordsUoW:
    uow = FakeRecordsUoW()
    mock_services.portfolio = PortfolioService(lambda: uow)
    return uow


async def _create(client, holding: dict) -> str:
    r = await client.post("/v1/portfolio/", json=holding, headers=AUTH)
    assert r.status_code == 201
    return r.json()["id"]


async def test_a_holding_reads_back_as_the_service_returns_it(client, mock_services):
    _uow(mock_services)
    holding_id = await _create(client, BONDS)

    r = await client.get(f"/v1/portfolio/{holding_id}", headers=AUTH)
    assert r.status_code == 200
    holding = r.json()
    assert holding == await mock_services.portfolio.get_holding(USER, holding_id)
    assert (holding["currency"], holding["cost_basis"], holding["current_value"]) == (
        "LKR",
        "5000.00",
        "4800.55",
    )

    r = await client.get("/v1/portfolio/", headers=AUTH)
    assert r.json() == {"holdings": [holding]}


async def test_an_update_answers_that_it_was_applied(client, mock_services):
    _uow(mock_services)
    holding_id = await _create(client, FUND)

    r = await client.patch(
        f"/v1/portfolio/{holding_id}", json={"current_value": 13000.1}, headers=AUTH
    )
    assert (r.status_code, r.json()) == (200, {"updated": True})
    holding = (await client.get(f"/v1/portfolio/{holding_id}", headers=AUTH)).json()
    assert holding["current_value"] == "13000.10"


async def test_the_summary_is_the_services_summary(client, mock_services):
    _uow(mock_services)
    await _create(client, FUND)
    await _create(client, BONDS)

    r = await client.get(
        "/v1/portfolio/summary", params={"target": ["equity:0.6", "bond:0.4"]}, headers=AUTH
    )
    assert r.status_code == 200
    summary = r.json()
    targets = {"equity": Decimal("0.6"), "bond": Decimal("0.4")}
    assert summary == await mock_services.portfolio.get_summary(USER, targets)
    assert (summary["currency"], summary["total_value"], summary["total_gain"]) == (
        "LKR",
        "17300.55",
        "2300.55",
    )
    assert summary["total_gain_pct"] == "0.1534"
    assert summary["allocation"] == [
        {"asset_class": "equity", "current_value": "12500.00", "pct_of_portfolio": "0.7225"},
        {"asset_class": "bond", "current_value": "4800.55", "pct_of_portfolio": "0.2775"},
    ]
    assert summary["alerts"] == [
        {
            "asset_class": "bond",
            "current_pct": "0.2775",
            "target_pct": "0.4",
            "drift_pct": "-0.1225",
        },
        {
            "asset_class": "equity",
            "current_pct": "0.7225",
            "target_pct": "0.6",
            "drift_pct": "0.1225",
        },
    ]


async def test_an_empty_portfolio_sums_to_zero_in_the_currencys_precision(client, mock_services):
    _uow(mock_services)
    summary = (await client.get("/v1/portfolio/summary", headers=AUTH)).json()
    assert summary == {
        "currency": "LKR",
        "total_value": "0.00",
        "total_cost_basis": "0.00",
        "total_gain": "0.00",
        "total_gain_pct": "0.0000",
        "allocation": [],
        "alerts": [],
        "notes": [],
    }


async def test_a_missing_holding_is_not_found(client, mock_services):
    _uow(mock_services)
    assert (await client.get("/v1/portfolio/nope", headers=AUTH)).status_code == 404


@pytest.mark.parametrize(
    "bad", ["equity", "equity:abc", "equity:NaN", "equity:Infinity", "equity:1.5"]
)
async def test_a_target_that_is_not_a_share_is_refused(client, mock_services, bad):
    # "equity:abc" used to escape the handler as a 500.
    r = await client.get("/v1/portfolio/summary", params={"target": bad}, headers=AUTH)
    assert r.status_code == 422


async def test_a_holding_with_transactions_reads_back_its_derived_figures(client, mock_services):
    _uow(mock_services)
    holding_id = await _create(client, FUND)
    svc = mock_services.portfolio
    await svc.add_transaction(
        USER, holding_id, {"kind": "buy", "date": "2026-01-05", "quantity": "10", "price": "900"}
    )
    await svc.set_price(USER, {"symbol": "VOO", "close": "1001.5", "date": "2026-10-08"})

    r = await client.get(f"/v1/portfolio/{holding_id}", headers=AUTH)
    assert r.status_code == 200
    holding = r.json()
    assert holding == await svc.get_holding(USER, holding_id)
    # Not the 10,000 / 12,500 it was declared with: 10 units bought at 900,
    # now 1,001.50 each.
    assert (holding["cost_basis"], holding["current_value"], holding["tracking"]) == (
        "9000.00",
        "10015.00",
        "transactions",
    )
    assert holding["price"]["per_unit"] == "1001.5"
    assert (await client.get("/v1/portfolio/", headers=AUTH)).json() == {"holdings": [holding]}


async def test_declared_figures_for_a_holding_with_transactions_are_refused(client, mock_services):
    _uow(mock_services)
    holding_id = await _create(client, FUND)
    await mock_services.portfolio.add_transaction(
        USER, holding_id, {"kind": "buy", "date": "2026-01-05", "quantity": "1", "price": "1"}
    )
    r = await client.patch(
        f"/v1/portfolio/{holding_id}", json={"current_value": "13000"}, headers=AUTH
    )
    assert r.status_code == 422
    assert "transactions and prices" in r.json()["detail"]


async def test_a_holding_tracked_by_transactions_needs_no_declared_figures(client, mock_services):
    _uow(mock_services)
    r = await client.post(
        "/v1/portfolio/",
        json={"symbol": "VOO", "name": "S&P 500", "asset_class": "equity", "currency": "usd"},
        headers=AUTH,
    )
    assert r.status_code == 201
    holding = (await client.get(f"/v1/portfolio/{r.json()['id']}", headers=AUTH)).json()
    assert (holding["currency"], holding["current_value"], holding["native"]["currency"]) == (
        "LKR",
        "0.00",
        "USD",
    )
    # Declaring figures for it is refused: they would be in no currency it has.
    r = await client.post(
        "/v1/portfolio/",
        json={**FUND, "currency": "USD"},
        headers=AUTH,
    )
    assert r.status_code == 422
