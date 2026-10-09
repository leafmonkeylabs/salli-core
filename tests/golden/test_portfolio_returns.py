"""
Time- and money-weighted returns against published worked examples.

Sources:
- Wikipedia, "Time-weighted return" (https://en.wikipedia.org/wiki/Time-weighted_return),
  Example 1 ("the problem of external flows"), Example 3 (annualising) and
  Example 4 ("internal flows and security performance").
- Microsoft Support, "XIRR function"
  (https://support.microsoft.com/en-us/office/xirr-function-de1242ec-6477-445b-b11b-a303ad9adc9d),
  the worked example, whose stated result is 0.373362535.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from salli.domain.portfolio.lots import Kind, Transaction
from salli.domain.portfolio.performance import History, report
from salli.domain.portfolio.returns import Day, Flow, annualised, twr, xirr
from salli.domain.portfolio.valuation import Pricing

D = Decimal


def _rounded(value: Decimal | None, places: int) -> Decimal:
    assert value is not None
    return value.quantize(Decimal(1).scaleb(-places))


# ── time-weighted ─────────────────────────────────────────────────────────────


def test_wikipedia_example_1_a_contribution_does_not_count_as_growth():
    # $500 at the start of year 1 doubles to $1,000; $1,000 more goes in at
    # the start of year 2, and the $2,000 ends the year at $1,500. Year 1 grew
    # 100%, year 2 fell 25%: (1 + 1) × (1 − 0.25) − 1 = 50%.
    days = [Day(date(2021, 1, 1), before=D(1000), after=D(2000), inflow=D(1000), outflow=D(0))]
    assert twr(D(500), days, D(1500)) == D("0.5")


def test_wikipedia_example_4_a_holding_bought_twice_and_sold():
    # 10 shares bought at $10, 5 more at $12, all 15 sold at $11. Growth
    # factors 120/100 = 1.2 and 165/180, so the return is 10% — the share
    # price's own return, whatever the investor's timing.
    history = [
        Transaction("b1", Kind.BUY, date(2026, 1, 5), quantity=D(10), price=D(10)),
        Transaction("b2", Kind.BUY, date(2026, 3, 5), quantity=D(5), price=D(12)),
        Transaction("s1", Kind.SELL, date(2026, 6, 5), quantity=D(15), price=D(11)),
    ]
    holding = History("h", history, Pricing(history, []), {})
    figures = report([holding], None, date(2026, 12, 31)).holdings[0].native
    assert _rounded(figures.twr, 12) == D("0.100000000000")
    # The same money, dollar for dollar: $160 in, $165 out.
    assert (figures.paid_in, figures.taken_out, figures.total_return) == (D(160), D(165), D(5))
    assert figures.realised == D(5)


def test_wikipedia_example_3_annualising_five_years():
    # +10% a year for two years and −3% a year for three: 1.1² × 0.97³ − 1
    # ≈ 10.4334% over the five years, ≈ 2.00% a year.
    cumulative = D("1.1") ** 2 * D("0.97") ** 3 - 1
    assert _rounded(cumulative, 6) == D("0.104334")
    yearly = annualised(cumulative, 5 * 365)
    assert _rounded(yearly, 4) == D("0.0200")


def test_a_short_period_is_not_annualised():
    assert annualised(D("0.05"), 364) is None


# ── money-weighted ────────────────────────────────────────────────────────────


def test_microsofts_xirr_example():
    flows = [
        Flow(date(2008, 1, 1), D(-10000)),
        Flow(date(2008, 3, 1), D(2750)),
        Flow(date(2008, 10, 30), D(4250)),
        Flow(date(2009, 2, 15), D(3250)),
        Flow(date(2009, 4, 1), D(2750)),
    ]
    # Excel stops iterating once within 0.000001 percent, so its 0.373362535
    # agrees with the root, 0.37336253351…, to eight places.
    assert _rounded(xirr(flows), 8) == D("0.37336253")
    assert _rounded(xirr(flows), 11) == D("0.37336253352")


def test_a_year_at_ten_percent_is_ten_percent():
    flows = [Flow(date(2021, 1, 1), D(-100)), Flow(date(2022, 1, 1), D(110))]
    assert _rounded(xirr(flows), 20) == D("0.1")


def test_of_several_rates_the_one_nearest_zero_is_the_answer():
    # −100, +230, −132 a year apart is discounted to nothing at both 10% and
    # 20% (100u² − 230u + 132 = 0 for u = 1 + r).
    flows = [
        Flow(date(2021, 1, 1), D(-100)),
        Flow(date(2022, 1, 1), D(230)),
        Flow(date(2023, 1, 1), D(-132)),
    ]
    assert _rounded(xirr(flows), 15) == D("0.1")


def test_no_rate_without_money_both_ways_or_over_time():
    assert xirr([Flow(date(2021, 1, 1), D(-100)), Flow(date(2022, 1, 1), D(-5))]) is None
    assert xirr([Flow(date(2021, 1, 1), D(-100)), Flow(date(2021, 1, 1), D(110))]) is None
    assert xirr([]) is None


def test_rates_over_days_are_found_however_far_they_annualise():
    # −10% in a day and +100% in three both annualise past e^±30: the search
    # widens with the flows' span rather than coming back empty.
    loss = xirr([Flow(date(2026, 1, 1), D(-100)), Flow(date(2026, 1, 2), D(90))])
    assert loss is not None and abs(loss - (D("0.9") ** 365 - 1)) < D("1e-15")
    gain = xirr([Flow(date(2026, 1, 1), D(-100)), Flow(date(2026, 1, 4), D(200))])
    assert gain is not None
    expected = D(2) ** (D(365) / D(3)) - 1
    assert abs(gain / expected - 1) < D("1e-14")
