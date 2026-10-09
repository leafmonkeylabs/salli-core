"""
Lot accounting: what a holding's transactions say it holds, what each unit cost,
and what each sale gained. Pure — transactions in; lots, sales and income out.

The transactions

  buy          `quantity` units at `price` per unit, plus `fees`. Opens a lot that
               cost quantity × price + fees.
  transfer_in  `quantity` units brought in from elsewhere at a stated total cost
               (`amount`). Opens a lot that cost that much.
  sell         `quantity` units at `price` per unit, less `fees`. Consumes lots:
               the oldest first (FIFO), or the ones `lots` names, in the
               quantities it names.
  dividend,    `amount` received before `withholding_tax`. Income; lots are
  interest     untouched, so it may arrive after everything was sold.
  split        every open lot's quantity × `split_to` / `split_from` (a 2-for-1
               split is 2:1, a 1-for-10 reverse split 1:10). Cost is unchanged.

Money is in the holding's own currency. Every transaction but a split also
carries `fx_rate`, the units of the owner's base currency one unit of the
holding's bought on its date, so each figure has a base-currency twin taken at
the rate of the day it happened: a lot's base cost at the rate it was bought
at, a sale's base proceeds at the rate it was sold at. A gain in the base
currency therefore includes what the exchange rate did, as a tax authority
reckons it.

A realised gain is proceeds − fees − the consumed lots' cost. A partly consumed
lot gives up its cost pro rata, and keeps exactly what it did not give up, so
nothing is lost or made in the division.

Order: by date. On one date, splits come first (a split takes effect from the
start of its day, so units bought that day are already post-split), then
acquisitions, then sales, then income; transactions of one kind on one date go
in the order they were recorded (`seq`).

Arithmetic is exact, with two deliberate roundings. Quantities, prices,
ratios and rates have at most 18 decimal places and 20 integer digits, and
money at most 4 places, so every figure formed from them (a cost is quantity
× price + fees; its base twin that × a rate) has at most 60 places and 140
digits, and everything here runs at 200 significant digits: sums, differences
and those products never round. The two roundings are the divisions:

- a partly consumed lot's share of its cost is rounded to 60 places, and the
  lot keeps exactly the rest, so no money is lost or made in the division
  (`realised + unrealised = proceeds − fees + value − cost` holds exactly);
- a split's quantities are rounded to the 18 places a quantity has.

Figures are rounded to a currency's precision only when they are shown.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from enum import StrEnum

ZERO = Decimal(0)
ONE = Decimal(1)

#: The context every computation in the portfolio domain runs in. See the
#: module docstring for why 200 digits is exact for what it adds and multiplies.
EXACT = Context(
    prec=200,
    rounding=ROUND_HALF_EVEN,
    Emax=999_999,
    Emin=-999_999,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)

#: Decimal places a quantity, unit price, split ratio or exchange rate may have.
#: 18 is the finest any asset divides (ether's wei is 10⁻¹⁸; bitcoin's satoshi
#: 10⁻⁸; fractional shares rarely go past 6).
PLACES = 18
#: Integer digits they may have: anything under 10²⁰.
INTEGER_DIGITS = 20
_STEP = Decimal(1).scaleb(-PLACES)
_LIMIT = Decimal(10) ** INTEGER_DIGITS
#: Money is stored as BIGINT minor units (at most 4 places): under 10¹⁴ fits.
MONEY_LIMIT = Decimal(10) ** 14
#: Places a partly consumed lot's share of its cost is rounded to: more than
#: any product of three 18-place numbers has, so a share that divides exactly
#: (the same price in and out) is never rounded at all.
SHARE_PLACES = 60
_SHARE_STEP = Decimal(1).scaleb(-SHARE_PLACES)


class Kind(StrEnum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    SPLIT = "split"
    TRANSFER_IN = "transfer_in"


#: Transactions that open a lot.
OPENING = frozenset({Kind.BUY, Kind.TRANSFER_IN})
#: Transactions that pay income.
INCOME = frozenset({Kind.DIVIDEND, Kind.INTEREST})
#: Transactions with a market price per unit.
TRADES = frozenset({Kind.BUY, Kind.SELL})

# Where a transaction falls among the others on its date.
_PHASE = {
    Kind.SPLIT: 0,
    Kind.BUY: 1,
    Kind.TRANSFER_IN: 1,
    Kind.SELL: 2,
    Kind.DIVIDEND: 3,
    Kind.INTEREST: 3,
}


class TransactionError(ValueError):
    """A transaction that is not well formed, or a history that cannot have
    happened (selling more than was held, naming a lot that was not)."""


@dataclass(frozen=True)
class LotPick:
    """A sale's claim on one lot: take `quantity` units from lot `lot_id`."""

    lot_id: str
    quantity: Decimal


