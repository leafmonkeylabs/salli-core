"""
Prices a user keeps, and what a holding is worth at them: quantity × the latest
price, converted at the rate of the price's own day, and carried at cost —
saying so — when there is no price or no rate.
"""

from __future__ import annotations

from datetime import date

import pytest

from salli.application.services.portfolio_service import PortfolioService
from salli.domain.portfolio.lots import TransactionError
from tests.fakes import FakeRecordsUoW
from tests.unit.application.test_portfolio_transactions import Rates

USER = "u1"
TODAY = date(2026, 10, 9)


def _service(base: str = "LKR", rates: dict[tuple[str, str], str] | None = None):
    uow = FakeRecordsUoW(base)
    fx = Rates(rates)
    return PortfolioService(lambda: uow, fx=fx, today=lambda: TODAY), uow, fx


async def _holding(svc: PortfolioService, symbol: str = "VOO", currency: str | None = None) -> str:
    return await svc.add_holding(
        USER, {"symbol": symbol, "name": symbol, "asset_class": "equity", "currency": currency}
    )


async def _add(svc: PortfolioService, holding_id: str, **fields) -> str:
    tx_id = await svc.add_transaction(USER, holding_id, fields)
    assert tx_id is not None
    return tx_id


# ── recording prices ──────────────────────────────────────────────────────────


async def test_a_price_is_in_its_holdings_currency_and_dated_today_unless_told():
    svc, uow, _ = _service("LKR", {("USD", "LKR"): "300"})
    await _holding(svc, "voo", "USD")
    quote_id = await svc.set_price(USER, {"symbol": "VOO", "close": "512.25"})
    [row] = uow.holding_prices.rows.values()
    assert (row["id"], row["symbol"], row["price_date"], row["currency"], row["source"]) == (
        quote_id,
        "VOO",
        "2026-10-09",
        "USD",
        "user",
    )


async def test_recording_a_days_price_again_replaces_it():
    svc, uow, _ = _service()
    await _holding(svc)
    first = await svc.set_price(USER, {"symbol": "VOO", "close": "1", "date": "2026-10-01"})
    second = await svc.set_price(USER, {"symbol": "voo", "close": "2", "date": "2026-10-01"})
    assert first == second and len(uow.holding_prices.rows) == 1
    [price] = await svc.list_prices(USER, "VOO")
    assert price["close"] == "2"


async def test_a_price_for_a_symbol_no_holding_has_needs_its_currency():
    svc, _, _ = _service()
    with pytest.raises(ValueError, match="Say which currency"):
        await svc.set_price(USER, {"symbol": "BTC", "close": "60000"})
    assert await svc.set_price(USER, {"symbol": "BTC", "close": "60000", "currency": "usd"})


@pytest.mark.parametrize("close", ["0", "-1", "abc", "NaN", None])
async def test_a_close_is_a_positive_number(close):
    svc, _, _ = _service()
    await _holding(svc)
    with pytest.raises(TransactionError, match="close"):
        await svc.set_price(USER, {"symbol": "VOO", "close": close})


async def test_prices_list_newest_first_and_can_be_deleted():
    svc, _, _ = _service()
    await _holding(svc)
    await _holding(svc, "BND")
    await svc.set_price(USER, {"symbol": "VOO", "close": "1", "date": "2026-10-01"})
    newest = await svc.set_price(USER, {"symbol": "VOO", "close": "2", "date": "2026-10-02"})
    await svc.set_price(USER, {"symbol": "BND", "close": "3", "date": "2026-10-03"})
    assert [p["close"] for p in await svc.list_prices(USER, "voo")] == ["2", "1"]
    assert [p["symbol"] for p in await svc.list_prices(USER)] == ["BND", "VOO", "VOO"]
    assert [p["date"] for p in await svc.list_prices(USER, start="2026-10-02")] == [
        "2026-10-03",
        "2026-10-02",
    ]
    assert await svc.delete_price(USER, newest) is True
    assert await svc.delete_price(USER, newest) is False
    assert [p["close"] for p in await svc.list_prices(USER, "VOO")] == ["1"]


# ── valuing a holding ─────────────────────────────────────────────────────────


