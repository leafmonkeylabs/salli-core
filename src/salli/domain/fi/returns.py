"""
Where the odds' returns come from (docs/baseline.md#the-odds). Pure, seeded.

One source gives both the mean and the volatility, never a mix of two:

- **yours**, when you set your own return (real, or nominal with your
  inflation) and your own volatility;
- else **the pack's**: the active capital-market assumptions' mix (its
  expected return and its volatility), or the labelled placeholder pack.

The weighted expense ratio of your holdings comes off the mean. A pack that
gives a `history` of the mix's monthly returns is resampled (a year's window
of consecutive months at a time, from a random start, wrapping round)
instead of drawn from a Student-t; its own mean less the expense ratio is
the mean.

`sustained_rate` is the safe withdrawal rate the FI number uses when you set
none: the highest constant real withdrawal a year, as a share of the pool,
that `DEFAULT_SUCCESS` of `DEFAULT_PATHS` seeded paths sustain over the
person's own drawdown (`Drawdown`: from the FI month to their planning age;
`DRAWDOWN_YEARS`, labelled, without a date of birth) (yearly returns, the withdrawal at each year's end:
1 / Σₖ 1/Gₖ, Gₖ the growth to year k).
"""

from __future__ import annotations

import datetime as dt
import functools
import math
import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

DEFAULT_PATHS = 1000
DEFAULT_SEED = 1
DEFAULT_SUCCESS = Decimal("0.9")
#: The years a derived withdrawal rate must last when there is no date of
#: birth to count to a planning age from: a labelled placeholder, the span
#: most writing on withdrawal rates tests, not anyone's lifespan.
DRAWDOWN_YEARS = 30
#: The planning age a drawdown runs to when the person set none: a labelled
#: placeholder, not a life expectancy.
PLANNING_AGE = 95
#: The fewest years a derived rate is tested over.
MIN_DRAWDOWN_YEARS = 5
#: The range a derived rate is held to: the bounds of a rate you set.
RATE_BOUNDS = (Decimal("0.01"), Decimal("0.10"))
_TWELVE = Decimal(12)
_FLOOR = Decimal("-0.95")

Origin = Literal["user", "pack", "placeholder"]


@dataclass(frozen=True)
class Drawdown:
    """The years a derived withdrawal rate must last, and why."""

    years: int
    origin: Literal["user", "placeholder"]
    says: str


#: Without a date of birth.
NO_BIRTH = Drawdown(
    DRAWDOWN_YEARS,
    "placeholder",
    f"Placeholder: {DRAWDOWN_YEARS} years drawn down, without a date of birth to count to a "
    "planning age from. Set your date of birth and planning age to replace it.",
)


