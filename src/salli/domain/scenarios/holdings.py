"""
Invest and sell changes on the person's own holdings (the phase 3 design,
section 2; docs/scenarios.md, "Holdings"). Pure, deterministic, Decimal; no
model, and nothing written anywhere.

**One real return** (decision 18). Holdings supply prices, units, lots, fees
and realised gains; never an expected return. The investments stay one pool
growing at the person's real return, so sensitivity and the break-evens
still vary one figure, and Salli never sets one security against another.

**The price** of a trade is the holding's last price recorded on or before
the as-of date (`BaselineHolding.price`, a close or one of its own trades),
in its own currency. A trade in a later month is at that price grown at the
person's real return and inflation through the months before the trade's
month (decision 19), the growth the investments have in the monthly
timeline, so a trade in the as-of month is at the recorded price. Every
trade converts at the as-of exchange rate. Salli forecasts no security's
price and no exchange rate, and the result says so.

**An invest into a holding** (`invest` with `holding`): the amount leaves
cash; the amount less fees joins the investments, and buys
(amount − fees) / rate / price units, to 18 places. It opens a hypothetical
lot (`scenario-invest-<n>`) at that cost, which a later sale in the same
scenario can sell.

**A sale** (`sell`): its units (given, or the value to sell over the price,
to 18 places) are replayed with the holding's recorded transactions and the
scenario's earlier trades on it (`portfolio.lots.replay`, unchanged, in
memory): first in, first out, or the lots named (decision 20). The replay
says the proceeds (units × price), the lots consumed and their cost, and the
realised gain (proceeds − fees − cost), in the holding's currency and the
base one (each lot at the rate it was bought at; the sale at the as-of
rate). The proceeds in the base currency leave the investments; the
proceeds less fees arrive in cash. A sale needs its holding linked to the
investment account that holds it, and can't take out more than that
account's ledger value (decision 17), counted at the as-of price, after the
scenario's earlier trades on that account's holdings. With a `tax_role`,
the gain (a loss, negative) adds to that income role, and the scenario's
tax follows (`tax.py`).

**Fees** are the person's own figure, in the base currency; none when left
out, and the result says "no fees given".
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal

from salli.domain.baseline import timelines
from salli.domain.baseline.models import Baseline, BaselineHolding
from salli.domain.currency import quantum
from salli.domain.portfolio.lots import (
    EXACT,
    PLACES,
    Kind,
    LotPick,
    Sale,
    Transaction,
    TransactionError,
    plain,
    replay,
)
from salli.domain.taxrules.common import Problem, join_path

#: A price older than this, before the as-of date, is stale (as the ledger is).
STALE_PRICE_DAYS = 45

_STEP = Decimal(1).scaleb(-PLACES)
_TWELVE = Decimal(12)


def invest_lot(index: int) -> str:
    """The id of the lot an `invest` change (by its index) opens."""
    return f"scenario-invest-{index + 1}"


def _sale_id(index: int) -> str:
    return f"scenario-sell-{index + 1}"


# ── The price at a trade ─────────────────────────────────────────────────────


def growth(baseline: Baseline, day: dt.date, real_return: Decimal) -> Decimal:
    """What one unit of money invested in the pool on the as-of date has
    become by the start of `day`'s month, in that month's own money: the
    real return compounded a twelfth a month (the as-of month by its share
    of days) and the person's inflation, through the months before `day`'s
    month. 1 in the as-of month."""
    months = (day.year - baseline.as_of.year) * 12 + day.month - baseline.as_of.month
    if months <= 0:
        return Decimal(1)
    periods = timelines.periods(baseline.as_of, months)
    level = timelines.deflators(baseline, periods)[-1]
    real = Decimal(1)
    for p in periods:
        real *= Decimal(1) + real_return / _TWELVE * p.share
    return real * level


def depends_on_return(baseline: Baseline, changes: Sequence[object]) -> bool:
    """Whether a scenario's holding trades are priced with the real return:
    one dated after the as-of month."""
    month = baseline.as_of.isoformat()[:7]
    for change in changes:
        day = getattr(change, "date", None)
        if (
            getattr(change, "type", None) in ("invest", "sell")
            and getattr(change, "holding", None) is not None
            and isinstance(day, dt.date)
            and day.isoformat()[:7] > month
        ):
            return True
    return False


# ── Results ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LotSold:
    """The part of one lot a sale consumes."""

    lot_id: str
    opened_on: str
    quantity: Decimal
    cost: Decimal
    cost_base: Decimal


@dataclass(frozen=True)
class Trade:
    """An invest into a holding, or a sale of one, as Salli read it."""

    kind: Literal["invest", "sell"]
    holding_id: str
    #: The person's own symbol and name for it.
    symbol: str
    name: str
    #: The holding's currency, and the as-of rate into the base one.
    currency: str
    fx_rate: Decimal
    units: Decimal
    #: Per unit, in the holding's currency: the recorded price, or it grown
    #: to the trade's month (`grown`).
    price: Decimal
    #: The recorded price it rests on: its day, who recorded it, and itself.
    price_date: str
    price_source: str
    recorded_price: Decimal
    grown: bool
    stale: bool
    #: The fees, in the base currency (None when none were given), and in
    #: the holding's currency.
    fees: Decimal | None
    fees_native: Decimal
    #: An invest: what the units cost, in the holding's currency and the base
    #: one (the amount less fees). A sale: the proceeds (units × price).
    gross: Decimal
    gross_base: Decimal
    #: A sale's figures from the replay; None for an invest.
    cost: Decimal | None = None
    cost_base: Decimal | None = None
    gain: Decimal | None = None
    gain_base: Decimal | None = None
    lots: tuple[LotSold, ...] = ()
    #: The lot an invest opens.
    lot_id: str | None = None
    #: The investment account a sale comes out of.
    account_id: str | None = None

    @property
    def fees_given(self) -> bool:
        return self.fees is not None


# ── Working a scenario's trades out ──────────────────────────────────────────


@dataclass
class _Pending:
    index: int
    kind: Literal["invest", "sell"]
    holding: BaselineHolding
    day: dt.date
    transaction: Transaction
    trade: Trade
    #: The path of what decides the units (a sale's quantity, amount or lots).
    path: str


@dataclass
class Trades:
    """A scenario's holding changes, priced and replayed (`work_out`)."""

    trades: dict[int, Trade] = field(default_factory=dict[int, Trade])
    problems: list[Problem] = field(default_factory=list[Problem])
    notes: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class Asked:
    """A holding change as the engine hands it over: its index, kind, day,
    holding, the base-currency amount (an invest's, or a sale's value), the
    units (a sale's), the fees, the lots named, and which field says how
    much a sale sells ("quantity", "amount" or "lots")."""

    index: int
    kind: Literal["invest", "sell"]
    day: dt.date
    holding: str
    amount: Decimal | None
    units: Decimal | None
    fees: Decimal | None
    lots: tuple[tuple[str, Decimal], ...] = ()
    how_much: str = "amount"


