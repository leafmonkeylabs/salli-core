"""
Rates of return, from dated money and valuations. Pure.

Time-weighted return (`twr`)
    The growth of one unit of money kept invested throughout, whatever was
    added or taken out along the way: the period is cut at every day money
    moved, each piece's growth is measured from valuations, and the pieces are
    chained. It is the investments' own performance, not the investor's
    timing, and the figure to compare with a fund's or an index's.

    On a day money moves, units bought come in at the start of the day and
    units sold or income paid go out at its end (the convention Portfolio
    Performance documents as "true time-weighted"), so a purchase's fees and a
    sale's proceeds both fall inside the day they happen:

        a day's growth     = (value after + money out) / (value before + money in)
        between two days   = value before the later / value after the earlier

    Income paid when nothing is held any more (a dividend for units sold
    before it was paid) belongs to the time they were held, and is credited to
    the last piece of the period in which something was.

Money-weighted return (`xirr`)
    The annual rate r at which the period's money, each amount discounted from
    its own day, comes to nothing:

        Σ amountᵢ / (1 + r) ^ (daysᵢ / 365) = 0

    (actual/365 days, as spreadsheets' XIRR counts them). Unlike the
    time-weighted return it does depend on when money went in and out: it is
    the investor's own rate. See `xirr` for how it is solved.

Both are fractions of one ("0.0725" is 7.25%) and are computed in Decimal at 50
significant digits, deterministically: the same flows give the same digits on
any machine.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
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

#: Rates are inexact by nature (a root, a product of ratios); 50 digits is far
#: past anything shown, and leaves room for (1 + r) ^ t of extreme rates.
RATE = Context(
    prec=50,
    rounding=ROUND_HALF_EVEN,
    Emax=999_999,
    Emin=-999_999,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)

_ZERO = Decimal(0)
_ONE = Decimal(1)
_YEAR = Decimal(365)


@dataclass(frozen=True)
class Flow:
    """Money between the investor and the investment on a day: negative paid
    in (a purchase), positive received (a sale, income, what is left at the end)."""

    on: date
    amount: Decimal


@dataclass(frozen=True)
class Day:
    """A day money moved, valued at that day's prices."""

    on: date
    #: What was held before the day's money moved.
    before: Decimal
    #: What was held after.
    after: Decimal
    #: Paid in (units bought, or transferred in at their cost).
    inflow: Decimal
    #: Taken out (a sale's proceeds less fees) or paid out (income).
    outflow: Decimal


# ── time-weighted ─────────────────────────────────────────────────────────────


def twr(start: Decimal, days: Sequence[Day], end: Decimal) -> Decimal | None:
    """The time-weighted return from a value of `start`, through `days` (in
    date order), to a value of `end`. None when it is not defined: nothing was
    ever at risk, or value appeared from nothing (worth 0, then more without
    money going in)."""
    with localcontext(RATE):
        pieces: list[list[Decimal]] = []  # [numerator, denominator]
        held = start
        for day in days:
            if held != 0:
                pieces.append([day.before, held])
            elif day.before != 0:
                return None
            numerator, denominator = day.after + day.outflow, day.before + day.inflow
            if denominator != 0:
                pieces.append([numerator, denominator])
            elif numerator != 0:
                # Paid out with nothing held: credit it to the last piece in
                # which something was.
                last = next((p for p in reversed(pieces) if p[1] != 0), None)
                if last is None:
                    return None
                last[0] += numerator
            held = day.after
        if held != 0:
            pieces.append([end, held])
        elif end != 0:
            return None
        if not pieces:
            return None
        growth = _ONE
        for numerator, denominator in pieces:
            growth = growth * numerator / denominator
        return growth - 1


def annualised(rate: Decimal, days: int) -> Decimal | None:
    """A return over `days` as the yearly rate that compounds to it. Only for
    a year or more: a short period's return compounded up says little but
    looks precise. None for shorter periods."""
    if days < 365:
        return None
    with localcontext(RATE):
        growth = _ONE + rate
        if growth <= 0:
            return -_ONE
        return growth ** (_YEAR / Decimal(days)) - 1


