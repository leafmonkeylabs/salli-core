"""
Risk figures for a portfolio over a period, from its monthly time-weighted
returns (performance.report over each calendar month). Pure.

  volatility     the monthly returns' standard deviation × √12, a yearly figure
  max_drawdown   the largest fall, as a fraction, of the growth of one unit
                 kept invested, from a month-end high to a later month-end low
  sharpe         (the yearly return − the hurdle) ÷ volatility; the hurdle is
                 a cash yield the person gives (their assumptions' cash
                 yield, say), else the benchmark's own yearly return

  tracking_error the standard deviation of the monthly differences from a
                 benchmark × √12

A blended benchmark weights several recorded series (`blend`): the person's
investment policy targets give the weights, each class measured against a
series they name. Net of fees, the yearly return less the holdings'
weighted expense ratio (prices of a fund that already nets its costs are
then counted twice, so the figure is labelled as the person's own ratio).

A benchmark is a series of closes the person records for any symbol (an index
they follow): its monthly returns come from its last close on or before each
month's end. Nothing is fetched. Fewer than two monthly returns give no
volatility, and so no Sharpe ratio.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext

from salli.domain.portfolio.returns import RATE

_TWELVE = Decimal(12)


def month_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Each calendar month the period touches, clipped to it."""
    windows: list[tuple[date, date]] = []
    first = start
    while first <= end:
        following = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        windows.append((first, min(following - timedelta(days=1), end)))
        first = following
    return windows


@dataclass(frozen=True)
class RiskFigures:
    months: int
    yearly_return: Decimal | None
    volatility: Decimal | None
    max_drawdown: Decimal | None
    sharpe: Decimal | None


def figures(monthly: Sequence[Decimal], hurdle: Decimal | None) -> RiskFigures:
    """From monthly returns (fractions of one) and a yearly hurdle."""
    n = len(monthly)
    if n == 0:
        return RiskFigures(0, None, None, None, None)
    with localcontext(RATE):
        growth, peak, worst = Decimal(1), Decimal(1), Decimal(0)
        for r in monthly:
            growth *= 1 + r
            peak = max(peak, growth)
            worst = max(worst, (peak - growth) / peak)
        yearly = growth ** (_TWELVE / n) - 1 if growth > 0 else Decimal(-1)
        volatility = None
        if n >= 2:
            mean = sum(monthly, Decimal(0)) / n
            variance = sum(((r - mean) ** 2 for r in monthly), Decimal(0)) / (n - 1)
            volatility = variance.sqrt() * _TWELVE.sqrt()
        sharpe = (
            (yearly - hurdle) / volatility
            if volatility is not None and volatility > 0 and hurdle is not None
            else None
        )
    return RiskFigures(n, yearly, volatility, worst, sharpe)


def series_returns(
    closes: Sequence[tuple[date, Decimal]], windows: Sequence[tuple[date, date]]
) -> list[Decimal] | None:
    """A recorded series' monthly returns over `windows`, from its last close
    on or before the day before each window and on its last day; None when a
    month has no close to start from."""
    ordered = sorted(closes)

    def close_on(day: date) -> Decimal | None:
        found = None
        for on, price in ordered:
            if on > day:
                break
            found = price
        return found

    returns: list[Decimal] = []
    with localcontext(RATE):
        for first, last in windows:
            before, after = close_on(first - timedelta(days=1)), close_on(last)
            if before is None or after is None:
                return None
            returns.append(after / before - 1)
    return returns


def tracking_error(own: Sequence[Decimal], bench: Sequence[Decimal]) -> Decimal | None:
    """The monthly differences' standard deviation × √12; None under two
    months or when the series differ in length."""
    n = len(own)
    if n < 2 or len(bench) != n:
        return None
    with localcontext(RATE):
        diffs = [a - b for a, b in zip(own, bench, strict=True)]
        mean = sum(diffs, Decimal(0)) / n
        variance = sum(((d - mean) ** 2 for d in diffs), Decimal(0)) / (n - 1)
        return variance.sqrt() * _TWELVE.sqrt()


def blend(series: Sequence[tuple[Decimal, Sequence[Decimal]]]) -> list[Decimal]:
    """Monthly returns weighted across series, `(weight, returns)` with the
    weights summing to 1 and the series of one length."""
    months = len(series[0][1])
    with localcontext(RATE):
        return [sum((w * r[k] for w, r in series), Decimal(0)) for k in range(months)]
