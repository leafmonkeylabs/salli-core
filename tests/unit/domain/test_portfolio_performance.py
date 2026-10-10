"""
A period's gains, income and returns, per holding and for the portfolio. The
expected figures are worked by hand in the comments.

The portfolio below is kept in USD and holds:
  A, in USD: 10 bought at 100 on 10 January; closes at 110 on 31 March.
  B, in EUR: 5 bought at 200 on 10 February at 1.10 USD per EUR; closes at
     210 on 31 March, when a euro is 1.20.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext

from salli.domain.portfolio.lots import EXACT, Kind, Transaction
from salli.domain.portfolio.performance import History, report, valuation_days
from salli.domain.portfolio.returns import RATE
from salli.domain.portfolio.valuation import Close, Pricing

D = Decimal
END = date(2026, 3, 31)

A = [Transaction("a1", Kind.BUY, date(2026, 1, 10), quantity=D(10), price=D(100))]
B = [Transaction("b1", Kind.BUY, date(2026, 2, 10), quantity=D(5), price=D(200), fx_rate=D("1.1"))]


def _a(history=A, closes=(Close(END, D(110), "user"),)) -> History:
    # A is in the base currency: a rate of 1 on every day it has a close.
    return History("A", history, Pricing(history, closes), {c.on: D(1) for c in closes})


def _b(rates=None) -> History:
    pricing = Pricing(B, [Close(END, D(210), "user")])
    return History("B", B, pricing, {END: D("1.2")} if rates is None else rates)


def _npv(flows: list[tuple[date, Decimal]], rate: Decimal) -> Decimal:
    first = flows[0][0]
    with localcontext(RATE):
        return sum((a / (1 + rate) ** (D((on - first).days) / 365) for on, a in flows), D(0))


def test_since_inception_across_two_currencies():
    result = report([_a(), _b()], None, END)
    a, b = (h.base for h in result.holdings)
    assert result.start == date(2026, 1, 10)
    # A: 1000 in, worth 1100. B: 1000 EUR in at 1.10 (1100 USD), worth
    # 5 × 210 × 1.20 = 1260 USD.
    assert (a.paid_in, a.closing_value, a.total_return) == (D(1000), D(1100), D(100))
    assert (b.paid_in, b.closing_value, b.total_return) == (D(1100), D(1260), D(160))
    # B in its own currency: 1000 in, worth 1050 — the rest is the euro.
    assert result.holdings[1].native.total_return == D(50)
    assert (result.holdings[0].native.twr, result.holdings[1].native.twr) == (
        D("0.1"),
        D("0.05"),
    )

    portfolio = result.portfolio
    assert (portfolio.paid_in, portfolio.closing_value, portfolio.total_return) == (
        D(2100),
        D(2360),
        D(260),
    )
    assert portfolio.closing_unrealised == D(260)
    # Nothing moved between the flows but money: the portfolio grew from 2100
    # to 2360 after its last contribution, 12.38095…%.
    assert portfolio.twr is not None
    assert portfolio.twr.quantize(D("1e-12")) == D("0.123809523810")
    # The money-weighted rate discounts −1000, −1100 and +2360 to nothing.
    assert portfolio.xirr is not None
    flows = [(date(2026, 1, 10), D(-1000)), (date(2026, 2, 10), D(-1100)), (END, D(2360))]
    assert abs(_npv(flows, portfolio.xirr)) < D("1e-10")


def test_a_period_starts_from_what_was_held_the_day_before():
    result = report([_a(), _b()], date(2026, 2, 11), END)
    portfolio = result.portfolio
    # Held on 10 February: A at its last trade (1000), B at its own (1100).
    assert (portfolio.opening_value, portfolio.paid_in, portfolio.closing_value) == (
        D(2100),
        D(0),
        D(2360),
    )
    assert portfolio.twr is not None and portfolio.xirr is not None
    with localcontext(RATE):
        assert portfolio.twr == D(2360) / D(2100) - 1
        # 49 days from the eve of the period to its close; the solver stops
        # within 10⁻¹⁶ of ln(1 + r) (see returns.xirr).
        exact = (D(2360) / D(2100)) ** (D(365) / D(49)) - 1
        assert abs(portfolio.xirr - exact) < D("1e-15")
    assert (result.start, result.days) == (date(2026, 2, 11), 49)


def test_only_sales_and_income_in_the_period_count():
    history = [
        *A,
        Transaction("s1", Kind.SELL, date(2026, 3, 15), quantity=D(4), price=D(120)),
        Transaction(
            "d1",
            Kind.DIVIDEND,
            date(2026, 2, 1),
            amount=D(10),
            withholding_tax=D("1.5"),
        ),
        Transaction("i1", Kind.INTEREST, date(2026, 3, 20), amount=D(2)),
    ]
    whole = report([_a(history)], None, END).holdings[0].native
    # 4 × 120 − 4 × 100 = 80.
    assert (whole.realised, whole.dividends, whole.interest) == (D(80), D(10), D(2))
    assert (whole.withholding_tax, whole.net_income) == (D("1.5"), D("10.5"))

    march = report([_a(history)], date(2026, 3, 1), END).holdings[0].native
    assert (march.realised, march.dividends, march.interest, march.net_income) == (
        D(80),
        D(0),
        D(2),
        D(2),
    )
    late = report([_a(history)], date(2026, 3, 16), END).holdings[0].native
    assert (late.realised, late.net_income) == (D(0), D(2))


def test_total_return_is_realised_plus_income_plus_the_change_in_unrealised():
    history = [
        *A,
        Transaction("s1", Kind.SELL, date(2026, 3, 15), quantity=D(4), price=D(120), fees=D(3)),
        Transaction("d1", Kind.DIVIDEND, date(2026, 2, 1), amount=D(10), withholding_tax=D(1)),
    ]
    for start in (None, date(2026, 1, 31), date(2026, 3, 16)):
        f = report([_a(history)], start, END).holdings[0].native
        with localcontext(EXACT):
            assert f.total_return == (
                f.realised + f.net_income + f.closing_unrealised - f.opening_unrealised
            )


def test_income_paid_after_everything_was_sold_counts_for_the_time_it_was_held():
    history = [
        Transaction("b1", Kind.BUY, date(2026, 1, 5), quantity=D(10), price=D(10)),
        Transaction("s1", Kind.SELL, date(2026, 2, 5), quantity=D(10), price=D(11)),
        Transaction("d1", Kind.DIVIDEND, date(2026, 3, 5), amount=D(5)),
    ]
    figures = report([_a(history, ())], None, END).holdings[0].native
    # 100 in; 110 and then 5 out: 15%, the way the money says.
    assert figures.twr == D("0.15")
    assert figures.total_return == D(15)


def test_valuations_carried_at_cost_are_listed():
    gift = [
        Transaction(
            "t1", Kind.TRANSFER_IN, date(2026, 1, 5), quantity=D(3), amount=D(30), fx_rate=D(2)
        )
    ]
    unpriced = History("G", gift, Pricing(gift, []), {})
    result = report([unpriced, _b(rates={})], None, END)
    g, b = result.holdings
    assert {a.missing for a in g.at_cost} == {"price"}
    assert (g.base.closing_value, g.base.total_return) == (D(60), D(0))
    # B has a close on 31 March but no rate for it: valued in euros, carried
    # at its cost in dollars.
    assert [(a.on, a.missing, a.price_on) for a in b.at_cost] == [(END, "rate", END)]
    assert (b.native.closing_value, b.base.closing_value) == (D(1050), D(1100))


def test_the_days_a_report_values_on_are_the_eve_each_flow_and_the_end():
    days = valuation_days([_a(), _b()], date(2026, 1, 1), END)
    assert days == [date(2025, 12, 31), date(2026, 1, 10), date(2026, 2, 10), END]
    assert valuation_days([_a()], None, END) == [date(2026, 1, 10), END]