def _units(value: Decimal) -> Decimal:
    with localcontext(EXACT):
        return value.quantize(_STEP, rounding=ROUND_DOWN)


def _price(value: Decimal) -> Decimal:
    with localcontext(EXACT):
        return value.quantize(_STEP, rounding=ROUND_HALF_EVEN)


def _stale(baseline: Baseline, h: BaselineHolding) -> bool:
    if h.price_date is None:
        return False
    return (baseline.as_of - dt.date.fromisoformat(h.price_date)).days > STALE_PRICE_DAYS


def _usable(
    baseline: Baseline, asked: Asked, at: str, out: Trades
) -> tuple[BaselineHolding, Decimal, Decimal] | None:
    """The holding, its rate and price, or a problem saying why not."""
    h = next((x for x in baseline.holdings if x.holding_id == asked.holding), None)
    if h is None:
        out.problems.append(
            Problem(join_path(at, "holding"), f"{asked.holding!r} is not one of your holdings")
        )
        return None
    if not h.tracked:
        out.problems.append(
            Problem(
                join_path(at, "holding"),
                f"{h.name} has no transactions recorded, so Salli can't tell what it holds or "
                "which lots a trade would touch: record what you bought "
                "(`salli portfolio transactions add`)",
            )
        )
        return None
    if h.price is None:
        out.problems.append(
            Problem(
                join_path(at, "holding"),
                f"{h.name} has no price recorded on or before "
                f"{baseline.as_of.isoformat()}: record one (`salli portfolio prices set`)",
            )
        )
        return None
    if h.fx_rate is None or h.fx_rate <= 0:
        out.problems.append(
            Problem(
                join_path(at, "holding"),
                f"{h.name} is in {h.currency}, and no source has a {h.currency} rate for "
                f"{baseline.as_of.isoformat()}: Salli never guesses one",
            )
        )
        return None
    return h, h.fx_rate, h.price


