"""
Rent or buy, worked by hand (docs/design/decision-lab-phase-3.md, section 3,
"Tests"), on the renting household (tests/golden/renting.py): as of
2031-06-30, no inflation, none of the surplus invested, rent of 1,000.00 a
month in the ledger.

Buy on 2031-07-01 for 200,000.00 with 50,000.00 down: a mortgage of
150,000.00 at 0% over 120 months (1,250.00 a month from August), no buying
or owning costs, no growth, selling costs of 3% (the home counted at
194,000.00). Keep renting: the ledger's rent stopped and put back as a
recurring cost, so both options state rent the same way.

- End of July: cash −50,000.00 + 1,000.00 (July's rent not paid), owed
  150,000.00, the home 194,000.00: net worth −5,000.00 against renting.
- Each month after: −250.00 of cash (1,250.00 paid, 1,000.00 of rent not
  paid) and 1,250.00 less owed: +1,000.00 a month.
- So buying first draws level with renting, and stays at least level, at
  the end of 2031-12 (0.00).
- With selling costs of 0: ahead from the end of July (+1,000.00).

Every figure is the scenario engine's, through the baseline the API builds.
"""

from __future__ import annotations

from decimal import Decimal as D
from typing import Any

import pytest

from salli.domain.baseline import Baseline, timelines
from salli.domain.scenarios import comparison, engine, schema, views
from tests.golden import renting


@pytest.fixture(scope="module")
def baseline() -> Baseline:
    return renting.ledger().baseline(renting.AS_OF)


STOP = {"type": "stop_recurring", "key": renting.RENT_KEY, "from": "2031-07-01"}


def keep_renting(years: int = 20) -> schema.Scenario:
    rent = {
        "type": "recurring",
        "amount": "-1000.00",
        "cadence": "monthly",
        "start": "2031-07-01",
        "label": "Rent",
    }
    return schema.load(
        {
            "schema": "salli.scenario/1",
            "label": "Keep renting",
            "horizon_years": years,
            "changes": [STOP, rent],
        }
    )


def buy(years: int = 20, **home: Any) -> schema.Scenario:
    asset = {
        "type": "asset",
        "price": "200000.00",
        "date": "2031-07-01",
        "selling_costs": "0.03",
        "label": "The home",
        **home,
    }
    mortgage = {
        "type": "loan",
        "principal": "150000.00",
        "annual_rate": "0",
        "term_months": 120,
        "start": "2031-07-01",
        "label": "Mortgage",
    }
    return schema.load(
        {
            "schema": "salli.scenario/1",
            "label": "Buy",
            "horizon_years": years,
            "changes": [asset, mortgage, STOP],
        }
    )


def timeline(baseline: Baseline, scenario: schema.Scenario) -> list[timelines.MonthPoint]:
    _, done = engine.run_with_outlook(baseline, scenario)
    return list(done.outlook.monthly.points)


def lead(baseline: Baseline, mine: schema.Scenario, other: schema.Scenario) -> dict[str, D]:
    """Buying's net worth less renting's at each month-end, to the cent."""
    a, b = timeline(baseline, mine), timeline(baseline, other)
    return {
        x.month: (x.net_worth - y.net_worth).quantize(D("0.01"))
        for x, y in zip(a[1:], b[1:], strict=True)
    }


def test_keep_renting_is_the_baseline_restated(baseline: Baseline):
    """The rent stopped and put back on the same days: every figure is the
    baseline's."""
    result = engine.run(baseline, keep_renting())
    assert all(c.net_worth.delta == 0 and c.cash.delta == 0 for c in result.monthly)
    assert result.fi.fi_number.delta == 0


def test_buying_starts_5000_behind_and_gains_1000_a_month(baseline: Baseline):
    ahead = lead(baseline, buy(), keep_renting())
    assert ahead["2031-06"] == 0
    assert [ahead[f"2031-{m:02d}"] for m in range(7, 13)] == [
        D("-5000.00"),
        D("-4000.00"),
        D("-3000.00"),
        D("-2000.00"),
        D("-1000.00"),
        D("0.00"),
    ]
    assert ahead["2032-01"] == D("1000.00")
    # The mortgage's last payment is in 2041-07; after it, 1,000.00 of rent
    # not paid a month, still +1,000.00 a month.
    assert ahead["2041-07"] - ahead["2041-06"] == D("1000.00")
    assert ahead["2041-08"] - ahead["2041-07"] == D("1000.00")


