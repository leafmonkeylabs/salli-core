"""
Property tests for lot accounting (domain/portfolio/lots.py), over random but
possible histories: buys and transfers in, sales first in first out or of named
lots, dividends, and splits, with fees and a different exchange rate each day.

The identities are exact — not approximately equal — in the holding's currency
and in the base currency alike.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal, localcontext
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from salli.domain.portfolio.lots import (
    EXACT,
    Kind,
    LotPick,
    Transaction,
    replay,
    total,
)


def _decimals(low: str, high: str, places: int) -> st.SearchStrategy[Decimal]:
    return st.decimals(
        min_value=Decimal(low),
        max_value=Decimal(high),
        places=places,
        allow_nan=False,
        allow_infinity=False,
    )


quantities = _decimals("0.000001", "1000", 6)
prices = _decimals("0", "10000", 4)
fees = _decimals("0", "50", 2)
amounts = _decimals("0.01", "100000", 2)
rates = _decimals("0.001", "1000", 6)
shares = _decimals("0.01", "1", 2)
SPLITS = [(2, 1), (3, 2), (1, 2), (1, 10), (1, 3), (10, 1)]


def _part(draw: Any, whole: Decimal) -> Decimal:
    """Some of `whole`: all of it, or a share rounded down to 6 places."""
    if draw(st.booleans()):
        return whole
    part = (whole * draw(shares)).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    return part if part > 0 else whole


@st.composite
def histories(draw: Any, *, with_splits: bool = True) -> list[Transaction]:
    """A history that could have happened: every sale is of units held then."""
    history: list[Transaction] = []
    day = date(2020, 1, 1)
    for seq in range(draw(st.integers(min_value=1, max_value=12))):
        day += timedelta(days=draw(st.integers(min_value=1, max_value=60)))
        book = replay(history)
        held = book.position.quantity
        kinds = ["buy", "transfer_in", "dividend"] + (["split"] if with_splits else [])
        kind = draw(st.sampled_from(kinds + (["sell", "sell"] if held > 0 else [])))
        common: dict[str, Any] = {"id": f"t{seq}", "on": day, "seq": seq}
        if kind == "buy":
            tx = Transaction(
                kind=Kind.BUY,
                quantity=draw(quantities),
                price=draw(prices),
                fees=draw(fees),
                fx_rate=draw(rates),
                **common,
            )
        elif kind == "transfer_in":
            tx = Transaction(
                kind=Kind.TRANSFER_IN,
                quantity=draw(quantities),
                amount=draw(amounts),
                fx_rate=draw(rates),
                **common,
            )
        elif kind == "dividend":
            amount = draw(amounts)
            withheld = (amount * draw(shares)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            tx = Transaction(
                kind=Kind.DIVIDEND,
                amount=amount,
                withholding_tax=withheld,
                fx_rate=draw(rates),
                **common,
            )
        elif kind == "split":
            to, from_ = draw(st.sampled_from(SPLITS))
            tx = Transaction(
                kind=Kind.SPLIT, split_to=Decimal(to), split_from=Decimal(from_), **common
            )
        else:
            named: tuple[LotPick, ...] = ()
            if draw(st.booleans()):
                quantity = _part(draw, held)
            else:
                lot = draw(st.sampled_from(book.open_lots))
                quantity = _part(draw, lot.quantity)
                named = (LotPick(lot.id, quantity),)
            tx = Transaction(
                kind=Kind.SELL,
                quantity=quantity,
                price=draw(prices),
                fees=draw(fees),
                fx_rate=draw(rates),
                lots=named,
                **common,
            )
        history.append(tx)
    return history


def _opening_cost(tx: Transaction) -> Decimal:
    if tx.kind is Kind.BUY:
        return tx.quantity * tx.price + tx.fees
    if tx.kind is Kind.TRANSFER_IN:
        return tx.amount
    return Decimal(0)


@given(history=histories(), price=prices, rate_now=rates)
@settings(max_examples=300, deadline=None)
def test_realised_plus_unrealised_is_proceeds_plus_value_less_cost(
    history: list[Transaction], price: Decimal, rate_now: Decimal
):
    """What was gained, realised or not, is what came out (net of fees) plus
    what is left, less everything that went in — to the last digit."""
    book = replay(history)
    position = book.position
    with localcontext(EXACT):
        value = position.quantity * price
        realised = total(sale.gain for sale in book.sales)
        unrealised = value - position.cost
        proceeds = total(sale.proceeds - sale.fees for sale in book.sales)
        cost = total(_opening_cost(tx) for tx in history)
        assert realised + unrealised == proceeds + value - cost

        # In the base currency: each cost at the rate of its day, each sale at
        # its own, and what is left at today's.
        value_base = value * rate_now
        realised_base = total(sale.gain_base for sale in book.sales)
        unrealised_base = value_base - position.cost_base
        proceeds_base = total(sale.proceeds_base - sale.fees_base for sale in book.sales)
        cost_base = total(_opening_cost(tx) * tx.fx_rate for tx in history)
        assert realised_base + unrealised_base == proceeds_base + value_base - cost_base


@st.composite
def round_trips(draw: Any) -> list[Transaction]:
    """Buys at one price and one rate, perhaps splits whose adjusted price is
    exact, then sales at that (adjusted) price until nothing is left; no fees."""
    price, rate = draw(prices), draw(rates)
    history: list[Transaction] = []
    day = date(2020, 1, 1)
    seq = 0

    def add(**fields: Any) -> None:
        nonlocal day, seq
        day += timedelta(days=1)
        history.append(Transaction(id=f"t{seq}", on=day, seq=seq, fx_rate=rate, **fields))
        seq += 1

    for _ in range(draw(st.integers(min_value=1, max_value=5))):
        add(kind=Kind.BUY, quantity=draw(quantities), price=price)
    for _ in range(draw(st.integers(min_value=0, max_value=2))):
        to, from_ = draw(st.sampled_from([(2, 1), (1, 2), (10, 1), (1, 10)]))
        add(kind=Kind.SPLIT, split_to=Decimal(to), split_from=Decimal(from_))
        with localcontext(EXACT):
            price = price * from_ / to
    while (book := replay(history)).position.quantity > 0:
        held = book.position.quantity
        if draw(st.booleans()):
            add(kind=Kind.SELL, quantity=_part(draw, held), price=price)
        else:
            lot = draw(st.sampled_from(book.open_lots))
            quantity = _part(draw, lot.quantity)
            add(kind=Kind.SELL, quantity=quantity, price=price, lots=(LotPick(lot.id, quantity),))
    return history


@given(history=round_trips())
@settings(max_examples=300, deadline=None)
def test_buying_then_selling_everything_at_one_price_without_fees_gains_nothing(
    history: list[Transaction],
):
    book = replay(history)
    assert book.position.quantity == 0 and book.position.cost == 0
    assert [sale.gain for sale in book.sales] == [0] * len(book.sales)
    assert [sale.gain_base for sale in book.sales] == [0] * len(book.sales)


@given(history=histories(with_splits=False))
@settings(max_examples=200, deadline=None)
def test_what_is_held_is_what_came_in_less_what_was_sold(history: list[Transaction]):
    book = replay(history)
    came_in = total(tx.quantity for tx in history if tx.kind in (Kind.BUY, Kind.TRANSFER_IN))
    sold = total(tx.quantity for tx in history if tx.kind is Kind.SELL)
    assert book.position.quantity == came_in - sold
    for sale in book.sales:
        assert total(c.quantity for c in sale.consumed) == sale.quantity


@given(history=histories())
@settings(max_examples=200, deadline=None)
def test_first_in_first_out_never_skips_an_older_open_lot(history: list[Transaction]):
    """A FIFO sale takes whole lots oldest first; only the last it touches
    can be left part-held."""
    by_id = {tx.id: tx for tx in history}
    for sale in replay(history).sales:
        if by_id[sale.transaction_id].lots:
            continue
        upto = replay(
            [tx for tx in history if (tx.on, tx.seq) < (sale.on, by_id[sale.transaction_id].seq)]
        )
        open_before = [lot.id for lot in upto.open_lots]
        touched = [c.lot_id for c in sale.consumed]
        assert touched == open_before[: len(touched)]