def drawdown(born: dt.date | None, planning_age: int | None, start: str) -> Drawdown:
    """From `start` (\"YYYY-MM\", the FI month) to the planning age (the
    person's, else the placeholder `PLANNING_AGE`), whole years rounded up."""
    if born is None:
        return NO_BIRTH
    age = planning_age or PLANNING_AGE
    months = (int(start[:4]) - born.year) * 12 + int(start[5:7]) - born.month
    years = max(MIN_DRAWDOWN_YEARS, -(-(age * 12 - months) // 12))
    if planning_age is not None:
        return Drawdown(
            years, "user", f"{years} years drawn down, from {start} to your planning age of {age}."
        )
    return Drawdown(
        years,
        "placeholder",
        f"Placeholder: {years} years drawn down, from {start} to a planning age of {age}, not a "
        "life expectancy. Set your own planning age to replace it.",
    )


@dataclass(frozen=True)
class ReturnSource:
    """The mean and volatility the odds draw with, from one source."""

    #: Yearly, real, before the expense ratio comes off.
    gross_mean: Decimal
    volatility: Decimal
    #: The Student-t degrees of freedom.
    tails: Decimal
    origin: Origin
    #: The holdings' weighted yearly expense ratio.
    expense_ratio: Decimal = Decimal(0)
    #: The pack's monthly returns, resampled instead of a Student-t.
    history: tuple[Decimal, ...] | None = None

    @property
    def method(self) -> Literal["student_t", "bootstrap"]:
        return "student_t" if self.history is None else "bootstrap"

    @property
    def mean(self) -> Decimal:
        """The yearly mean drawn with: the source's (the history's own, when
        resampled) less the expense ratio."""
        if self.history is not None:
            return sum(self.history, Decimal(0)) / len(self.history) * 12 - self.expense_ratio
        return self.gross_mean - self.expense_ratio

    def monthly(self, months: int, paths: int, seed: int) -> list[list[Decimal]]:
        """`paths` sequences of `months` monthly real returns."""
        if self.history is None:
            return student_t(self.mean, self.volatility, months, paths, seed, self.tails)
        rng = random.Random(seed)
        series, n, fee = self.history, len(self.history), self.expense_ratio / _TWELVE
        out: list[list[Decimal]] = []
        for _ in range(paths):
            path: list[Decimal] = []
            while len(path) < months:
                start = rng.randrange(n)
                path.extend(max(_FLOOR, series[(start + k) % n] - fee) for k in range(12))
            out.append(path[:months])
        return out


def student_t(
    mean: Decimal,
    volatility: Decimal,
    months: int,
    paths: int,
    seed: int,
    tails: Decimal,
) -> list[list[Decimal]]:
    """`paths` sequences of `months` monthly real returns: a normal over the
    square root of a chi-squared with `tails` degrees of freedom over
    `tails`, times √((ν − 2)/ν) for unit variance, at `mean` over twelve and
    `volatility` over √12; each written to nine places."""
    rng = random.Random(seed)
    mu = mean / _TWELVE
    sd = volatility / _TWELVE.sqrt()
    nu = float(tails)
    scale = math.sqrt((nu - 2) / nu)

    def t() -> float:
        return rng.gauss(0.0, 1.0) * scale / math.sqrt(rng.gammavariate(nu / 2, 2.0) / nu)

    out: list[list[Decimal]] = []
    for _ in range(paths):
        out.append([max(_FLOOR, mu + sd * Decimal(f"{t():.9f}")) for _ in range(months)])
    return out


def sustained_rate(source: ReturnSource, years: int = DRAWDOWN_YEARS) -> Decimal:
    """The derived withdrawal rate (see the module), to four places."""
    return _sustained(
        float(source.mean),
        float(source.volatility),
        float(source.tails),
        source.history,
        float(source.expense_ratio),
        years,
    )


@functools.lru_cache(maxsize=256)
def _sustained(
    mean: float,
    volatility: float,
    tails: float,
    history: tuple[Decimal, ...] | None,
    expense: float,
    years: int,
) -> Decimal:
    rng = random.Random(DEFAULT_SEED)
    scale = math.sqrt((tails - 2) / tails)
    series = None if history is None else [float(r) - expense / 12 for r in history]
    rates: list[float] = []
    for _ in range(DEFAULT_PATHS):
        growth, total = 1.0, 0.0
        for _ in range(years):
            if series is None:
                z = (
                    rng.gauss(0.0, 1.0)
                    * scale
                    / math.sqrt(rng.gammavariate(tails / 2, 2.0) / tails)
                )
                r = max(-0.95, mean + volatility * z)
            else:
                start = rng.randrange(len(series))
                r = (
                    math.prod(1 + max(-0.95, series[(start + k) % len(series)]) for k in range(12))
                    - 1
                )
            growth *= 1 + r
            total += 1 / growth
        rates.append(1 / total)
    rates.sort()
    rate = Decimal(f"{rates[int((1 - float(DEFAULT_SUCCESS)) * (len(rates) - 1))]:.4f}")
    low, high = RATE_BOUNDS
    return min(max(rate, low), high)