def test_the_end_of_july_in_parts(baseline: Baseline):
    july_buy = {p.month: p for p in timeline(baseline, buy())}["2031-07"]
    july_rent = {p.month: p for p in timeline(baseline, keep_renting())}["2031-07"]
    assert july_buy.cash - july_rent.cash == D("-49000.00")
    assert july_buy.debts == D("150000.00")
    assert (july_buy.other_assets, july_buy.other_assets_value) == (D("194000.00"), D("200000"))


def test_buying_draws_level_at_the_end_of_2031_12(baseline: Baseline):
    level = comparison.level_from(
        timeline(baseline, buy()),
        timeline(baseline, keep_renting()),
        "2031-07",
        "2051-06",
        "NZD",
    )
    assert level is not None and level.month == "2031-12"


def test_without_selling_costs_buying_is_ahead_from_july(baseline: Baseline):
    ahead = lead(baseline, buy(selling_costs="0"), keep_renting())
    assert ahead["2031-07"] == D("1000.00")
    level = comparison.level_from(
        timeline(baseline, buy(selling_costs="0")),
        timeline(baseline, keep_renting()),
        "2031-07",
        "2051-06",
        "NZD",
    )
    assert level is not None and level.month == "2031-07"


def test_the_house_price_growth_at_which_buying_ends_level(baseline: Baseline):
    """Over one year (to 2032-06), buying ends 6,000.00 ahead at no growth
    (level in December, then six months of +1,000.00). The home grows for
    eleven months (August to June), so it ends level where 194,000 × ((1 +
    g/12)^11 − 1) = −6,000: at −3.42%, 194,000 × (1 − 0.00285)^11 =
    188,004.03 (5,995.97 down: level or ahead); at −3.43%, 187,986.75
    (6,013.25 down: behind)."""
    compared = comparison.compare(baseline, [keep_renting(1), buy(1)])
    growth = next(b for b in compared.break_evens if b.kind == "asset_growth")
    assert (growth.status, growth.value, growth.option, growth.change) == (
        "found",
        D("-0.0342"),
        "Buy",
        0,
    )
    assert views.break_even_view(growth, "NZD")["says"] == (
        "At a growth of -3.42% a year beyond inflation or more in the value of Buy's asset, "
        "Buy ends the horizon with at least Keep renting's net worth; below it, Keep renting "
        "ends with more."
    )
    # And the mortgage rate at which the two cost the same, as for any loan.
    assert any(b.kind == "loan_rate" and b.option == "Buy" for b in compared.break_evens)


def test_over_twenty_years_buying_is_ahead_at_every_growth_in_range(baseline: Baseline):
    """+234,000.00 at no growth by 2051-06; even at −5% a year the home
    loses less than that."""
    compared = comparison.compare(baseline, [keep_renting(), buy()])
    growth = next(b for b in compared.break_evens if b.kind == "asset_growth")
    assert (growth.status, growth.ahead) == ("none_in_range", "Buy")
    assert lead(baseline, buy(), keep_renting())["2051-06"] == D("234000.00")


def test_what_comes_back_shows_the_home_and_its_value(baseline: Baseline):
    result = views.result_view(engine.run(baseline, buy()))
    one = result["monthly"][0]
    assert one["other_assets"] == {
        "baseline": "0.00",
        "scenario": "194000.00",
        "delta": "194000.00",
    }
    assert one["other_assets_value"]["scenario"] == "200000.00"
    # No growth of its own: 0, as a labelled placeholder; a stated 0 isn't one.
    assert "asset_growth" in result["placeholders"]
    stated = views.result_view(engine.run(baseline, buy(real_growth="0")))
    assert "asset_growth" not in stated["placeholders"]
