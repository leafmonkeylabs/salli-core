"""
Hand-worked invest and sell changes on a person's own holdings (decision lab
3b; docs/scenarios.md, "Holdings").

The household is the XA one (tests/golden/taxed.py: New Zealand dollars, as
of 2031-06-30, a salary of 4,000.00 a month so far, the fictional rules "XA
2031": a relief of 12,000, then 20% to 40,000 and 40% above), with an income
role for gains added to the rules (taxable income: salary plus gains less
pension contributions), and a brokerage account, an investment account,
holding 1,500.00. The person's fund, which they call "My index fund", is
linked to it:

- bought 10 units at 100.00 with 5.00 of fees on 2031-02-03 (a lot costing
  1,005.00);
- a close of 150.00 recorded on the as-of date.

Each test shows its arithmetic. Every figure is the scenario engine's,
through the baseline the API builds.
"""

from __future__ import annotations

import copy
import datetime as dt
from decimal import Decimal as D
from typing import Any

import pytest

from salli.domain.baseline import Baseline
from salli.domain.scenarios import engine, schema, views
from salli.domain.scenarios.engine import ScenarioError
from tests.baseline_ledger import Ledger
from tests.golden import taxed

AS_OF = taxed.AS_OF

#: XA 2031 with an income role for realised gains.
GAINS_RULES: dict[str, Any] = copy.deepcopy(taxed.RULES)
GAINS_RULES["roles"].append({"key": "gains", "kind": "income", "label": "Realised gains"})
GAINS_RULES["lines"][0] = {
    "key": "taxable_income",
    "label": "Salary and gains less pension contributions",
    "expr": "max(0, role.salary + role.gains - role.pension)",
}


def books(*, brokerage: str = "1500", rules: bool = True) -> Ledger:
    ledger = taxed.ledger()
    ledger.uow.tax_rule_sets.active[:] = [taxed.rules_row(GAINS_RULES)] if rules else []
    ledger.account("brk", "asset", asset_role="investment", name="Brokerage")
    ledger.book("2030-12-31", "brk", "eq", brokerage)
    ledger.holding("fund", "My index fund", symbol="FND", account_id="brk")
    ledger.trade("fund", "buy", "2031-02-03", "10", "100", fees="5", id_="lot-feb")
    ledger.close("fund", "2031-06-30", "150")
    return ledger


def scenario(*changes: dict[str, Any]) -> schema.Scenario:
    return schema.load({"schema": "salli.scenario/1", "changes": list(changes)})


def sell(**over: Any) -> dict[str, Any]:
    return {"type": "sell", "holding": "fund", "date": "2031-06-30", **over}


def as_of_month(b: Baseline, s: schema.Scenario) -> tuple[D, D, D]:
    """The change in cash, investments and net worth at the as-of month's
    end: the scenario's month point less the baseline's."""
    _, evaluated = engine.run_with_outlook(b, s)
    base = engine.baseline_outlook(b).monthly.points[1]
    mine = evaluated.outlook.monthly.points[1]
    return (
        mine.cash - base.cash,
        mine.investments - base.investments,
        mine.net_worth - base.net_worth,
    )


def test_a_sale_first_in_first_out_with_fees():
    """Sell 4 units on the as-of date at 150.00 with 2.00 of fees, first in,
    first out: proceeds 4 × 150.00 = 600.00; the lot's cost 1,005.00 × 4/10
    = 402.00; gain 600.00 − 2.00 − 402.00 = 196.00. Cash +598.00,
    investments −600.00, net worth −2.00."""
    b = books(rules=False).baseline(AS_OF)
    s = scenario(sell(quantity="4", fees="2.00"))
    result = engine.run(b, s)
    trade = result.changes[0].holding
    assert trade is not None
    assert (trade.units, trade.price, trade.gross, trade.fees) == (
        D("4"),
        D("150"),
        D("600"),
        D("2.00"),
    )
    assert (trade.cost, trade.gain, trade.gain_base) == (D("402"), D("196"), D("196"))
    assert [(lot.lot_id, lot.quantity, lot.cost) for lot in trade.lots] == [
        ("lot-feb", D("4"), D("402"))
    ]
    assert result.changes[0].label == "Sell My index fund"
    assert as_of_month(b, s) == (D("598.00"), D("-600.00"), D("-2.00"))

    view = views.result_view(result)["changes"][0]["holding"]
    assert {k: view[k] for k in ("units", "price", "fees", "value", "cost", "gain")} == {
        "units": "4",
        "price": "150",
        "fees": "2.00",
        "value": "600.00",
        "cost": "402.00",
        "gain": "196.00",
    }
    assert view["price_basis"] == {
        "date": "2031-06-30",
        "source": "user",
        "price": "150",
        "grown": False,
        "stale": False,
    }