def work_out(baseline: Baseline, asked: Sequence[Asked], real_return: Decimal) -> Trades:
    """Every holding change of a scenario, priced, replayed and checked
    against the ledger (see the module). Problems carry each change's path."""
    out = Trades()
    pending: list[_Pending] = []
    for a in asked:
        at = join_path("changes", a.index)
        usable = _usable(baseline, a, at, out)
        if usable is None:
            continue
        h, rate, recorded = usable
        factor = growth(baseline, a.day, real_return)
        price = _price(recorded * factor)
        fees_native = (a.fees or Decimal(0)) / rate
        seq = len(h.transactions) + a.index
        common = {
            "holding_id": h.holding_id,
            "symbol": h.symbol,
            "name": h.name,
            "currency": h.currency,
            "fx_rate": rate,
            "price": price,
            "price_date": h.price_date or "",
            "price_source": h.price_source or "",
            "recorded_price": recorded,
            "grown": factor != 1,
            "stale": _stale(baseline, h),
            "fees": a.fees,
        }
        if a.kind == "invest":
            assert a.amount is not None
            with localcontext(EXACT):
                spent = (a.amount - (a.fees or Decimal(0))) / rate
                units = _units(spent / price)
            if units <= 0:
                out.problems.append(
                    Problem(
                        join_path(at, "amount"),
                        f"is too little to buy any of {h.name} at {plain(price)} {h.currency}",
                    )
                )
                continue
            with localcontext(EXACT):
                gross = units * price
            lot = invest_lot(a.index)
            tx = Transaction(
                id=lot,
                kind=Kind.BUY,
                on=a.day,
                quantity=units,
                price=price,
                fees=fees_native,
                fx_rate=rate,
                seq=seq,
            )
            trade = Trade(
                kind="invest",
                units=units,
                fees_native=fees_native,
                gross=gross,
                gross_base=gross * rate,
                lot_id=lot,
                **common,  # type: ignore[arg-type]
            )
            out.trades[a.index] = trade
            pending.append(
                _Pending(a.index, "invest", h, a.day, tx, trade, join_path(at, "amount"))
            )
            continue
        # A sale.
        path = join_path(at, a.how_much)
        if a.units is not None:
            units = a.units
        else:
            assert a.amount is not None
            with localcontext(EXACT):
                units = _units(a.amount / rate / price)
            if units <= 0:
                out.problems.append(Problem(path, f"is too little to sell any of {h.name}"))
                continue
        with localcontext(EXACT):
            gross = units * price
        tx = Transaction(
            id=_sale_id(a.index),
            kind=Kind.SELL,
            on=a.day,
            quantity=units,
            price=price,
            fees=fees_native,
            lots=tuple(LotPick(lot, q) for lot, q in a.lots),
            fx_rate=rate,
            seq=seq,
        )
        trade = Trade(
            kind="sell",
            units=units,
            fees_native=fees_native,
            gross=gross,
            gross_base=gross * rate,
            account_id=h.account_id,
            **common,  # type: ignore[arg-type]
        )
        pending.append(_Pending(a.index, "sell", h, a.day, tx, trade, path))

    _replay(pending, out)
    _within_the_ledger(baseline, pending, out)
    return out


def _order(p: _Pending) -> tuple[dt.date, int, int]:
    return (p.day, 1 if p.kind == "invest" else 2, p.index)


