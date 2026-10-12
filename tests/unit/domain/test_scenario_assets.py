"""
An asset a scenario buys, and a recurring amount that grows beyond
inflation (domain/scenarios/engine.py, domain/baseline/timelines.py): the
price out of cash on the day, the asset among other assets from that
month's end, growing at its own real growth and counted in net worth at its
value less its selling costs; a recurring change's `real_growth` compounded
monthly from its start's month.

The books are in Swiss francs, as of 2030-03-31: a salary of 5,000.00 on the
25th and rent of 1,800.00 on the 1st, October to March, and 400,000.00 in
the bank.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal as D
from typing import Any

import pytest

from salli.domain.baseline import Baseline, fi, timelines
from salli.domain.scenarios import engine, schema
from tests.baseline_ledger import Ledger

AS_OF = dt.date(2030, 3, 31)


def books(**assume: str) -> Ledger:
    ledger = Ledger("CHF")
    ledger.account("bank", "asset")
    ledger.account("card", "liability")
    ledger.account("pay", "income")
    ledger.account("rent", "expense")
    ledger.account("eq", "equity")
    ledger.book("2029-09-30", "bank", "eq", "400000")
    for year, month in [(2029, 10), (2029, 11), (2029, 12), (2030, 1), (2030, 2), (2030, 3)]:
        ledger.book(f"{year}-{month:02d}-01", "rent", "bank", "1800", description="LAKESIDE FLATS")
        ledger.book(f"{year}-{month:02d}-25", "bank", "pay", "5000", description="ORBIT PAY")
    ledger.assume(surplus_invested="0", **assume)
    return ledger


@pytest.fixture(scope="module")
def baseline() -> Baseline:
    return books().baseline(AS_OF)


def doc(*changes: dict[str, Any], years: int = 5) -> schema.Scenario:
    return schema.load(
        {"schema": "salli.scenario/1", "horizon_years": years, "changes": list(changes)}
    )


HOME = {"type": "asset", "price": "600000.00", "date": "2030-05-15", "label": "A flat"}


def points(baseline: Baseline, scenario: schema.Scenario) -> dict[str, timelines.MonthPoint]:
    changes = engine.translate(baseline, scenario).changes
    return {
        p.month: p for p in timelines.monthly(baseline, scenario.horizon_years, changes).points[1:]
    }


def test_the_price_leaves_cash_and_the_asset_counts_from_its_month(baseline: Baseline):
    """Bought on 2030-05-15 for 600,000.00 from cash: by the end of May,
    cash is 600,000.00 lower and other assets 600,000.00 higher, so net worth
    is where it was. Nothing changes in April."""
    base, mine = points(baseline, doc()), points(baseline, doc(HOME))
    assert mine["2030-04"].other_assets == base["2030-04"].other_assets == 0
    assert mine["2030-05"].cash - base["2030-05"].cash == D("-600000.00")
    assert mine["2030-05"].other_assets == mine["2030-05"].other_assets_value == D("600000.00")
    assert mine["2030-05"].net_worth == base["2030-05"].net_worth
    assert mine["2034-03"].net_worth == base["2034-03"].net_worth


def test_an_asset_grows_at_its_real_growth_a_twelfth_a_month_from_the_next():
    """6% a year: 0.5% a month from June, compounded. By the end of
    December, seven months on: 600,000 × 1.005^7 = 621,317.64 (to the
    centime). Less selling costs of 4%: 596,464.93 counted."""
    baseline = books().baseline(AS_OF)
    grown = points(baseline, doc({**HOME, "real_growth": "0.06", "selling_costs": "0.04"}))
    assert grown["2030-05"].other_assets_value == D("600000.00")
    december = grown["2030-12"]
    assert december.other_assets_value.quantize(D("0.01")) == D("621317.64")
    assert december.other_assets.quantize(D("0.01")) == D("596464.93")
    assert december.other_assets == december.other_assets_value * D("0.96")


def test_selling_costs_come_off_net_worth_from_the_purchase(baseline: Baseline):
    """At 3%, the asset counts at 582,000.00, its value 600,000.00 beside
    it: net worth is 18,000.00 lower from the end of May."""
    base = points(baseline, doc())
    mine = points(baseline, doc({**HOME, "selling_costs": "0.03"}))
    may = mine["2030-05"]
    assert (may.other_assets, may.other_assets_value) == (D("582000.00"), D("600000.00"))
    assert may.net_worth - base["2030-05"].net_worth == D("-18000.00")


def test_in_todays_money_the_price_is_deflated_to_its_month():
    """With inflation of 2.4% (0.2% a month), the price paid in May is
    600,000 over May's price level in today's money; with no growth beyond
    inflation it keeps that value in today's money."""
    baseline = books(inflation="0.024").baseline(AS_OF)
    mine = points(baseline, doc(HOME))
    months = timelines.periods(AS_OF, 3)
    may = timelines.deflators(baseline, months)[2]
    assert mine["2030-05"].other_assets == D("600000.00") / may
    assert mine["2031-05"].other_assets == mine["2030-05"].other_assets


