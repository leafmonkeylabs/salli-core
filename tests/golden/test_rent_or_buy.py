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

The template `rent-or-buy` builds the same two options from its answers,
and its start reads the same month and break-evens.

Every figure is the scenario engine's, through the baseline the API builds.
"""

from __future__ import annotations

from decimal import Decimal as D
from typing import Any

import pytest

from salli.domain.baseline import Baseline, timelines
from salli.domain.decisions import catalogue, start, templates
from salli.domain.scenarios import comparison, engine, schema, views
from tests.golden import renting
from tests.guardrails import assert_never_ranks


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


# ── The template: the same, from its answers ─────────────────────────────────

ANSWERS = {
    "price": "200000.00",
    "date": "2031-07-01",
    "deposit": "50000.00",
    "mortgages": [{"annual_rate": "0", "term_months": 120}],
    "buying_costs": "0",
    "owning_costs": "0",
    "rent": renting.RENT_KEY,
    "selling_costs": "0.03",
}


def started(baseline: Baseline, **answers: Any) -> dict[str, Any]:
    template = catalogue.get("rent-or-buy")
    read, built = templates.build(template, {**ANSWERS, **answers}, templates.facts_of(baseline))
    return start.start(baseline, template, read, built)


def test_the_template_builds_the_hand_worked_options(baseline: Baseline):
    result = started(baseline)
    assert [o["label"] for o in result["options"]] == ["Keep renting", "Buy"]
    rent, buy_ = result["comparison"]["options"]
    # Keeping renting states the ledger's rent again: the baseline exactly.
    assert all(c["net_worth"]["delta"] == "0.00" for c in rent["monthly"])
    # Buying: 1,000.00 a month ahead of renting from December, so 234,000.00
    # ahead by 2051-06; the home at 194,000.00, worth 200,000.00.
    twenty = buy_["monthly"][-1]
    assert (twenty["years"], twenty["net_worth"]["delta"]) == (20, "234000.00")
    assert (twenty["other_assets"]["scenario"], twenty["other_assets_value"]["scenario"]) == (
        "194000.00",
        "200000.00",
    )


def test_the_template_reads_when_buying_draws_level(baseline: Baseline):
    level = started(baseline)["level"]
    assert (level["against"], level["from"], level["to"]) == ("Keep renting", "2031-07", "2051-06")
    assert level["options"] == [
        {
            "option": "Buy",
            "month": "2031-12",
            "months": 5,
            "net_worth_then": "0.00",
            "net_worth_at_horizon": "234000.00",
        }
    ]
    ahead = started(baseline, selling_costs="0")["level"]["options"][0]
    assert (ahead["month"], ahead["months"], ahead["net_worth_then"]) == ("2031-07", 0, "1000.00")


def test_the_template_gives_the_three_break_evens(baseline: Baseline):
    """Over one year: the house-price growth (-3.42%, as above) and the
    mortgage rate at which buying and renting cost the same."""
    result = started(baseline, horizon_years=1)
    kinds = {b["kind"]: b for b in result["comparison"]["break_evens"]}
    assert set(kinds) == {"asset_growth", "loan_rate"}
    assert (kinds["asset_growth"]["value"], kinds["asset_growth"]["option"]) == ("-0.0342", "Buy")
    assert kinds["loan_rate"]["status"] == "found"
    # Over twenty years, buying is ahead at every growth from -5% to 10%.
    growth = next(
        b for b in started(baseline)["comparison"]["break_evens"] if b["kind"] == "asset_growth"
    )
    assert (growth["status"], growth["ahead"]) == ("none_in_range", "Buy")


def test_the_template_says_what_it_rests_on_and_ranks_nothing(baseline: Baseline):
    result = started(baseline)
    assert {"asset_growth", "rent_growth"} <= set(result["placeholders"])
    sources = {a["id"]: a["source"] for a in result["answers"]}
    assert (sources["rent_growth"], sources["home_growth"]) == ("placeholder", "placeholder")
    notes = " ".join(result["notes"])
    for said in (
        "never a forecast",
        "held fixed for its term",
        "illiquid and undiversified",
        "leaving them low flatters buying",
        "comes only from your own rules",
        "knows nothing about any local property market",
    ):
        assert said in notes
    assert_never_ranks(result)
    # With the person's own views, neither growth is a placeholder.
    own = started(baseline, rent_growth="0.005", home_growth="0.01")
    assert not {"asset_growth", "rent_growth"} & set(own["placeholders"])
    assert_never_ranks(own)


def test_a_sale_of_holdings_can_fund_the_deposit_on_a_home():
    """3b's household (tests/golden/test_holding_scenarios.py): all 10
    units of "My index fund" sold on 2031-07-01, at the 150.00 recorded on
    the as-of date grown a month at the 4% real return (1,500.17, no fees),
    put towards a flat for 20,000.00 bought that day with a mortgage of
    15,000.00 at 0% over 120 months, no growth and no selling costs. At the
    end of July: cash 1,500.17 + 15,000.00 − 20,000.00 = −3,499.83 against
    the baseline, investments −1,500.17, the flat 20,000.00 and 15,000.00
    owed: net worth exactly as it was. Each works as it does alone."""
    from tests.golden import test_holding_scenarios as holdings

    b = holdings.books().baseline(holdings.AS_OF)
    both = schema.load(
        {
            "schema": "salli.scenario/1",
            "changes": [
                {"type": "sell", "holding": "fund", "quantity": "10", "date": "2031-07-01"},
                {
                    "type": "asset",
                    "price": "20000.00",
                    "date": "2031-07-01",
                    "real_growth": "0",
                    "label": "A flat",
                },
                {
                    "type": "loan",
                    "principal": "15000.00",
                    "annual_rate": "0",
                    "term_months": 120,
                    "start": "2031-07-01",
                    "label": "Mortgage",
                },
            ],
        }
    )
    result, done = engine.run_with_outlook(b, both)
    base = {p.month: p for p in engine.baseline_outlook(b).monthly.points[1:]}
    july = {p.month: p for p in done.outlook.monthly.points[1:]}["2031-07"]
    cent = D("0.01")
    assert (july.cash - base["2031-07"].cash).quantize(cent) == D("-3499.83")
    assert (july.investments - base["2031-07"].investments).quantize(cent) == D("-1500.17")
    assert (july.other_assets, july.debts) == (D("20000.00"), D("15000.00"))
    assert (july.net_worth - base["2031-07"].net_worth).quantize(cent) == 0
    assert [c.type for c in result.changes] == ["sell", "asset", "loan"]
    assert result.changes[0].holding is not None and result.changes[0].holding.units == 10
    assert "asset_growth" not in result.placeholders
