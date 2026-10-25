"""
Reviews: what the chosen option projected, against what happened. Pure.

A review compares at a month's end: the last one on or before the day of
the review (the review date itself, when it is a month's last day). There,
the chosen option's projection (`projection.py`, recorded with the entry)
meets the baseline as of that day:

- **cash**, **investments**, **owed** (debts with terms and liabilities
  without) and **net worth**, each in that day's own money;
- **spending**: the average a month over the full months from the one after
  the decision's as-of month to the compared month, projected against what
  the ledger shows was spent (the baseline's one definition: netted per
  calendar month).

Each with the difference, actual less projected. Nothing is judged: a
difference is what happened, and why it happened is the person's to say in
their reflection. The other options' projections at the same month are
shown beside it, as what they expected, never as what would have happened.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from salli.domain.baseline.models import Baseline, MonthFlow
from salli.domain.currency import quantize
from salli.domain.decisions.projection import months_to
from salli.domain.scenarios.engine import STALE_AFTER_DAYS

FIGURES = ("cash", "investments", "owed", "net_worth")


def month_end(day: dt.date) -> dt.date:
    """The last day of `day`'s month."""
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def earliest_review(as_of: dt.date) -> dt.date:
    """The first day a decision made as of `as_of` can be reviewed on: the
    end of its as-of month, the first month-end its projection has."""
    return month_end(as_of)


def comparison_date(review_as_of: dt.date) -> dt.date:
    """The month's end a review on `review_as_of` compares at: that day,
    when it is a month's last, else the end of the month before."""
    if review_as_of == month_end(review_as_of):
        return review_as_of
    return review_as_of.replace(day=1) - dt.timedelta(days=1)


def compared_at(entry: Mapping[str, Any], review_as_of: dt.date) -> tuple[dt.date, list[str]]:
    """The day a review on `review_as_of` compares at, kept within the
    projection the entry recorded, and a note if it had to be."""
    projection: list[Mapping[str, Any]] = _chosen(entry)["projection"]
    at = comparison_date(review_as_of)
    last = dt.date.fromisoformat(str(projection[-1]["date"]))
    if at > last:
        return last, [
            f"The projection recorded with the decision runs to {last.isoformat()}, so the "
            "review compares there."
        ]
    return at, []


def _chosen(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    chosen = entry["chosen"]
    return next(o for o in entry["options"] if o["label"] == chosen)


def _at(projection: Sequence[Mapping[str, Any]], as_of: str, at: dt.date) -> Mapping[str, Any]:
    index = months_to(as_of, at.isoformat()) + 1
    return projection[max(1, min(index, len(projection) - 1))]


def compare(
    entry: Mapping[str, Any],
    *,
    at: dt.date,
    actual: Baseline,
    spent: Sequence[MonthFlow],
) -> dict[str, Any]:
    """What the entry's chosen option projected at the month's end `at`,
    against `actual` (the baseline as of `at`) and `spent` (the months the
    ledger shows, from a baseline whose months reach `at`'s), as decimal
    strings: actual less projected."""
    currency = str(entry["currency"])
    as_of = str(entry["as_of"])

    def money(value: Decimal) -> str:
        return str(quantize(value, currency, strict=False))

    chosen = _chosen(entry)
    projected = _at(chosen["projection"], as_of, at)
    actual_values = {
        "cash": actual.cash + actual.savings,
        "investments": actual.investments,
        "owed": actual.debts_owed + actual.other_liabilities,
        "net_worth": actual.cash
        + actual.savings
        + actual.investments
        + actual.other_assets
        - actual.debts_owed
        - actual.other_liabilities,
    }
    rows: list[dict[str, str]] = []
    for name in FIGURES:
        was = Decimal(str(projected[name]))
        now = quantize(actual_values[name], currency, strict=False)
        rows.append(
            {
                "figure": name,
                "projected": money(was),
                "actual": money(now),
                "difference": money(now - was),
            }
        )

    notes: list[str] = []
    by_month = {m.month: m for m in spent}
    months: list[str] = []
    projected_total = Decimal(0)
    actual_total = Decimal(0)
    for point in chosen["projection"][2:]:
        if str(point["date"]) > at.isoformat():
            break
        month = str(point["month"])
        flow = by_month.get(month)
        if flow is None or point["spending"] is None:
            notes.append(f"{month}: the ledger shows no spending to compare.")
            continue
        months.append(month)
        projected_total += Decimal(str(point["spending"]))
        actual_total += flow.expenses
    spending: dict[str, Any]
    if months:
        count = Decimal(len(months))
        was = quantize(projected_total / count, currency, strict=False)
        now = quantize(actual_total / count, currency, strict=False)
        spending = {
            "months": months,
            "projected": money(was),
            "actual": money(now),
            "difference": money(now - was),
        }
    else:
        spending = {"months": [], "projected": None, "actual": None, "difference": None}
        notes.append(
            "No full month has passed since the decision's as-of month, so there is no "
            "spending to compare yet."
        )
    latest = actual.latest_entry
    stale = latest is None or (at - dt.date.fromisoformat(latest)).days > STALE_AFTER_DAYS
    if stale:
        notes.insert(
            0,
            "Your ledger's newest entry is "
            + (f"from {latest}" if latest else "missing")
            + ": what happened is only what it shows, so bring it up to date before reading "
            "these differences.",
        )
    if actual.notes:
        notes.extend(actual.notes)

    others = [
        {
            "option": o["label"],
            **{name: _at(o["projection"], as_of, at)[name] for name in FIGURES},
        }
        for o in entry["options"]
        if o["label"] != chosen["label"]
    ]
    return {
        "option": chosen["label"],
        "at": at.isoformat(),
        "month": at.isoformat()[:7],
        "currency": currency,
        "terms": "nominal",
        "figures": rows,
        "spending": spending,
        "others": others,
        "baseline_fingerprint": actual.fingerprint,
        "data_as_of": latest,
        "is_stale": stale,
        "notes": list(dict.fromkeys(notes)),
    }
