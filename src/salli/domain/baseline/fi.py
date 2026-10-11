"""
Financial independence on the monthly timeline. Pure, Decimal, real terms.

FI's date and projections come from the baseline's monthly timeline
(`timelines.monthly`), where cash, investments and debts are kept apart: cash
earns nothing and takes the surplus, investments grow at the real return,
debts follow their schedules. So FI, the baseline and every scenario agree:
a scenario with no changes has the baseline's FI exactly.

- **The FI number** is a year of the spending to live on, over the safe
  withdrawal rate: the FIRE strategy's target, when it names one, or the
  baseline's average monthly spending (and a scenario's spending for good).
  Zero while there is no spending to go by.
- **The FI asset base** at a month's end is what could fund withdrawals:
  cash and investments, less debts and other liabilities, in today's money.
  What else is owned (a home) funds none.
- **The FI month** is the first month whose end the base reaches the
  number, searched to 50 years whatever horizon is shown, counted in months
  from the as-of month (0: reached by its end, or already). None while there
  is no number, or when it isn't reached within 50 years.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from salli.domain.baseline import timelines
from salli.domain.baseline.models import Baseline
from salli.domain.debt.engine import month_after

#: How far the FI month is looked for: the longest timeline.
FI_YEARS = timelines.MAX_HORIZON_YEARS


def spending(baseline: Baseline) -> Decimal:
    """The monthly spending FI is built on: the FIRE strategy's target, when
    it names one, else the baseline's average spending."""
    target = baseline.strategy.target_monthly_expenses if baseline.strategy else None
    if target is not None and target > 0:
        return target
    return baseline.flows.expenses


def fi_number(baseline: Baseline, monthly_spending: Decimal | None = None) -> Decimal:
    """12 × `monthly_spending` (the baseline's, `spending`, when None) over the
    safe withdrawal rate; zero without spending or a rate."""
    spend = spending(baseline) if monthly_spending is None else monthly_spending
    swr = baseline.assumptions.safe_withdrawal_rate.value
    annual = spend * 12
    return annual / swr if annual > 0 and swr > 0 else Decimal(0)


def asset_base(point: timelines.MonthPoint) -> Decimal:
    """What could fund withdrawals at a point, in today's money."""
    return point.cash + point.investments - point.debts - point.other_liabilities


def months_to_fi(points: Sequence[timelines.MonthPoint], number: Decimal) -> int | None:
    """Months from the as-of month to the first month-end at which the asset
    base reaches `number`: 0 when it already has (the as-of point) or does by
    the as-of month's end. `points` are a monthly timeline's."""
    if number <= 0 or not points:
        return None
    if asset_base(points[0]) >= number:
        return 0
    for i, point in enumerate(points[1:]):
        if asset_base(point) >= number:
            return i
    return None


def fi_month(baseline: Baseline, months: int | None) -> str | None:
    """The calendar month ("YYYY-MM") `months` after the as-of month."""
    return None if months is None else month_after(baseline.as_of.isoformat()[:7], months)


def year_points(points: Sequence[timelines.MonthPoint], years: int) -> list[timelines.MonthPoint]:
    """The as-of point, then the point at each whole year on (the end of the
    month 12 × k months after the as-of month), to `years`."""
    return [
        points[0],
        *(points[12 * k + 1] for k in range(1, years + 1) if 12 * k + 1 < len(points)),
    ]


@dataclass(frozen=True)
class FiOutlook:
    """When FI is reached on one monthly timeline."""

    fi_number: Decimal
    #: Months from the as-of month, and the month; None when not reached
    #: within 50 years, or there is no number yet.
    months: int | None
    month: str | None
    #: The real return the timeline's investments grew at.
    real_return: Decimal


def outlook(
    baseline: Baseline, timeline: timelines.MonthlyTimeline, number: Decimal | None = None
) -> FiOutlook:
    """FI on `timeline` (a monthly timeline to 50 years, for the FI month to
    be found wherever it falls), against `number` (the baseline's when None)."""
    number = fi_number(baseline) if number is None else number
    months = months_to_fi(timeline.points, number)
    return FiOutlook(number, months, fi_month(baseline, months), timeline.real_return)


def full_timeline(
    baseline: Baseline,
    changes: timelines.Changes = timelines.NO_CHANGES,
    *,
    real_return: Decimal | None = None,
) -> timelines.MonthlyTimeline:
    """The monthly timeline to 50 years: what the FI month and the debts'
    payoff are read from, whatever horizon is shown."""
    return timelines.monthly(baseline, FI_YEARS, changes, real_return=real_return)
