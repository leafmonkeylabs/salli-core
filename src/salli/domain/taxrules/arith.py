"""
The arithmetic every rule set is computed with: one decimal context, rounding to
a unit, and progressive band tables.

Everything here runs inside `decimal_context()`, never the ambient context, so a
result cannot depend on what some other code set `decimal.getcontext()` to.

Precision is 28 significant digits: Python's default context, fixed here so
that a fraction that doesn't terminate (a cap of one third of income, say)
always keeps the same digits. Twenty-eight digits is far beyond any amount of
money (a trillion with four decimals is 17 digits), and a literal or figure
with more significant digits than that is refused rather than rounded.
"""

from __future__ import annotations

import decimal
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

#: Significant digits every evaluation keeps. See the module docstring.
PRECISION = 28

RoundingMode = Literal["nearest", "down", "up", "half_even"]

#: The rounding modes a rule set may name, and what each does to a value that
#: lies between two multiples of the unit. "nearest" breaks a tie away from zero
#: (ROUND_HALF_UP, the way tax authorities usually round); "half_even" breaks
#: it towards the even multiple (banker's rounding). "down" goes towards zero
#: and "up" away from it, like Python's ROUND_DOWN and ROUND_UP, so a refund
#: (a negative amount) rounds by its size, just as a bill does.
ROUNDING_MODES: tuple[RoundingMode, ...] = ("nearest", "down", "up", "half_even")

_CONTEXT = decimal.Context(
    prec=PRECISION,
    rounding=decimal.ROUND_HALF_EVEN,
    Emin=-999_999,
    Emax=999_999,
    capitals=1,
    clamp=0,
    flags=[],
    # A result that is undefined, infinite or too large to hold is an error,
    # never a NaN or an Infinity that flows on into somebody's tax.
    traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow],
)


@contextmanager
def decimal_context() -> Generator[decimal.Context]:
    """A fresh copy of the evaluation context, installed for the block."""
    with decimal.localcontext(_CONTEXT) as ctx:
        yield ctx


def significant_digits(value: Decimal) -> int:
    """How many significant digits `value` has, ignoring trailing zeros
    (so "1.500" has two, "1500" has two, "0.0015" has two)."""
    digits = value.as_tuple().digits
    end = len(digits)
    while end > 1 and digits[end - 1] == 0:
        end -= 1
    start = 0
    while start < end - 1 and digits[start] == 0:
        start += 1
    return end - start


def normalized_str(value: Decimal) -> str:
    """The shortest plain string for `value`: "0.15", "100", "0" (never "1E+2",
    "0.150" or "-0"). Used wherever two spellings of a number must agree."""
    if value == 0:
        return "0"
    with decimal_context() as ctx:
        ctx.prec = max(PRECISION, significant_digits(value))
        return format(value.normalize(), "f")


def round_to(value: Decimal, mode: RoundingMode, unit: Decimal) -> Decimal:
    """`value` rounded to a multiple of `unit` (unit 1 is whole units, 0.01 is
    hundredths, 5 is fives).

    Works on the magnitude with an exact quotient and remainder, so the result
    is exactly a multiple of `unit` and the tie test is exact too; a value too
    large to divide exactly by `unit`, or whose rounded result needs more than
    `PRECISION` digits, raises `decimal.InvalidOperation` rather than rounding
    twice. Call it inside `decimal_context()`.
    """
    if unit <= 0:
        raise ValueError(f"A rounding unit must be positive, got {unit}")
    if mode not in ROUNDING_MODES:
        raise ValueError(f"Unknown rounding mode {mode!r}")
    negative = value < 0
    quotient, remainder = divmod(value.copy_abs(), unit)
    step = 0
    if remainder:
        if mode == "up":
            step = 1
        elif mode in ("nearest", "half_even"):
            with decimal.localcontext() as wide:
                wide.prec = PRECISION + 2
                twice = remainder + remainder
            if twice > unit or (twice == unit and (mode == "nearest" or quotient % 2 == 1)):
                step = 1
    with decimal.localcontext() as wide:
        wide.prec = 2 * PRECISION + 2
        exact = (quotient + step) * unit
    # Back to the evaluation's precision, refusing a result that won't fit
    # rather than silently making it no longer a multiple of `unit`.
    strict = decimal.getcontext().copy()
    strict.traps[decimal.Inexact] = True
    try:
        result = strict.plus(exact)
    except decimal.Inexact:
        raise decimal.InvalidOperation(
            f"{value} rounded to a multiple of {unit} needs more than {PRECISION} digits"
        ) from None
    if result == 0:
        return result.copy_abs()
    return -result if negative else result


@dataclass(frozen=True)
class Rounding:
    mode: RoundingMode
    unit: Decimal

    def apply(self, value: Decimal) -> Decimal:
        return round_to(value, self.mode, self.unit)


@dataclass(frozen=True)
class Band:
    """One band of a progressive table. `upto` is the band's ceiling, counted
    from zero (cumulative, as tax tables are printed); None for the last band,
    which has no ceiling."""

    upto: Decimal | None
    rate: Decimal


@dataclass(frozen=True)
class BandTable:
    """A progressive schedule. When `rounding` is set, each band's tax is
    rounded on its own before the bands are added up, which is how some
    authorities print their tables."""

    bands: tuple[Band, ...]
    rounding: Rounding | None = None

    def __post_init__(self) -> None:
        # The schema checks all of this with paths for the author; this is the
        # engine's own guard, so a table built in code can't be malformed either.
        if not self.bands:
            raise ValueError("A band table needs at least one band")
        if self.bands[-1].upto is not None:
            raise ValueError("The last band must have no ceiling")
        previous = Decimal(0)
        for band in self.bands[:-1]:
            if band.upto is None:
                raise ValueError("Only the last band may have no ceiling")
            if band.upto <= previous:
                raise ValueError("Band ceilings must be positive and strictly ascend")
            previous = band.upto
        for band in self.bands:
            if not Decimal(0) <= band.rate <= Decimal(1):
                raise ValueError("Band rates must be between 0 and 1")

    def amount_in_band(self, amount: Decimal, n: int) -> Decimal:
        """How much of `amount` falls in band `n` (1-based). Nothing falls in
        any band of an amount of zero or less."""
        if not 1 <= n <= len(self.bands):
            raise ValueError(f"Band {n} does not exist; the table has {len(self.bands)}")
        lower = self.bands[n - 2].upto if n > 1 else Decimal(0)
        assert lower is not None  # only the last band is unbounded
        upto = self.bands[n - 1].upto
        above = max(Decimal(0), amount - lower)
        if upto is None:
            return above
        return min(above, upto - lower)

    def tax_in_band(self, amount: Decimal, n: int) -> Decimal:
        """The tax on the part of `amount` in band `n`, rounded if the table
        rounds per band."""
        tax = self.amount_in_band(amount, n) * self.bands[n - 1].rate
        return self.rounding.apply(tax) if self.rounding else tax

    def tax(self, amount: Decimal) -> Decimal:
        """The total tax on `amount`: each band's tax, added up in order."""
        total = Decimal(0)
        for n in range(1, len(self.bands) + 1):
            total += self.tax_in_band(amount, n)
        return total