def test_a_result_shows_the_value_and_what_it_would_fetch(baseline: Baseline):
    result = engine.run(baseline, doc({**HOME, "selling_costs": "0.03"}))
    one = result.monthly[0]
    assert (one.other_assets.scenario, one.other_assets.delta) == (D("582000.00"), D("582000.00"))
    assert one.other_assets_value.scenario == D("600000.00")
    assert one.cash.delta == D("-600000.00")
    assert one.net_worth.delta == D("-18000.00")


def test_an_asset_funds_no_withdrawals(baseline: Baseline):
    """FI's asset base counts cash and investments, never what a home is
    worth: paid from cash, it lowers the base by its price."""
    mine = points(baseline, doc(HOME))
    base = points(baseline, doc())
    assert fi.asset_base(mine["2030-05"]) - fi.asset_base(base["2030-05"]) == D("-600000.00")


def test_without_a_growth_of_its_own_it_is_a_placeholder(baseline: Baseline):
    assert "asset_growth" in engine.run(baseline, doc(HOME)).placeholders
    stated = engine.run(baseline, doc({**HOME, "real_growth": "0"}))
    assert "asset_growth" not in stated.placeholders


def test_an_asset_is_checked_like_any_change(baseline: Baseline):
    with pytest.raises(engine.ScenarioError) as error:
        engine.translate(
            baseline,
            doc({**HOME, "date": "2030-03-01", "price": "1.005", "from": "card"}),
        )
    found = {p.path: p.message for p in error.value.problems}
    assert set(found) == {"changes[0].date", "changes[0].price", "changes[0].from"}
    assert "before the as-of date" in found["changes[0].date"]


# ── A recurring amount's real growth ─────────────────────────────────────────

RENT = {
    "type": "recurring",
    "amount": "-2000.00",
    "cadence": "monthly",
    "start": "2030-04-01",
    "label": "A new rent",
}


def _regular(baseline: Baseline, change: dict[str, Any]) -> list[tuple[str, D]]:
    flows = engine.translate(baseline, doc(change)).changes.regular
    return [(f.date, f.amount) for f in flows]


def test_a_recurring_amount_grows_beyond_inflation_from_its_start(baseline: Baseline):
    """3% a year beyond inflation: 0.25% a month, compounded, from April:
    2,000.00, 2,005.00, 2,010.01 (2,010.0125), ... and a year on 2,060.83."""
    grown = _regular(baseline, {**RENT, "real_growth": "0.03"})
    assert grown[:3] == [
        ("2030-04-01", D("-2000.00")),
        ("2030-05-01", D("-2005.00")),
        ("2030-06-01", D("-2010.01")),
    ]
    assert grown[12] == ("2031-04-01", D("-2060.83"))


def test_a_growth_of_zero_is_exactly_as_without_one(baseline: Baseline):
    assert _regular(baseline, {**RENT, "real_growth": "0"}) == _regular(baseline, RENT)
    with_zero = engine.run(baseline, doc({**RENT, "real_growth": "0"}))
    without = engine.run(baseline, doc(RENT))
    assert with_zero.monthly == without.monthly
    assert with_zero.fi == without.fi


def test_growth_and_inflation_compound_together():
    """Inflation of 2.4% (0.2% a month) and growth of 1.2% (0.1% a month):
    the first rent in May is the amount at May's price level, and June's
    that, 0.2% and 0.1% more."""
    baseline = books(inflation="0.024").baseline(AS_OF)
    months = timelines.periods(AS_OF, 4)
    level = dict(zip([p.month for p in months], timelines.deflators(baseline, months), strict=True))
    flows = _regular(baseline, {**RENT, "start": "2030-05-01", "real_growth": "0.012"})
    cent = D("0.01")
    assert flows[0] == ("2030-05-01", (D("-2000.00") * level["2030-05"]).quantize(cent))
    assert level["2030-06"] == level["2030-05"] * D("1.002")
    assert flows[1] == (
        "2030-06-01",
        (D("-2000.00") * level["2030-06"] * D("1.001")).quantize(cent),
    )