@dataclass(frozen=True)
class Transaction:
    """One event in a holding's history. Which fields matter depends on `kind`
    (see the module docstring); the others keep their defaults."""

    id: str
    kind: Kind
    on: date
    quantity: Decimal = ZERO
    #: Per unit, in the holding's currency (buy, sell).
    price: Decimal = ZERO
    fees: Decimal = ZERO
    #: Gross income (dividend, interest); the total cost (transfer_in).
    amount: Decimal = ZERO
    withholding_tax: Decimal = ZERO
    split_to: Decimal = ONE
    split_from: Decimal = ONE
    #: A sale's named lots; empty means first in, first out.
    lots: tuple[LotPick, ...] = ()
    #: Base currency per unit of the holding's currency, on `on`.
    fx_rate: Decimal = ONE
    #: Recording order: breaks ties between transactions of one kind on one date.
    seq: int = 0


# ── Validation ────────────────────────────────────────────────────────────────


def check_number(name: str, value: Decimal, *, positive: bool = False) -> None:
    """A quantity, unit price, ratio or rate Salli can keep exactly: finite,
    not negative (or positive, when `positive`), under 10²⁰, and with at most
    18 decimal places. Raises TransactionError."""
    if not value.is_finite():
        raise TransactionError(f"{name} must be a number, not {value}")
    if value < 0 or (positive and value == 0):
        raise TransactionError(f"{name} must be {'positive' if positive else 'zero or more'}")
    if value >= _LIMIT:
        raise TransactionError(f"{name} must be less than 10^{INTEGER_DIGITS}")
    # Trailing zeros are not places ("1.50000000000000000000" is 1.5), and a
    # value too small for 18 places (1E-999999999) does not round to one.
    if value.quantize(_STEP, context=EXACT) != value:
        raise TransactionError(f"{name} has more than {PLACES} decimal places")


def check_amount(name: str, value: Decimal, *, positive: bool = False) -> None:
    """An amount of money Salli can keep: finite, not negative (or positive),
    and under 10¹⁴, so its minor units fit a BIGINT in any currency."""
    if not value.is_finite():
        raise TransactionError(f"{name} must be an amount, not {value}")
    if value < 0 or (positive and value == 0):
        raise TransactionError(f"{name} must be {'positive' if positive else 'zero or more'}")
    if value >= MONEY_LIMIT:
        raise TransactionError(f"{name} must be less than 10^14")


