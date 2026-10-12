"""
Properties of invest and sell changes on a person's holdings (decision lab
3b), over random histories, prices, real returns and inflation:

- a sale and an invest of the same value on the same day, with no fees,
  leave every figure unchanged;
- with fees, a sale moves value from the investments to cash less the fees:
  net worth at the trade's month end falls by exactly the fees;
- a sale's gain is its proceeds less its fees less the cost of the lots it
  consumes, and on the hypothetical replay realised + unrealised =
  proceeds − fees + value − cost (the lot engine's own invariant);
- the stored transactions are byte-for-byte the same after any scenario.
"""

from __future__ import annotations

import copy
import datetime as dt
import pickle
from decimal import Decimal, localcontext

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salli.domain.portfolio.lots import EXACT, replay
from salli.domain.scenarios import engine, schema
from tests.baseline_ledger import Ledger

_SETTINGS = settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
AS_OF = dt.date(2028, 5, 20)
CENT = Decimal("0.01")


@st.composite
def households(draw: st.DrawFn) -> Ledger:
    """In Kenyan shillings: a bank account, a brokerage holding exactly what
    its holding is worth at its price, and a fund with one to four buys."""
    ledger = Ledger("KES")
    ledger.account("bank", "asset")
    ledger.account("brk", "asset", asset_role="investment", name="Brokerage")
    ledger.account("pay", "income")
    ledger.account("eq", "equity")
    ledger.book("2027-12-31", "bank", "eq", "250000")
    for month in range(1, 5):
        ledger.book(f"2028-{month:02d}-25", "bank", "pay", "90000")
    ledger.holding("fund", "My fund", account_id="brk")
    units = Decimal(0)
    for n in range(draw(st.integers(min_value=1, max_value=4))):
        quantity = draw(st.integers(min_value=1, max_value=200))
        price = draw(st.decimals(min_value=Decimal("10"), max_value=Decimal("900"), places=2))
        fees = draw(st.decimals(min_value=Decimal("0"), max_value=Decimal("50"), places=2))
        ledger.trade(
            "fund", "buy", f"2028-0{n + 1}-0{n + 2}", str(quantity), str(price), fees=str(fees)
        )
        units += quantity
    close = draw(st.decimals(min_value=Decimal("10"), max_value=Decimal("900"), places=2))
    ledger.close("fund", AS_OF.isoformat(), str(close))
    ledger.book("2027-12-31", "brk", "eq", str(units * close))
    ledger.assume(
        real_return=str(
            draw(st.decimals(min_value=Decimal("-0.02"), max_value=Decimal("0.08"), places=3))
        ),
        inflation=str(
            draw(st.decimals(min_value=Decimal("0"), max_value=Decimal("0.06"), places=3))
        ),
    )
    return ledger


def _doc(*changes: dict) -> schema.Scenario:
    return schema.load({"schema": "salli.scenario/1", "changes": list(changes)})


days = st.integers(min_value=0, max_value=300)


@_SETTINGS
@given(
    households(), st.decimals(min_value=Decimal("100"), max_value=Decimal("5000"), places=2), days
)
def test_a_sale_and_an_invest_of_the_same_value_change_nothing(ledger, amount, ahead):
    b = ledger.baseline(AS_OF)
    day = (AS_OF + dt.timedelta(days=ahead)).isoformat()
    sale = {"type": "sell", "holding": "fund", "amount": f"{amount}", "date": day}
    invest = {"type": "invest", "amount": f"{amount}", "date": day, "label": "Back in"}
    held = b.holdings[0]
    if amount > held.quantity * (held.price or 0):
        return  # more than it holds: refused, as tested elsewhere
    _, both = engine.run_with_outlook(b, _doc(sale, invest))
    base = engine.baseline_outlook(b)
    for mine, theirs in zip(both.outlook.monthly.points, base.monthly.points, strict=True):
        assert (mine.cash, mine.investments, mine.net_worth) == (
            theirs.cash,
            theirs.investments,
            theirs.net_worth,
        )
    assert both.outlook.cash.forecast.daily == base.cash.forecast.daily


