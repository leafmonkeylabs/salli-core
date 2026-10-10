"""
Property tests for a period's figures (domain/portfolio/performance.py) and
the return solvers (domain/portfolio/returns.py), over random histories,
prices, periods and rates — some of them missing, so that some valuations are
carried at cost.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from salli.domain.portfolio.lots import EXACT, Kind, Transaction, total
from salli.domain.portfolio.performance import History, report
from salli.domain.portfolio.returns import RATE, Flow, xirr
from salli.domain.portfolio.valuation import Close, Pricing
from tests.properties.test_portfolio_lots import histories, prices, quantities, rates

FIRST = date(2020, 1, 1)


@st.composite
def holdings(draw: Any, key: str) -> History:
    """A history, closes on random days, and rates for some of those days."""
    history = draw(histories())
    last = max(tx.on for tx in history)
    span = (last - FIRST).days + 30
    days = draw(st.lists(st.integers(min_value=0, max_value=span), max_size=6, unique=True))
    closes = [
        Close(FIRST + timedelta(days=d), draw(prices.filter(lambda p: p > 0)), "user") for d in days
    ]
    known = {c.on: draw(rates) for c in closes if draw(st.booleans())}
    return History(key, history, Pricing(history, closes), known)


@st.composite
def periods(draw: Any) -> tuple[date | None, date]:
    end = FIRST + timedelta(days=draw(st.integers(min_value=0, max_value=900)))
    if draw(st.booleans()):
        return None, end
    start = FIRST + timedelta(days=draw(st.integers(min_value=0, max_value=900)))
    return min(start, end), end


@given(held=st.lists(st.sampled_from("ABC"), min_size=1, max_size=3, unique=True), data=st.data())
@settings(max_examples=150, deadline=None)
def test_total_return_is_realised_plus_income_plus_the_change_in_unrealised(
    held: list[str], data: Any
):
    """Whatever the period, and whether each valuation is at a price, at a
    rate, or carried at cost: what the period earned is what was realised,
    plus income, plus what happened to the unrealised gain — exactly."""
    start, end = data.draw(periods())
    result = report([data.draw(holdings(key)) for key in held], start, end)
    with localcontext(EXACT):
        for figures in [f for h in result.holdings for f in (h.native, h.base)]:
            assert figures.total_return == (
                figures.realised
                + figures.net_income
                + figures.closing_unrealised
                - figures.opening_unrealised
            )
        # The portfolio is its holdings added up, in the base currency.
        for name in ("opening_value", "closing_value", "realised", "net_income", "paid_in"):
            assert getattr(result.portfolio, name) == total(
                getattr(h.base, name) for h in result.holdings
            )
        assert result.portfolio.total_return == total(h.base.total_return for h in result.holdings)


@st.composite
def one_price_histories(draw: Any) -> tuple[list[Transaction], Decimal]:
    """Buys and sales at one price, no fees, no income, no splits."""
    price = draw(prices.filter(lambda p: p > 0))
    history: list[Transaction] = []
    held = Decimal(0)
    day = FIRST
    for seq in range(draw(st.integers(min_value=1, max_value=8))):
        day += timedelta(days=draw(st.integers(min_value=1, max_value=60)))
        if held > 0 and draw(st.booleans()):
            quantity = min(held, draw(quantities))
            history.append(Transaction(f"t{seq}", Kind.SELL, day, quantity, price, seq=seq))
            held -= quantity
        else:
            quantity = draw(quantities)
            history.append(Transaction(f"t{seq}", Kind.BUY, day, quantity, price, seq=seq))
            held += quantity
    return history, price


@given(case=one_price_histories())
@settings(max_examples=150, deadline=None)
def test_money_in_and_out_at_an_unmoving_price_returns_nothing(
    case: tuple[list[Transaction], Decimal],
):
    history, _ = case
    holding = History("h", history, Pricing(history, []), {})
    figures = report([holding], None, history[-1].on + timedelta(days=10)).holdings[0].native
    assert figures.total_return == 0 and figures.realised == 0
    assert figures.twr is not None
    with localcontext(RATE):
        assert abs(figures.twr) < Decimal("1e-40")


@given(
    rate=st.decimals(min_value=Decimal("-0.9"), max_value=Decimal(5), places=4),
    payments=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=3650),
            st.decimals(min_value=Decimal(1), max_value=Decimal(100000), places=2),
        ),
        min_size=1,
        max_size=5,
        unique_by=lambda p: p[0],
    ),
    term=st.integers(min_value=1, max_value=3650),
)
@settings(max_examples=200, deadline=None)
def test_xirr_finds_the_rate_the_flows_were_built_at(
    rate: Decimal, payments: list[tuple[int, Decimal]], term: int
):
    """Money paid in on several days and all of it, grown at `rate`, taken
    out at the end: the money-weighted return is `rate`."""
    end = max(day for day, _ in payments) + term
    with localcontext(RATE):
        grown = sum(
            (amount * (1 + rate) ** (Decimal(end - day) / 365) for day, amount in payments),
            Decimal(0),
        )
    flows = [Flow(FIRST + timedelta(days=day), -amount) for day, amount in payments]
    flows.append(Flow(FIRST + timedelta(days=end), grown))
    found = xirr(flows)
    assert found is not None
    # Converged within 10⁻¹⁶ of ln(1 + r): that is r to within (1 + r)·10⁻¹⁶.
    assert abs(found - rate) <= (1 + rate) * Decimal("1e-15")