def validate(tx: Transaction) -> None:
    """Refuse a transaction that is not well formed for its kind."""
    if tx.kind is not Kind.SPLIT:
        check_number("fx_rate", tx.fx_rate, positive=True)
    if tx.kind in (Kind.BUY, Kind.SELL):
        check_number("quantity", tx.quantity, positive=True)
        check_number("price", tx.price)
        check_amount("fees", tx.fees)
    elif tx.kind is Kind.TRANSFER_IN:
        check_number("quantity", tx.quantity, positive=True)
        check_amount("cost", tx.amount)
    elif tx.kind in INCOME:
        check_amount("amount", tx.amount, positive=True)
        check_amount("withholding_tax", tx.withholding_tax)
        if tx.withholding_tax > tx.amount:
            raise TransactionError("withholding_tax cannot exceed the amount")
    else:  # split
        check_number("split ratio", tx.split_to, positive=True)
        check_number("split ratio", tx.split_from, positive=True)
        if tx.split_to == tx.split_from:
            raise TransactionError("A split changes the number of units: its ratio cannot be 1:1")
    if tx.lots:
        if tx.kind is not Kind.SELL:
            raise TransactionError("Only a sale names the lots it sells from")
        named = [pick.lot_id for pick in tx.lots]
        if len(set(named)) != len(named):
            raise TransactionError("A sale names each lot once")
        for pick in tx.lots:
            check_number("a lot's quantity", pick.quantity, positive=True)
        named_total = total(pick.quantity for pick in tx.lots)
        if named_total != tx.quantity:
            raise TransactionError(
                f"The lots named add up to {plain(named_total)} units, "
                f"not the {plain(tx.quantity)} sold"
            )


# ── Results ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Lot:
    """Units acquired together. `quantity` and `cost` are what is still held
    (after splits, less what sales consumed); a closed lot has quantity 0."""

    id: str  # the transaction that opened it
    kind: Kind  # buy or transfer_in
    opened_on: date
    #: The units it opened with, scaled by any split since.
    opened_quantity: Decimal
    quantity: Decimal
    cost: Decimal
    cost_base: Decimal

    @property
    def is_open(self) -> bool:
        return self.quantity > 0


@dataclass(frozen=True)
class Consumed:
    """The part of one lot a sale used up."""

    lot_id: str
    opened_on: date
    quantity: Decimal
    cost: Decimal
    cost_base: Decimal


@dataclass(frozen=True)
class Sale:
    transaction_id: str
    on: date
    quantity: Decimal
    #: quantity × price, before fees.
    proceeds: Decimal
    fees: Decimal
    #: What the consumed lots cost.
    cost: Decimal
    #: proceeds − fees − cost.
    gain: Decimal
    fx_rate: Decimal
    proceeds_base: Decimal
    fees_base: Decimal
    cost_base: Decimal
    gain_base: Decimal
    consumed: tuple[Consumed, ...]


@dataclass(frozen=True)
class Income:
    transaction_id: str
    kind: Kind  # dividend or interest
    on: date
    gross: Decimal
    withholding_tax: Decimal
    #: gross − withholding_tax: what was received.
    net: Decimal
    fx_rate: Decimal
    gross_base: Decimal
    withholding_tax_base: Decimal
    net_base: Decimal


@dataclass(frozen=True)
class Position:
    """What is held at a point in the history."""

    quantity: Decimal
    cost: Decimal
    cost_base: Decimal


@dataclass(frozen=True)
class Book:
    """A holding's history, replayed."""

    #: Every lot ever opened, in the order sales consume them.
    lots: tuple[Lot, ...]
    sales: tuple[Sale, ...]
    income: tuple[Income, ...]

    @property
    def open_lots(self) -> tuple[Lot, ...]:
        return tuple(lot for lot in self.lots if lot.is_open)

    @property
    def position(self) -> Position:
        return Position(
            quantity=total(lot.quantity for lot in self.lots),
            cost=total(lot.cost for lot in self.lots),
            cost_base=total(lot.cost_base for lot in self.lots),
        )


# ── Replay ────────────────────────────────────────────────────────────────────


def ordered(transactions: Iterable[Transaction]) -> list[Transaction]:
    """In the order they take effect (see the module docstring)."""
    return sorted(transactions, key=lambda t: (t.on, _PHASE[t.kind], t.seq, t.id))


