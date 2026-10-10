"""
Holdings as the hosted apps already read them: every field they know keeps its
meaning — figures in the base currency — while a holding with transactions now
gets those figures from its lots and prices, and a holding without keeps the
ones the user declared.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from salli.application.services.portfolio_service import PortfolioService
from tests.fakes import FakeRecordsUoW
from tests.unit.application.test_portfolio_transactions import Rates

USER = "u1"
LEGACY_FIELDS = {
    "id",
    "symbol",
    "name",
    "asset_class",
    "currency",
    "cost_basis",
    "current_value",
    "is_active",
    "created_at",
    "updated_at",
}


def _service(base: str = "LKR", rates: dict[tuple[str, str], str] | None = None):
    uow = FakeRecordsUoW(base)
    return PortfolioService(lambda: uow, fx=Rates(rates), today=lambda: date(2026, 10, 9)), uow


async def _declared(svc: PortfolioService, symbol: str, asset_class: str, cost: str, value: str):
    return await svc.add_holding(
        USER,
        {
            "symbol": symbol,
            "name": symbol,
            "asset_class": asset_class,
            "cost_basis": cost,
            "current_value": value,
        },
    )


async def test_a_holding_declared_the_old_way_reads_as_it_always_has():
    svc, _ = _service()
    h = await _declared(svc, "BND", "bond", "5000", "4800.55")
    holding = await svc.get_holding(USER, h)
    assert holding is not None and set(holding) >= LEGACY_FIELDS
    assert (holding["currency"], holding["cost_basis"], holding["current_value"]) == (
        "LKR",
        "5000.00",
        "4800.55",
    )
    assert (holding["tracking"], holding["quantity"], holding["price"], holding["priced"]) == (
        "declared",
        None,
        None,
        None,
    )
    assert holding["native"] == {
        "currency": "LKR",
        "cost_basis": "5000.00",
        "current_value": "4800.55",
        "unrealised_gain": "-199.45",
    }
    assert holding["notes"] == []


async def test_once_it_has_transactions_its_figures_come_from_them():
    svc, _ = _service()
    h = await _declared(svc, "VOO", "equity", "10000", "12500")
    await svc.add_transaction(
        USER, h, {"kind": "transfer_in", "date": "2020-01-02", "quantity": "100", "amount": "9000"}
    )
    await svc.set_price(USER, {"symbol": "VOO", "close": "95", "date": "2026-10-08"})
    holding = await svc.get_holding(USER, h)
    assert holding is not None
    assert (holding["cost_basis"], holding["current_value"], holding["unrealised_gain"]) == (
        "9000.00",
        "9500.00",
        "500.00",
    )
    assert (holding["tracking"], holding["quantity"]) == ("transactions", "100")
    assert holding["price"] == {
        "date": "2026-10-08",
        "close": "95",
        "per_unit": "95",
        "source": "user",
    }
    # With its transactions gone, it is the holding it was declared as again.
    [tx] = await svc.list_transactions(USER, h) or []
    await svc.delete_transaction(USER, h, tx["id"])
    holding = await svc.get_holding(USER, h)
    assert holding is not None
    assert (holding["cost_basis"], holding["current_value"]) == ("10000.00", "12500.00")


async def test_a_foreign_holding_reads_in_the_base_currency_with_its_own_alongside():
    svc, _ = _service("LKR", {("USD", "LKR"): "301"})
    h = await svc.add_holding(
        USER, {"symbol": "VOO", "name": "S&P 500", "asset_class": "equity", "currency": "USD"}
    )
    await svc.add_transaction(
        USER,
        h,
        {"kind": "buy", "date": "2026-01-05", "quantity": "2", "price": "500", "fx_rate": "295"},
    )
    await svc.set_price(USER, {"symbol": "VOO", "close": "550", "date": "2026-10-08"})
    [holding] = await svc.list_holdings(USER)
    assert (holding["currency"], holding["cost_basis"], holding["current_value"]) == (
        "LKR",
        "295000.00",
        "331100.00",
    )
    assert holding["native"] == {
        "currency": "USD",
        "cost_basis": "1000.00",
        "current_value": "1100.00",
        "unrealised_gain": "100.00",
    }
    assert (holding["fx_rate"], holding["converted"]) == ("301", True)


async def test_the_summary_allocates_and_alerts_on_the_derived_figures():
    svc, _ = _service()
    await _declared(svc, "BND", "bond", "5000", "4800.55")
    equity = await svc.add_holding(USER, {"symbol": "VOO", "name": "VOO", "asset_class": "equity"})
    await svc.add_transaction(
        USER, equity, {"kind": "buy", "date": "2026-01-05", "quantity": "10", "price": "1000"}
    )
    await svc.set_price(USER, {"symbol": "VOO", "close": "1250", "date": "2026-10-08"})

    summary = await svc.get_summary(USER, {"equity": Decimal("0.6"), "bond": Decimal("0.4")})
    # The same portfolio the declared-only summary test describes, the
    # equity's 12,500 now 10 units at 1,250.
    assert (summary["total_value"], summary["total_cost_basis"], summary["total_gain"]) == (
        "17300.55",
        "15000.00",
        "2300.55",
    )
    assert summary["allocation"] == [
        {"asset_class": "bond", "current_value": "4800.55", "pct_of_portfolio": "0.2775"},
        {"asset_class": "equity", "current_value": "12500.00", "pct_of_portfolio": "0.7225"},
    ]
    assert [(a["asset_class"], a["drift_pct"]) for a in summary["alerts"]] == [
        ("bond", "-0.1225"),
        ("equity", "0.1225"),
    ]
    assert summary["notes"] == []


async def test_the_summary_says_what_it_carries_at_cost():
    svc, _ = _service()
    h = await svc.add_holding(USER, {"symbol": "PE", "name": "Private fund", "asset_class": "pe"})
    await svc.add_transaction(
        USER, h, {"kind": "transfer_in", "date": "2026-01-05", "quantity": "1", "amount": "100"}
    )
    summary = await svc.get_summary(USER)
    assert summary["total_value"] == "100.00"
    assert summary["notes"] == ["No price for PE: valued at what it cost"]


async def test_declared_figures_are_refused_for_a_holding_with_transactions():
    svc, _ = _service()
    h = await _declared(svc, "VOO", "equity", "1", "1")
    await svc.add_transaction(
        USER, h, {"kind": "buy", "date": "2026-01-05", "quantity": "1", "price": "1"}
    )
    with pytest.raises(ValueError, match="come from its transactions and prices"):
        await svc.update_holding(USER, h, {"current_value": "13000"})
    # Its name and class are still its own to change.
    await svc.update_holding(USER, h, {"name": "Vanguard S&P 500", "asset_class": "fund"})
    holding = await svc.get_holding(USER, h)
    assert holding is not None and (holding["name"], holding["asset_class"]) == (
        "Vanguard S&P 500",
        "fund",
    )