def test_the_gain_is_taxed_through_the_xa_rules():
    """Tagged with the income role `gains`, that role gains 196.00: XA 2031's
    salary of 48,000 (24,000 actual, six months at 4,000) and gains of 196:
    48,196 − 12,000 = 36,196 at 20% = 7,239.20, against 7,200.00 without:
    a change of 39.20, spread from June to December, 5.60 a month."""
    b = books().baseline(AS_OF)
    result = engine.run(b, scenario(sell(quantity="4", fees="2.00", tax_role="gains")))
    assert result.tax.status == "computed"
    (y2031,) = [y for y in result.tax.outcome.years if y.label == "2031"]
    gains = next(r for r in y2031.roles if r.key == "gains")
    assert (gains.actual, gains.projected, gains.scenario) == (D("0.00"), D("0.00"), D("196.00"))
    assert (y2031.net_baseline, y2031.net_scenario, y2031.change) == (
        D("7200.00"),
        D("7239.20"),
        D("39.20"),
    )
    assert [part for _, part in y2031.parts] == [D("5.60")] * 7


def test_a_sale_of_named_lots_with_fees_taxed():
    """A second lot, 5 units at 120.00 bought on 2031-04-01 (600.00, no
    fees); the brokerage holds 2,100.00. Sell 4 units of that lot by name
    at 150.00 with 3.00 of fees: proceeds 600.00, its cost 4 × 120.00 =
    480.00, gain 600.00 − 3.00 − 480.00 = 117.00. Tagged gains: 48,117 −
    12,000 = 36,117 at 20% = 7,223.40, a change of 23.40 from June:
    23.40 / 7 = 3.342857…, 3.34 six times and 3.36 in December."""
    ledger = books(brokerage="2100")
    ledger.trade("fund", "buy", "2031-04-01", "5", "120", id_="lot-apr")
    b = ledger.baseline(AS_OF)
    change = sell(lots=[{"lot": "lot-apr", "quantity": "4"}], fees="3.00", tax_role="gains")
    result = engine.run(b, scenario(change))
    trade = result.changes[0].holding
    assert trade is not None
    assert (trade.units, trade.gross, trade.cost, trade.gain) == (
        D("4"),
        D("600"),
        D("480"),
        D("117"),
    )
    assert [(lot.lot_id, lot.quantity) for lot in trade.lots] == [("lot-apr", D("4"))]
    (y2031,) = [y for y in result.tax.outcome.years if y.label == "2031"]
    assert (y2031.net_scenario, y2031.change) == (D("7223.40"), D("23.40"))
    assert [part for _, part in y2031.parts] == [D("3.34")] * 6 + [D("3.36")]


def test_first_in_first_out_across_several_lots():
    """Lots of 10 at 100.00 (+5.00 fees: 1,005.00) and 5 at 120.00
    (600.00); the brokerage holds 2,250.00 = 15 × 150.00. Selling 12 units
    takes the first lot whole and 2 units of the second: cost 1,005.00 +
    2 × 120.00 = 1,245.00; proceeds 12 × 150.00 = 1,800.00; no fees given;
    gain 555.00."""
    ledger = books(brokerage="2250", rules=False)
    ledger.trade("fund", "buy", "2031-04-01", "5", "120", id_="lot-apr")
    b = ledger.baseline(AS_OF)
    result = engine.run(b, scenario(sell(quantity="12")))
    trade = result.changes[0].holding
    assert trade is not None
    assert [(lot.lot_id, lot.quantity, lot.cost) for lot in trade.lots] == [
        ("lot-feb", D("10"), D("1005")),
        ("lot-apr", D("2"), D("240")),
    ]
    assert (trade.gross, trade.cost, trade.gain, trade.fees) == (
        D("1800"),
        D("1245"),
        D("555"),
        None,
    )
    assert "Sell My index fund: no fees given, so none are counted" in result.notes
    assert views.result_view(result)["changes"][0]["holding"]["fees_given"] is False


def test_an_invest_into_a_holding_buys_units_at_its_price():
    """Invest 1,000.00 into it with 4.00 of fees: (1,000.00 − 4.00) / 150.00
    = 6.64 units. Cash −1,000.00, investments +996.00, net worth −4.00. It
    opens the lot scenario-invest-1."""
    b = books(rules=False).baseline(AS_OF)
    s = scenario(
        {
            "type": "invest",
            "amount": "1000.00",
            "date": "2031-06-30",
            "holding": "fund",
            "fees": "4.00",
            "label": "Top up",
        }
    )
    result = engine.run(b, s)
    trade = result.changes[0].holding
    assert trade is not None
    assert (trade.kind, trade.units, trade.price, trade.lot_id) == (
        "invest",
        D("6.64"),
        D("150"),
        "scenario-invest-1",
    )
    assert as_of_month(b, s) == (D("-1000.00"), D("996.00"), D("-4.00"))


