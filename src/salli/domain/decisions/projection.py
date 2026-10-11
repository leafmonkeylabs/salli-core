"""
What an option projected, month by month: the part of its timeline a
review compares with what happened. Pure, Decimal.

Each point is a month's end (the first is the as-of date itself) in **that
month's own money**, the money a later baseline reports: cash, investments,
what is owed (debts with terms and liabilities without), net worth, and,
for each full month after the as-of month, the spending the option
expected. A real figure on the monthly timeline is turned into its month's
own money by its deflator; with no inflation set, the two are the same.

Spending is the baseline's average monthly spending in the month's own
money, plus the option's recurring costs that fall in that month, less
what its stopped payments would have cost: what the person expected to
spend, the way the baseline counts spending.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from salli.domain.baseline import timelines
from salli.domain.baseline.models import Baseline
from salli.domain.currency import quantize
from salli.domain.scenarios import engine, schema
from salli.domain.scenarios.engine import Outlook

#: Months recorded past the review date, so a late review still compares.
AFTER_REVIEW_MONTHS = 12


def months_to(as_of: str, month: str) -> int:
    """Calendar months from `as_of`'s month ("YYYY-MM-DD" or "YYYY-MM") to `month`."""
    return timelines.month_index(month[:7]) - timelines.month_index(as_of[:7])


def _spending_changes(baseline: Baseline, scenario: schema.Scenario) -> dict[str, Decimal]:
    """By month, what the scenario adds to spending: its recurring costs,
    less what each stopped outgoing payment would have cost."""
    added: dict[str, Decimal] = defaultdict(Decimal)
    costs = [c for c in scenario.changes if isinstance(c, schema.RecurringChange) and c.amount < 0]
    if costs:
        only = scenario.model_copy(update={"changes": costs})
        for flow in engine.translate(baseline, only).changes.regular:
            added[flow.date[:7]] -= flow.amount
    for change in scenario.changes:
        if not isinstance(change, schema.StopRecurringChange):
            continue
        translation = engine.translate(baseline, scenario.model_copy(update={"changes": [change]}))
        stopped = translation.applied[0].stopped if translation.applied else ()
        if stopped and all(s.amount < 0 for s in stopped):
            for flow in translation.changes.regular:
                added[flow.date[:7]] -= flow.amount
    return added


def projection(
    baseline: Baseline,
    scenario: schema.Scenario | None,
    outlook: Outlook,
    months: int,
) -> list[dict[str, str | None]]:
    """The first `months` month-ends after the as-of date (and the as-of
    point), each in its own money, as decimal strings."""
    currency = baseline.currency

    def money(value: Decimal) -> str:
        return str(quantize(value, currency, strict=False))

    changes = _spending_changes(baseline, scenario) if scenario is not None else {}
    points = outlook.monthly.points[: months + 1]
    out: list[dict[str, str | None]] = []
    for i, point in enumerate(points):
        level = point.deflator
        spending: str | None = None
        # The as-of point is a day, and the as-of month is already partly
        # over: spending is projected for the full months after it.
        if i >= 2:
            spending = money(baseline.flows.expenses * level + changes.get(point.month, Decimal(0)))
        out.append(
            {
                "month": point.month,
                "date": point.date,
                "cash": money(point.cash * level),
                "investments": money(point.investments * level),
                "owed": money((point.debts + point.other_liabilities) * level),
                "net_worth": money(point.net_worth * level),
                "spending": spending,
            }
        )
    return out
