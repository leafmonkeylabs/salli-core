"""
Signals: what in the user's finances needs their attention now.

Each detector looks at figures Salli has already computed (the forecast,
recurring payments, spending by month, cash flow, transactions waiting for
review) and says, plainly and with its evidence, when something stands out:
the cash running out before payday, a subscription that got dearer, a new
recurring charge, a category far above usual, the savings rate falling, a
review queue growing old. Nothing here advises; it points. Pure: no I/O.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from statistics import median
from typing import Literal

from salli.domain.reports.insights import MonthFlow, Recurring, SpendingLine

Severity = Literal["high", "medium", "info"]
SignalKind = Literal[
    "low_balance_ahead",
    "price_change",
    "new_recurring",
    "spending_spike",
    "savings_rate_drop",
    "review_waiting",
]
#: What the user can look at or do about it, for a client to link to.
Action = Literal["see_forecast", "see_recurring", "see_spending", "see_cash_flow", "review"]

_ORDER: dict[Severity, int] = {"high": 0, "medium": 1, "info": 2}


@dataclass(frozen=True)
class Signal:
    kind: SignalKind
    severity: Severity
    title: str
    detail: str
    action: Action
    #: The figure it is about, in `currency`, when there is one.
    amount: Decimal | None = None
    currency: str | None = None
    #: The day it is about (the low point, the charge), when there is one.
    date: str | None = None
    #: What it rests on: journal entry, transaction or account ids.
    refs: tuple[str, ...] = field(default_factory=tuple)


def low_balance_ahead(
    lowest: Decimal,
    lowest_date: str,
    today: Decimal,
    monthly_spending: Decimal | None,
    currency: str,
) -> list[Signal]:
    """Cash projected below zero (high), or below a tenth of a usual month's
    spending (medium), before the forecast's horizon."""
    if lowest < 0:
        return [
            Signal(
                "low_balance_ahead",
                "high",
                "Cash runs out before it comes back",
                f"Your cash is forecast to reach {lowest} {currency} on {lowest_date}.",
                "see_forecast",
                lowest,
                currency,
                lowest_date,
            )
        ]
    if (
        monthly_spending
        and monthly_spending > 0
        and lowest < monthly_spending / 10
        and lowest < today
    ):
        return [
            Signal(
                "low_balance_ahead",
                "medium",
                "Cash gets thin",
                f"Your cash is forecast to fall to {lowest} {currency} on {lowest_date}, "
                f"under a tenth of a usual month's spending ({monthly_spending} {currency}).",
                "see_forecast",
                lowest,
                currency,
                lowest_date,
            )
        ]
    return []


def price_changes(found: Sequence[Recurring]) -> list[Signal]:
    """A recurring payment whose latest charge differs from a steady run of
    the same amount before it."""
    signals: list[Signal] = []
    for r in found:
        before, latest = r.previous_amount, r.latest_amount
        if r.direction != "out" or not before or latest is None or latest == before:
            continue
        change = (latest - before) / before
        up = latest > before
        signals.append(
            Signal(
                "price_change",
                "medium" if up else "info",
                f"{r.payee} {'went up' if up else 'went down'}",
                f"{r.payee} charged {latest} {r.currency} on {r.last_date}, after "
                f"{before} {r.currency} before ({change:+.0%}).",
                "see_recurring",
                latest,
                r.currency,
                r.last_date,
                r.entry_ids[-1:],
            )
        )
    return signals


def new_recurring(
    found: Sequence[Recurring], tracked: Mapping[str, bool], today: dt.date, within_days: int = 100
) -> list[Signal]:
    """A recurring payment that began recently (its first charge within
    `within_days`) and that no declared subscription tracks yet. `tracked`
    is keyed by the series' first entry id."""
    signals: list[Signal] = []
    for r in found:
        if r.direction != "out" or not r.entry_ids or tracked.get(r.entry_ids[0], False):
            continue
        if not r.first_date:
            continue
        first = dt.date.fromisoformat(r.first_date)
        if (today - first).days > within_days:
            continue
        signals.append(
            Signal(
                "new_recurring",
                "info",
                f"New recurring payment: {r.payee}",
                f"{r.payee} has charged {r.typical_amount} {r.currency} {r.cadence} "
                f"{r.occurrences} times since {first.isoformat()}; next expected "
                f"{r.next_expected}.",
                "see_recurring",
                r.typical_amount,
                r.currency,
                r.next_expected,
                r.entry_ids,
            )
        )
    return signals


def spending_spikes(
    lines: Sequence[SpendingLine],
    months: Sequence[str],
    currency: str,
    floor: Decimal = Decimal(0),
) -> list[Signal]:
    """A category whose last full month was at least half again its usual
    (the median of the months before it), by more than `floor`."""
    if len(months) < 3:
        return []
    *before, last = months
    signals: list[Signal] = []
    for line in lines:
        usual = median(line.by_month.get(m, Decimal(0)) for m in before)
        spent = line.by_month.get(last, Decimal(0))
        if usual <= 0 or spent < usual * Decimal("1.5") or spent - usual <= floor:
            continue
        signals.append(
            Signal(
                "spending_spike",
                "medium",
                f"{line.key} was well above usual",
                f"You spent {spent} {currency} on {line.key} in {last}, against a usual "
                f"{usual} {currency} a month.",
                "see_spending",
                spent,
                currency,
                last,
            )
        )
    return signals


def savings_rate_drop(
    flows: Sequence[MonthFlow], points: Decimal = Decimal("0.15")
) -> list[Signal]:
    """The last full month's savings rate at least `points` below the median
    of the months before it."""
    rated = [f for f in flows if f.savings_rate is not None]
    if len(rated) < 3:
        return []
    *before, last = rated
    usual = median(f.savings_rate for f in before if f.savings_rate is not None)
    assert last.savings_rate is not None
    if usual - last.savings_rate < points:
        return []
    return [
        Signal(
            "savings_rate_drop",
            "medium",
            "You kept less than usual",
            f"You kept {last.savings_rate:.0%} of your income in {last.month}, against a "
            f"usual {usual:.0%}.",
            "see_cash_flow",
            date=last.month,
        )
    ]


def review_waiting(
    count: int, oldest: str | None, today: dt.date, stale_days: int = 7
) -> list[Signal]:
    """Transactions waiting for review: info, or medium once the oldest has
    waited longer than `stale_days`."""
    if count <= 0:
        return []
    waited = (today - dt.date.fromisoformat(oldest)).days if oldest else 0
    return [
        Signal(
            "review_waiting",
            "medium" if waited > stale_days else "info",
            f"{count} transaction{'s' if count != 1 else ''} to review",
            f"{count} imported transaction{'s are' if count != 1 else ' is'} waiting to be "
            "booked" + (f"; the oldest since {oldest}." if oldest else "."),
            "review",
            date=oldest,
        )
    ]


def ranked(signals: Sequence[Signal]) -> list[Signal]:
    """Most pressing first: by severity, then by date (soonest first)."""
    return sorted(signals, key=lambda s: (_ORDER[s.severity], s.date or "9999", s.title))
