"""Risk figures from monthly returns, a benchmark series, running costs, and
average-cost sales."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from salli.domain.insurance import engine as insurance
from salli.domain.portfolio import engine, risk
from salli.domain.portfolio.lots import Kind, LotPick, Transaction, TransactionError, replay


def test_month_windows_clip_to_the_period():
    assert risk.month_windows(date(2026, 1, 20), date(2026, 3, 5)) == [
        (date(2026, 1, 20), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 5)),
    ]


def test_volatility_drawdown_and_sharpe():
    monthly = [Decimal("0.10"), Decimal("-0.10"), Decimal("0.05"), Decimal("-0.05")]
    f = risk.figures(monthly, Decimal("0.02"))
    assert f.months == 4
    # Growth 1.1, 0.99, 1.0395, 0.987525: from the 1.1 high, a 10.225% fall.
    assert f.max_drawdown == Decimal("0.102250")
    assert f.volatility is not None and f.volatility.quantize(Decimal("0.0001")) == Decimal(
        "0.3162"
    )
    assert f.sharpe is not None and f.sharpe < 0
    assert risk.figures([Decimal("0.01")], Decimal(0)).volatility is None


def test_a_benchmark_series_needs_a_close_before_every_month():
    windows = risk.month_windows(date(2026, 1, 1), date(2026, 2, 28))
    closes = [
        (date(2025, 12, 31), Decimal(100)),
        (date(2026, 1, 31), Decimal(110)),
        (date(2026, 2, 27), Decimal(99)),
    ]
    assert risk.series_returns(closes, windows) == [Decimal("0.1"), Decimal("-0.1")]
    assert risk.series_returns(closes[1:], windows) is None


def test_running_costs_weight_the_expense_ratios_by_value():
    costs = engine.running_costs(
        [
            ("AAA", Decimal(30000), Decimal("0.001")),
            ("BBB", Decimal(10000), Decimal("0.009")),
            ("CCC", Decimal(5000), None),
        ]
    )
    assert costs == {
        "weighted_expense_ratio": "0.003000",
        "yearly_cost": "120.00",
        "value_covered": "40000.00",
        "without_ratio": ["CCC"],
    }


def _buys_then_sale(lots: tuple[LotPick, ...] = ()) -> list[Transaction]:
    return [
        Transaction("b1", Kind.BUY, date(2026, 1, 5), quantity=Decimal(10), price=Decimal(10)),
        Transaction("b2", Kind.BUY, date(2026, 2, 5), quantity=Decimal(10), price=Decimal(20)),
        Transaction(
            "s1", Kind.SELL, date(2026, 3, 5), quantity=Decimal(10), price=Decimal(25), lots=lots
        ),
    ]


def test_average_cost_sells_at_the_average_cost_per_unit():
    fifo = replay(_buys_then_sale()).sales[0]
    average = replay(_buys_then_sale(), method="average").sales[0]
    assert fifo.cost == 100 and fifo.gain == 150
    assert average.cost == 150 and average.gain == 100
    assert replay(_buys_then_sale(), method="average").position.cost == 150
    with pytest.raises(TransactionError, match="average cost"):
        replay(_buys_then_sale((LotPick("b2", Decimal(10)),)), method="average")


def test_insurance_needs_are_figures_from_income_debts_goals_and_assets():
    n = insurance.needs(
        Decimal(3000),
        Decimal(2000),
        Decimal(50000),
        Decimal(10000),
        Decimal(40000),
        Decimal(100000),
        10,
    )
    assert n.income_replacement == 360000
    assert n.life_cover_need == 380000 and n.life_cover_gap == 280000
    assert n.income_protection_monthly == 2000
    assert (
        insurance.needs(
            Decimal(0), Decimal(0), Decimal(0), Decimal(0), Decimal(1), Decimal(0), 5
        ).life_cover_need
        == 0
    )


def test_tracking_error_and_a_blended_benchmark():
    from salli.domain.portfolio import risk as r

    own = [Decimal("0.02"), Decimal("0.01"), Decimal("-0.01")]
    same = r.tracking_error(own, own)
    assert same == 0
    assert r.tracking_error(own, own[:2]) is None
    blended = r.blend([(Decimal("0.6"), [Decimal("0.05")] * 2), (Decimal("0.4"), [Decimal(0)] * 2)])
    assert blended == [Decimal("0.030"), Decimal("0.030")]
    error = r.tracking_error(own, [Decimal(0)] * 3)
    assert error is not None and error > 0