@_SETTINGS
@given(
    households(),
    st.integers(min_value=1, max_value=100),
    st.decimals(min_value=Decimal("0"), max_value=Decimal("80"), places=2),
    days,
)
def test_a_sale_moves_value_to_cash_less_its_fees(ledger, units, fees, ahead):
    b = ledger.baseline(AS_OF)
    if units > b.holdings[0].quantity:
        return
    day = AS_OF + dt.timedelta(days=ahead)
    s = _doc(
        {
            "type": "sell",
            "holding": "fund",
            "quantity": str(units),
            "date": day.isoformat(),
            "fees": f"{fees}",
        }
    )
    result, evaluated = engine.run_with_outlook(b, s)
    base = engine.baseline_outlook(b)
    trade = result.changes[0].holding
    assert trade is not None
    # At the end of the sale's month, in that month's own money: cash up by
    # the proceeds less fees, investments down by the proceeds.
    at = (day.year - AS_OF.year) * 12 + day.month - AS_OF.month + 1
    mine, theirs = evaluated.outlook.monthly.points[at], base.monthly.points[at]
    level = mine.deflator
    proceeds = trade.gross_base.quantize(CENT)

    def nominal(delta: Decimal) -> Decimal:
        # The timeline keeps today's money to 28 digits: back in the month's
        # own money, to the cent.
        return (delta * level).quantize(CENT)

    assert nominal(mine.cash - theirs.cash) == proceeds - fees
    assert nominal(mine.investments - theirs.investments) == -proceeds
    assert nominal(mine.net_worth - theirs.net_worth) == -fees


@_SETTINGS
@given(households(), st.integers(min_value=1, max_value=100), days)
def test_the_gain_is_the_proceeds_less_fees_less_the_lots_cost(ledger, units, ahead):
    b = ledger.baseline(AS_OF)
    held = b.holdings[0]
    if units > held.quantity:
        return
    day = AS_OF + dt.timedelta(days=ahead)
    s = _doc(
        {
            "type": "sell",
            "holding": "fund",
            "quantity": str(units),
            "date": day.isoformat(),
            "fees": "7.50",
        }
    )
    trade = engine.run(b, s).changes[0].holding
    assert trade is not None and trade.gain is not None and trade.cost is not None
    with localcontext(EXACT):
        assert trade.cost == sum((lot.cost for lot in trade.lots), Decimal(0))
        assert trade.gain == trade.gross - trade.fees_native - trade.cost
        assert (
            trade.gain_base
            == trade.gross_base - Decimal("7.50") / trade.fx_rate * trade.fx_rate - trade.cost_base
        )
        # The replay's invariant: realised + unrealised = proceeds − fees +
        # value − cost, with what is left valued at the sale's price.
        before = replay(held.transactions)
        left = held.quantity - units
        unrealised = left * trade.price - (before.position.cost - trade.cost)
        assert trade.gain + unrealised == (
            trade.gross - trade.fees_native + left * trade.price - before.position.cost
        )


@_SETTINGS
@given(households(), st.integers(min_value=1, max_value=50), days)
def test_the_stored_transactions_are_untouched(ledger, units, ahead):
    stored = copy.deepcopy(ledger.uow.holding_transactions.rows)
    before = pickle.dumps(stored)
    b = ledger.baseline(AS_OF)
    day = (AS_OF + dt.timedelta(days=ahead)).isoformat()
    changes = [
        {"type": "invest", "amount": "1000.00", "date": day, "holding": "fund", "label": "In"},
    ]
    if units <= b.holdings[0].quantity:
        changes.append({"type": "sell", "holding": "fund", "quantity": str(units), "date": day})
    engine.run(b, _doc(*changes))
    assert pickle.dumps(ledger.uow.holding_transactions.rows) == before