def _replay(pending: Sequence[_Pending], out: Trades) -> None:
    """Each sale replayed with its holding's recorded transactions and the
    scenario's trades on it up to the sale: the replay's own refusals (more
    units than held, a lot not held) come back at the sale's path."""
    by_holding: dict[str, list[_Pending]] = {}
    for p in pending:
        by_holding.setdefault(p.holding.holding_id, []).append(p)
    for mine in by_holding.values():
        mine.sort(key=_order)
        buys = [p.transaction for p in mine if p.kind == "invest"]
        sales: list[Transaction] = []
        for p in mine:
            if p.kind != "sell":
                continue
            history = [*p.holding.transactions, *buys, *sales, p.transaction]
            try:
                book = replay(history, p.day)
            except TransactionError as error:
                out.problems.append(Problem(p.path, str(error)))
                continue
            sale = next(s for s in book.sales if s.transaction_id == p.transaction.id)
            out.trades[p.index] = _sold(p.trade, sale)
            sales.append(p.transaction)


def _sold(trade: Trade, sale: Sale) -> Trade:
    return replace(
        trade,
        cost=sale.cost,
        cost_base=sale.cost_base,
        gain=sale.gain,
        gain_base=sale.gain_base,
        gross=sale.proceeds,
        gross_base=sale.proceeds_base,
        lots=tuple(
            LotSold(c.lot_id, c.opened_on.isoformat(), c.quantity, c.cost, c.cost_base)
            for c in sale.consumed
        ),
    )


def _within_the_ledger(baseline: Baseline, pending: Sequence[_Pending], out: Trades) -> None:
    """A sale needs its holding linked to an investment account, and the
    sales from an account can't take out more than its ledger value (with
    what the scenario invests into its holdings first), counted at the
    as-of price so a later sale's growth doesn't count against it."""
    balances = {b.account_id: b for b in baseline.balances}
    room: dict[str, Decimal] = {}
    invested: dict[str, Decimal] = {}
    sold: dict[str, Decimal] = {}
    for p in sorted(pending, key=_order):
        h = p.holding
        at = join_path("changes", p.index)
        assert h.price is not None and h.fx_rate is not None
        as_of_value = p.transaction.quantity * h.price * h.fx_rate
        if p.kind == "invest":
            if h.account_id is not None:
                invested[h.account_id] = invested.get(h.account_id, Decimal(0)) + as_of_value
            continue
        replayed = p.index in out.trades
        if h.account_id is None:
            out.problems.append(
                Problem(
                    join_path(at, "holding"),
                    f"{h.name} isn't linked to the investment account that holds it, so a sale "
                    "can't come out of anything your baseline counts: link it "
                    f"(`salli holdings update {h.holding_id[:8]} --account <account>`)",
                )
            )
            out.trades.pop(p.index, None)
            continue
        account = balances.get(h.account_id)
        if account is None or account.role != "investment" or account.value is None:
            why = (
                "isn't one your baseline holds"
                if account is None
                else "isn't an investment account"
                if account.role != "investment"
                else "can't be valued in your base currency on this date"
            )
            name = account.name if account is not None else "The account it is linked to"
            out.problems.append(
                Problem(
                    join_path(at, "holding"),
                    f"{name}, which holds {h.name}, {why}, so a sale can't come out of it",
                )
            )
            out.trades.pop(p.index, None)
            continue
        if not replayed:
            continue  # the replay refused it already
        if h.account_id not in room:
            room[h.account_id] = account.value
        sold[h.account_id] = sold.get(h.account_id, Decimal(0)) + as_of_value
        holds = room[h.account_id] + invested.get(h.account_id, Decimal(0))
        if sold[h.account_id] > holds:
            cur = baseline.currency
            more = invested.get(h.account_id, Decimal(0))
            what = (
                "this sale is"
                if sold[h.account_id] == as_of_value
                else (f"this sale, with the scenario's earlier sales from {account.name}, is")
            )
            put = f", and the scenario invests {_money(more, cur)} into it first," if more else ""
            out.problems.append(
                Problem(
                    p.path,
                    f"your ledger holds {_money(account.value, cur)} in {account.name}{put} "
                    f"and {what} worth {_money(sold[h.account_id], cur)}: bring the ledger up "
                    "to date, or sell less",
                )
            )
            out.trades.pop(p.index, None)


def _money(value: Decimal, currency: str) -> str:
    q = quantum(currency, strict=False)
    return f"{value.quantize(q, rounding=ROUND_HALF_EVEN):,}"


__all__ = [
    "STALE_PRICE_DAYS",
    "Asked",
    "LotSold",
    "Trade",
    "Trades",
    "depends_on_return",
    "growth",
    "invest_lot",
    "work_out",
]