class _OpenLot:
    __slots__ = ("id", "kind", "opened_on", "opened_quantity", "quantity", "cost", "cost_base")

    def __init__(
        self, id: str, kind: Kind, opened_on: date, quantity: Decimal, cost: Decimal, rate: Decimal
    ) -> None:
        self.id = id
        self.kind = kind
        self.opened_on = opened_on
        self.opened_quantity = quantity
        self.quantity = quantity
        self.cost = cost
        self.cost_base = cost * rate

    def freeze(self) -> Lot:
        return Lot(
            id=self.id,
            kind=self.kind,
            opened_on=self.opened_on,
            opened_quantity=self.opened_quantity,
            quantity=self.quantity,
            cost=self.cost,
            cost_base=self.cost_base,
        )


def scale(quantity: Decimal, split_to: Decimal, split_from: Decimal) -> Decimal:
    """A quantity after a split, to the 18 places a quantity is kept at."""
    with localcontext(EXACT):
        return (quantity * split_to / split_from).quantize(_STEP)


class Replay:
    """A holding's history, applied a date at a time.

    `advance` moves forward only, so the states a performance report needs
    (each date's position before and after its transactions) come from one
    pass over the history.
    """

    def __init__(self, transactions: Iterable[Transaction]) -> None:
        self._pending = ordered(transactions)
        self._next = 0
        self._lots: list[_OpenLot] = []
        self._sales: list[Sale] = []
        self._income: list[Income] = []

    def advance(self, through: date, *, splits_only_on_last_day: bool = False) -> Replay:
        """Apply every transaction dated on or before `through`. With
        `splits_only_on_last_day`, of those dated `through` only its splits:
        the position at the start of that day."""
        with localcontext(EXACT):
            while self._next < len(self._pending):
                tx = self._pending[self._next]
                if tx.on > through or (
                    splits_only_on_last_day and tx.on == through and tx.kind is not Kind.SPLIT
                ):
                    break
                self._apply(tx)
                self._next += 1
        return self

    def position(self) -> Position:
        return Position(
            quantity=total(lot.quantity for lot in self._lots),
            cost=total(lot.cost for lot in self._lots),
            cost_base=total(lot.cost_base for lot in self._lots),
        )

    def book(self) -> Book:
        return Book(
            lots=tuple(lot.freeze() for lot in self._lots),
            sales=tuple(self._sales),
            income=tuple(self._income),
        )

    # ── one transaction ──────────────────────────────────────────────────────

    def _apply(self, tx: Transaction) -> None:
        if tx.kind is Kind.BUY:
            cost = tx.quantity * tx.price + tx.fees
            self._lots.append(_OpenLot(tx.id, tx.kind, tx.on, tx.quantity, cost, tx.fx_rate))
        elif tx.kind is Kind.TRANSFER_IN:
            self._lots.append(_OpenLot(tx.id, tx.kind, tx.on, tx.quantity, tx.amount, tx.fx_rate))
        elif tx.kind is Kind.SELL:
            self._sell(tx)
        elif tx.kind is Kind.SPLIT:
            for lot in self._lots:
                lot.quantity = scale(lot.quantity, tx.split_to, tx.split_from)
                lot.opened_quantity = scale(lot.opened_quantity, tx.split_to, tx.split_from)
        else:
            self._income.append(
                Income(
                    transaction_id=tx.id,
                    kind=tx.kind,
                    on=tx.on,
                    gross=tx.amount,
                    withholding_tax=tx.withholding_tax,
                    net=tx.amount - tx.withholding_tax,
                    fx_rate=tx.fx_rate,
                    gross_base=tx.amount * tx.fx_rate,
                    withholding_tax_base=tx.withholding_tax * tx.fx_rate,
                    net_base=(tx.amount - tx.withholding_tax) * tx.fx_rate,
                )
            )

    def _sell(self, tx: Transaction) -> None:
        held = total(lot.quantity for lot in self._lots)
        if tx.quantity > held:
            raise TransactionError(
                f"The sale on {tx.on} is of {plain(tx.quantity)} units, "
                f"but only {plain(held)} are held then"
            )
        if tx.lots:
            picks = [(self._named_lot(tx, pick), pick.quantity) for pick in tx.lots]
        else:
            picks = self._first_in_first_out(tx.quantity)

        consumed: list[Consumed] = []
        for lot, quantity in picks:
            if quantity > lot.quantity:
                raise TransactionError(
                    f"The sale on {tx.on} takes {plain(quantity)} units from lot {lot.id}, "
                    f"which holds {plain(lot.quantity)} then"
                )
            if quantity == lot.quantity:
                cost, cost_base = lot.cost, lot.cost_base
            else:
                cost = (lot.cost * quantity / lot.quantity).quantize(_SHARE_STEP)
                cost_base = (lot.cost_base * quantity / lot.quantity).quantize(_SHARE_STEP)
            lot.quantity -= quantity
            lot.cost -= cost
            lot.cost_base -= cost_base
            consumed.append(Consumed(lot.id, lot.opened_on, quantity, cost, cost_base))

        proceeds = tx.quantity * tx.price
        cost = total(c.cost for c in consumed)
        cost_base = total(c.cost_base for c in consumed)
        proceeds_base = proceeds * tx.fx_rate
        fees_base = tx.fees * tx.fx_rate
        self._sales.append(
            Sale(
                transaction_id=tx.id,
                on=tx.on,
                quantity=tx.quantity,
                proceeds=proceeds,
                fees=tx.fees,
                cost=cost,
                gain=proceeds - tx.fees - cost,
                fx_rate=tx.fx_rate,
                proceeds_base=proceeds_base,
                fees_base=fees_base,
                cost_base=cost_base,
                gain_base=proceeds_base - fees_base - cost_base,
                consumed=tuple(consumed),
            )
        )

    def _named_lot(self, tx: Transaction, pick: LotPick) -> _OpenLot:
        for lot in self._lots:
            if lot.id == pick.lot_id:
                return lot
        raise TransactionError(
            f"The sale on {tx.on} names lot {pick.lot_id}, which is not one this holding "
            "had opened by then"
        )

    def _first_in_first_out(self, quantity: Decimal) -> list[tuple[_OpenLot, Decimal]]:
        picks: list[tuple[_OpenLot, Decimal]] = []
        remaining = quantity
        for lot in self._lots:
            if remaining == 0:
                break
            if lot.quantity == 0:
                continue
            take = min(lot.quantity, remaining)
            picks.append((lot, take))
            remaining -= take
        return picks