def test_a_sale_can_sell_what_an_earlier_invest_bought():
    """Invest 1,500.00 (no fees: 10 units at 150.00, a lot costing
    1,500.00), then sell 15 units: the 10 recorded first (1,005.00), then 5
    of the new lot (750.00); proceeds 2,250.00, gain 495.00. The brokerage's
    1,500.00 and the 1,500.00 invested into its holding cover the 2,250.00
    sold."""
    b = books(rules=False).baseline(AS_OF)
    invest = {
        "type": "invest",
        "amount": "1500.00",
        "date": "2031-06-30",
        "holding": "fund",
        "label": "Top up",
    }
    result = engine.run(b, scenario(invest, sell(quantity="15")))
    trade = result.changes[1].holding
    assert trade is not None
    assert [(lot.lot_id, lot.quantity, lot.cost) for lot in trade.lots] == [
        ("lot-feb", D("10"), D("1005")),
        ("scenario-invest-1", D("5"), D("750")),
    ]
    assert (trade.gross, trade.gain) == (D("2250"), D("495"))


def test_a_later_sale_is_at_the_price_grown_at_the_real_return_and_inflation():
    """With the person's real return of 6% and inflation of 2.4%, as of
    2031-06-30, a sale on 2031-08-15 is at 150.00 grown through June (its
    one day: a share of 1/30) and July: real (1 + 0.005/30)(1.005), price
    level (1 + 0.002/30)(1.002): 150 × 1.0051675 × 1.0020668 = 151.0867…,
    and 4 units fetch 604.35. The test works the price out the same way, to
    show it is that and nothing else: no price or rate is forecast."""
    ledger = books(rules=False)
    ledger.assume(real_return="0.06", inflation="0.024")
    b = ledger.baseline(AS_OF)
    result = engine.run(b, scenario(sell(quantity="4", date="2031-08-15")))
    trade = result.changes[0].holding
    assert trade is not None
    share = D(1) / D(30)
    grown = (1 + D("0.005") * share) * D("1.005") * (1 + D("0.002") * share) * D("1.002")
    assert trade.price == (D(150) * grown).quantize(D(1).scaleb(-18))
    assert trade.grown and trade.recorded_price == D("150")
    assert views.result_view(result)["changes"][0]["holding"]["value"] == "604.35"
    assert any("Salli forecasts no security's price" in n for n in result.notes)


def test_a_sale_of_more_units_than_held_is_refused_at_its_quantity():
    with pytest.raises(ScenarioError) as refused:
        engine.run(books(rules=False).baseline(AS_OF), scenario(sell(quantity="11")))
    (problem,) = refused.value.problems
    assert problem.path == "changes[0].quantity"
    assert "only 10 are held then" in problem.message


def test_a_sale_worth_more_than_the_account_holds_is_refused():
    """The brokerage's ledger says 1,200.00; 9 units at 150.00 are worth
    1,350.00."""
    b = books(brokerage="1200", rules=False).baseline(AS_OF)
    with pytest.raises(ScenarioError) as refused:
        engine.run(b, scenario(sell(quantity="9")))
    (problem,) = refused.value.problems
    assert problem.path == "changes[0].quantity"
    assert problem.message == (
        "your ledger holds 1,200.00 in Brokerage and this sale is worth 1,350.00: bring the "
        "ledger up to date, or sell less"
    )


def test_a_sale_of_an_unlinked_holding_is_refused():
    ledger = books(rules=False)
    ledger.uow.holdings.rows["fund"]["account_id"] = None
    with pytest.raises(ScenarioError) as refused:
        engine.run(ledger.baseline(AS_OF), scenario(sell(quantity="1")))
    (problem,) = refused.value.problems
    assert problem.path == "changes[0].holding"
    assert "isn't linked to the investment account that holds it" in problem.message


def test_every_existing_figure_is_unchanged_and_the_engine_stays_at_4():
    """An invest without a holding or fees hashes and runs as before."""
    assert engine.ENGINE_VERSION == "4"
    b = books(rules=False).baseline(AS_OF)
    plain = {"type": "invest", "amount": "500.00", "date": "2031-07-01", "label": "Invest"}
    data = schema.hashable(scenario(plain))
    assert data["changes"][0] == {
        "type": "invest",
        "amount": D("500.00"),
        "date": dt.date(2031, 7, 1),
        "from": None,
        "label": "Invest",
    }
    assert engine.run(b, scenario(plain)).changes[0].holding is None