async def test_a_holding_is_worth_its_quantity_at_the_latest_price():
    svc, _, _ = _service()
    h = await _holding(svc)
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="10", price="100", fees="5")
    await svc.set_price(USER, {"symbol": "VOO", "close": "120.5", "date": "2026-10-08"})
    valuation = await svc.get_valuation(USER, h)
    assert valuation is not None
    assert {
        k: valuation[k] for k in ("quantity", "value", "cost", "unrealised_gain", "value_base")
    } == {
        "quantity": "10",
        "value": "1205.00",
        "cost": "1005.00",
        "unrealised_gain": "200.00",
        "value_base": "1205.00",
    }
    assert valuation["price"] == {
        "date": "2026-10-08",
        "close": "120.5",
        "per_unit": "120.5",
        "source": "user",
    }
    assert (valuation["priced"], valuation["converted"], valuation["notes"]) == (True, True, [])


async def test_a_foreign_holding_converts_at_the_rate_of_the_prices_own_day():
    svc, _, fx = _service("LKR", {("USD", "LKR"): "301.25"})
    h = await _holding(svc, currency="USD")
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="2", price="100", fx_rate="290")
    await svc.set_price(USER, {"symbol": "VOO", "close": "110", "date": "2026-09-30"})
    valuation = await svc.get_valuation(USER, h)
    assert valuation is not None
    # Asked for 30 September's rate — the price's day — not today's.
    assert fx.asked == [("USD", "LKR", "2026-09-30")]
    assert (valuation["value"], valuation["fx_rate"], valuation["value_base"]) == (
        "220.00",
        "301.25",
        "66275.00",
    )
    # Cost 200 USD at 290; the gain in rupees includes what the rate did.
    assert (valuation["cost_base"], valuation["unrealised_gain_base"]) == ("58000.00", "8275.00")


async def test_a_rate_the_users_own_transactions_carry_is_used_for_that_day():
    svc, _, fx = _service("LKR")
    h = await _holding(svc, currency="USD")
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="100", fx_rate="290")
    await _add(svc, h, kind="dividend", date="2026-09-30", amount="1", fx_rate="305")
    await svc.set_price(USER, {"symbol": "VOO", "close": "110", "date": "2026-09-30"})
    valuation = await svc.get_valuation(USER, h)
    assert valuation is not None
    assert fx.asked == [] and valuation["fx_rate"] == "305"


async def test_without_a_rate_for_the_prices_day_the_base_value_is_carried_at_cost():
    svc, _, _ = _service("LKR")
    h = await _holding(svc, currency="USD")
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="2", price="100", fx_rate="290")
    await svc.set_price(USER, {"symbol": "VOO", "close": "110", "date": "2026-09-30"})
    valuation = await svc.get_valuation(USER, h)
    assert valuation is not None
    assert (valuation["value"], valuation["value_base"], valuation["cost_base"]) == (
        "220.00",
        "58000.00",
        "58000.00",
    )
    assert (valuation["priced"], valuation["converted"]) == (True, False)
    assert valuation["notes"] == [
        "No USD→LKR rate for 2026-09-30: VOO's value in LKR is carried at what it cost"
    ]


async def test_without_any_price_a_holding_is_valued_at_what_it_cost():
    svc, _, _ = _service()
    h = await _holding(svc)
    await _add(svc, h, kind="transfer_in", date="2015-03-01", quantity="50", amount="2500")
    valuation = await svc.get_valuation(USER, h)
    assert valuation is not None
    assert (valuation["value"], valuation["unrealised_gain"], valuation["price"]) == (
        "2500.00",
        "0.00",
        None,
    )
    assert valuation["notes"] == ["No price for VOO: valued at what it cost"]


async def test_a_price_in_another_currency_is_not_the_holdings():
    svc, _, _ = _service("LKR")
    h = await _holding(svc)
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="100")
    await svc.set_price(USER, {"symbol": "VOO", "close": "1", "currency": "USD"})
    valuation = await svc.get_valuation(USER, h)
    assert valuation is not None
    assert valuation["price"] is not None and valuation["price"]["source"] == "trade"
    assert valuation["notes"] == [
        "1 recorded price(s) for VOO are not in LKR, so are not this holding's"
    ]


async def test_a_holding_declared_by_value_keeps_its_figures():
    svc, _, _ = _service()
    h = await svc.add_holding(
        USER,
        {
            "symbol": "FD",
            "name": "Fixed deposit",
            "asset_class": "cash",
            "cost_basis": "1000",
            "current_value": "1100",
        },
    )
    valuation = await svc.get_valuation(USER, h)
    assert valuation is not None
    assert (valuation["tracking"], valuation["value_base"], valuation["unrealised_gain"]) == (
        "declared",
        "1100.00",
        "100.00",
    )
    assert await svc.get_valuation("someone-else", h) is None
