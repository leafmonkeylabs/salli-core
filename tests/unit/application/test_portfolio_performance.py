"""
A period's gains, income and returns through PortfolioService: a tax year's
realised gains and income, every figure in the holding's currency and the base
one, and holdings without a history listed apart rather than guessed at.
"""

from __future__ import annotations

from datetime import date

import pytest

from salli.application.services.portfolio_service import PortfolioService
from tests.fakes import FakeRecordsUoW
from tests.unit.application.test_portfolio_transactions import Rates

USER = "u1"
TODAY = date(2026, 10, 9)
TAX_YEAR = ("2025-04-01", "2026-03-31")


def _service(base: str = "LKR", rates: dict[tuple[str, str], str] | None = None):
    uow = FakeRecordsUoW(base)
    fx = Rates(rates)
    return PortfolioService(lambda: uow, fx=fx, today=lambda: TODAY), uow, fx


async def _holding(svc: PortfolioService, symbol: str, currency: str | None = None) -> str:
    return await svc.add_holding(
        USER, {"symbol": symbol, "name": symbol, "asset_class": "equity", "currency": currency}
    )


async def _add(svc: PortfolioService, holding_id: str, **fields) -> None:
    assert await svc.add_transaction(USER, holding_id, fields) is not None


async def test_a_tax_years_gains_and_income():
    svc, _, _ = _service()
    h = await _holding(svc, "JKH")
    await _add(svc, h, kind="buy", date="2025-01-10", quantity="100", price="200", fees="50")
    await _add(svc, h, kind="sell", date="2025-06-01", quantity="40", price="250", fees="20")
    await _add(svc, h, kind="sell", date="2026-05-01", quantity="10", price="260")
    await _add(svc, h, kind="dividend", date="2025-08-01", amount="300", withholding_tax="45")
    await _add(svc, h, kind="dividend", date="2025-03-01", amount="100")

    report = await svc.get_performance(USER, *TAX_YEAR)
    assert report is not None
    assert (report["start"], report["end"], report["days"]) == ("2025-04-01", "2026-03-31", 365)
    year = report["portfolio"]
    # Only the June sale: 40 × 250 − 20 − 40 × (20050 / 100) = 1960.
    assert (year["realised_gain"], year["currency"]) == ("1960.00", "LKR")
    # Only the August dividend.
    assert (year["dividends"], year["withholding_tax"], year["net_income"]) == (
        "300.00",
        "45.00",
        "255.00",
    )
    [holding] = report["holdings"]
    assert holding["native"]["realised_gain"] == holding["base"]["realised_gain"] == "1960.00"

    since_inception = await svc.get_performance(USER)
    assert since_inception is not None
    # Both sales: 1960 + 10 × 260 − 2005 = 2555.
    assert since_inception["portfolio"]["realised_gain"] == "2555.00"
    assert since_inception["portfolio"]["dividends"] == "400.00"
    assert (since_inception["start"], since_inception["end"]) == ("2025-01-10", "2026-10-09")


async def test_wikipedias_example_4_through_the_service():
    # Bought 10 at $10 and 5 at $12, sold all 15 at $11: 10%, time-weighted.
    svc, _, _ = _service("USD")
    h = await _holding(svc, "X")
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="10", price="10")
    await _add(svc, h, kind="buy", date="2026-03-05", quantity="5", price="12")
    await _add(svc, h, kind="sell", date="2026-06-05", quantity="15", price="11")
    report = await svc.get_performance(USER, end="2026-06-30")
    assert report is not None
    figures = report["portfolio"]
    assert (figures["twr"], figures["total_return"], figures["paid_in"]) == (
        "0.100000",
        "5.00",
        "160.00",
    )
    # Less than a year: not annualised.
    assert figures["twr_annualised"] is None and figures["xirr"] is not None


async def test_a_foreign_holding_in_both_currencies():
    svc, _, fx = _service("LKR", {("USD", "LKR"): "310"})
    h = await _holding(svc, "VOO", "USD")
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="2", price="100", fx_rate="300")
    await svc.set_price(USER, {"symbol": "VOO", "close": "110", "date": "2026-09-30"})
    report = await svc.get_performance(USER, end="2026-09-30")
    assert report is not None
    [holding] = report["holdings"]
    assert (holding["native"]["currency"], holding["native"]["total_return"]) == ("USD", "20.00")
    # 220 USD at 310 is 68,200 rupees, for 60,000 paid.
    assert (holding["base"]["currency"], holding["base"]["total_return"]) == ("LKR", "8200.00")
    assert holding["native"]["twr"] == "0.100000"
    assert holding["base"]["twr"] == "0.136667"
    assert fx.asked == [("USD", "LKR", "2026-09-30")]
    assert holding["notes"] == []


async def test_a_missing_rate_is_carried_at_cost_and_said():
    svc, _, _ = _service("LKR")
    h = await _holding(svc, "VOO", "USD")
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="2", price="100", fx_rate="300")
    await svc.set_price(USER, {"symbol": "VOO", "close": "110", "date": "2026-09-30"})
    report = await svc.get_performance(USER, end="2026-09-30")
    assert report is not None
    [holding] = report["holdings"]
    assert holding["base"]["total_return"] == "0.00"
    assert holding["notes"] == [
        "No USD→LKR rate for 2026-09-30: VOO's value in LKR is carried at what it cost"
    ]


async def test_inactive_holdings_count_and_declared_ones_are_listed_apart():
    svc, _, _ = _service()
    sold = await _holding(svc, "OLD")
    await _add(svc, sold, kind="buy", date="2025-05-01", quantity="1", price="100")
    await _add(svc, sold, kind="sell", date="2025-07-01", quantity="1", price="150")
    await svc.update_holding(USER, sold, {"is_active": False})
    await svc.add_holding(
        USER,
        {
            "symbol": "fd",
            "name": "Fixed deposit",
            "asset_class": "cash",
            "cost_basis": "1000",
            "current_value": "1100",
        },
    )
    report = await svc.get_performance(USER, *TAX_YEAR)
    assert report is not None
    assert report["portfolio"]["realised_gain"] == "50.00"
    assert [(h["symbol"], h["is_active"]) for h in report["holdings"]] == [("OLD", False)]
    assert report["notes"] == [
        "Declared by value, with no transactions to measure, so not in these figures: FD"
    ]


async def test_one_holdings_performance():
    svc, _, _ = _service()
    a = await _holding(svc, "A")
    b = await _holding(svc, "B")
    await _add(svc, a, kind="buy", date="2026-01-05", quantity="1", price="100")
    await _add(svc, b, kind="buy", date="2026-01-05", quantity="1", price="200")
    report = await svc.get_performance(USER, holding_id=b)
    assert report is not None
    assert [h["holding_id"] for h in report["holdings"]] == [b]
    assert report["portfolio"]["paid_in"] == "200.00"
    assert await svc.get_performance(USER, holding_id="nope") is None
    assert await svc.get_performance("someone-else", holding_id=b) is None


async def test_a_period_cannot_end_before_it_starts():
    svc, _, _ = _service()
    with pytest.raises(ValueError, match="starts"):
        await svc.get_performance(USER, "2026-04-01", "2026-03-31")


async def test_an_empty_portfolio_has_nothing_to_measure():
    svc, _, _ = _service()
    report = await svc.get_performance(USER)
    assert report is not None
    assert report["holdings"] == [] and report["portfolio"]["twr"] is None
    assert (report["start"], report["end"]) == ("2026-10-09", "2026-10-09")