# ── money-weighted ────────────────────────────────────────────────────────────

#: Where to look for a root, as x = ln(1 + r): r from −100% (just above) to
#: about e⁸⁰ — a day's trade can annualise to astronomical rates.
_GRID = tuple(
    Decimal(x)
    for x in (
        "-30", "-20", "-10", "-5", "-2", "-1", "-0.5", "-0.2", "-0.1", "-0.05",
        "0",
        "0.05", "0.1", "0.2", "0.5", "1", "2", "5", "10", "20", "40", "80",
    )
)  # fmt: skip
#: Converged when the bracket around x is narrower than this.
_TOLERANCE = Decimal("1e-16")
#: And never more steps than this (each at least halves the bracket every
#: second step, so ~120 suffice from the widest bracket on the grid).
_MAX_STEPS = 300


def xirr(flows: Sequence[Flow]) -> Decimal | None:
    """The money-weighted annual return of dated `flows`, or None when there
    is none: no money in or none out, or all of it on one day.

    How it is solved, deterministically:

    1. Amounts on the same day are added together; days that net to nothing
       are dropped. The rate is sought as x = ln(1 + r), where the discounted
       sum f(x) = Σ aᵢ·e^(−tᵢx) is smooth and has no pole.
    2. f is evaluated on a fixed grid of x (r from just above −100% to about
       e⁸⁰). Every adjacent pair where it changes sign brackets a root.
    3. Each bracket is narrowed by Newton's method from the last point, when
       the step lands inside the bracket and has at least halved it since two
       steps before; otherwise by bisection. That keeps Newton's speed and
       bisection's guarantee: it converges when the bracket is narrower than
       10⁻¹⁶ (or f is exactly 0), in at most 300 steps.
    4. Flows that change sign more than once can have several rates; the one
       nearest 0% is the answer, as the economically meaningful one.

    The result is e^x − 1 at 50 significant digits.
    """
    by_day: dict[date, Decimal] = {}
    for flow in flows:
        by_day[flow.on] = by_day.get(flow.on, _ZERO) + flow.amount
    points = sorted((on, amount) for on, amount in by_day.items() if amount != 0)
    if not any(a > 0 for _, a in points) or not any(a < 0 for _, a in points):
        return None
    first = points[0][0]
    if all(on == first for on, _ in points):
        return None

    with localcontext(RATE):
        terms = [(Decimal((on - first).days) / _YEAR, amount) for on, amount in points]

        def f(x: Decimal) -> tuple[Decimal, Decimal]:
            """The discounted sum at x, and its derivative."""
            value = derivative = _ZERO
            for t, amount in terms:
                term = amount * (-t * x).exp()
                value += term
                derivative -= t * term
            return value, derivative

        values = [f(x)[0] for x in _GRID]
        roots: list[Decimal] = [x for x, value in zip(_GRID, values, strict=True) if value == 0]
        for i in range(len(_GRID) - 1):
            low, high = values[i], values[i + 1]
            if low != 0 and high != 0 and (low > 0) != (high > 0):
                roots.append(_narrow(f, _GRID[i], _GRID[i + 1], low > 0))
        if not roots:
            return None
        x = min(roots, key=abs)
        return x.exp() - 1


def _narrow(
    f: Callable[[Decimal], tuple[Decimal, Decimal]],
    low: Decimal,
    high: Decimal,
    positive_at_low: bool,
) -> Decimal:
    """The root of f in [low, high], where f changes sign (see `xirr`)."""
    x = (low + high) / 2
    widths = [high - low, high - low]
    for _ in range(_MAX_STEPS):
        value, derivative = f(x)
        if value == 0:
            return x
        if (value > 0) == positive_at_low:
            low = x
        else:
            high = x
        width = high - low
        if width < _TOLERANCE:
            break
        newton = x - value / derivative if derivative != 0 else None
        fast_enough = width <= widths[-2] / 2
        widths.append(width)
        if newton is not None and low < newton < high and fast_enough:
            x = newton
        else:
            x = (low + high) / 2
    return (low + high) / 2