def replay(transactions: Iterable[Transaction], until: date | None = None) -> Book:
    """The holding's lots, sales and income, from every transaction dated on or
    before `until` (all of them, by default). Raises TransactionError for a
    history that cannot have happened."""
    return Replay(transactions).advance(until or date.max).book()


def split_factor(transactions: Iterable[Transaction], after: date, through: date) -> Decimal:
    """How many units one unit held on `after` became by `through`: the
    product of the splits dated after `after`, up to and including `through`.
    A price quoted on `after` divided by this is the same thing's price per
    unit on `through`."""
    factor = ONE
    with localcontext(EXACT):
        for tx in transactions:
            if tx.kind is Kind.SPLIT and after < tx.on <= through:
                factor = factor * tx.split_to / tx.split_from
    return factor


def total(values: Iterable[Decimal]) -> Decimal:
    """The exact sum of figures from this module. A pro-rata cost can carry
    more digits than Python's default context keeps (28), so a plain `sum`
    outside EXACT would round it; this does not."""
    with localcontext(EXACT):
        return sum(values, ZERO)


def plain(value: Decimal) -> str:
    """A decimal as plain digits without trailing zeros: "10", "0.5", "1234.5678"."""
    if value == 0:
        return "0"
    return format(value.normalize(EXACT), "f")
