"""
Signals: what in the user's finances needs their attention now.

Each detector looks at figures Salli has already computed (the forecast,
recurring payments, spending by month, cash flow, transactions waiting for
review) and says, plainly and with its evidence, when something stands out:
the cash running out before payday, a subscription that got dearer, a new
recurring charge, a category far above usual, the savings rate falling, a
review queue growing old, a decision whose review date has come, cash and
savings covering fewer months than the FI method's emergency target, a debt
charging more than the method's line. Nothing
here advises; it points. Pure: no I/O.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from statistics import median
from typing import Literal

from salli.domain.budget.monthly import CurrentLine
from salli.domain.currency import quantize
from salli.domain.fi.assumptions import PLACEHOLDERS
from salli.domain.reports.insights import MonthFlow, Recurring, SpendingLine

Severity = Literal["high", "medium", "low", "info"]
SignalKind = Literal[
    "low_balance_ahead",
    "price_change",
    "new_recurring",
    "spending_spike",
    "savings_rate_drop",
    "review_waiting",
    "decision_review_due",
    "emergency_fund_low",
    "expensive_debt",
    "budget_over",
    "budget_pace",
]
#: What the user can look at or do about it, for a client to link to.
Action = Literal[
    "see_forecast",
    "see_recurring",
    "see_spending",
    "see_cash_flow",
    "see_debts",
    "review",
    "review_decision",
    "see_budget",
]

#: The yearly rate at or above which a debt is described as costly: the
#: placeholder real return plus a margin. Part of the method, not any
#: country's figure.
EXPENSIVE_DEBT_RATE = PLACEHOLDERS["real_return"].value + Decimal("0.04")

_ORDER: dict[Severity, int] = {"high": 0, "medium": 1, "low": 2, "info": 3}


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
    #: Why Salli says so (the method and its line), apart from the plain
    #: words of `detail`; None when the detail says it all.
    rationale: str | None = None


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


def budget_lines(lines: Sequence[CurrentLine], currency: str) -> list[Signal]:
    """The monthly budget this month: a line spent past what is available
    (`budget_over`, medium), or past the share of it matching the share of
    the month gone (`budget_pace`, low)."""

    def q(amount: Decimal) -> Decimal:
        return quantize(amount, currency, strict=False)

    found: list[Signal] = []
    for line in lines:
        if line.left < 0:
            found.append(
                Signal(
                    "budget_over",
                    "medium",
                    f"{line.category} is over its budget this month",
                    f"{q(line.spent)} {currency} spent of {q(line.available)} {currency} available.",
                    "see_budget",
                    -line.left,
                    currency,
                    refs=(line.account_id,),
                )
            )
        elif line.pace == "over":
            found.append(
                Signal(
                    "budget_pace",
                    "low",
                    f"{line.category} is running faster than its budget",
                    f"{q(line.spent)} {currency} spent of {q(line.available)} {currency}; at an "
                    f"even pace it would be {q(line.expected_by_now)} {currency} by now.",
                    "see_budget",
                    line.spent,
                    currency,
                    refs=(line.account_id,),
                    rationale="Spending against the share of the month gone, today included.",
                )
            )
    return found


def decision_reviews_due(due: Sequence[tuple[str, str, str]]) -> list[Signal]:
    """A decision in the journal whose review date has come and that has no
    review yet: (id, question, review date) each. Info: a review is an
    invitation, never urgent."""
    return [
        Signal(
            "decision_review_due",
            "info",
            "A decision is ready for review",
            f'You decided "{" ".join(question.split())}" and asked to look back on '
            f"{review_on}: see how it turned out against what Salli projected.",
            "review_decision",
            date=review_on,
            refs=(decision_id,),
        )
        for decision_id, question, review_on in due
    ]


def emergency_fund_low(
    liquid: Decimal,
    monthly_spending: Decimal,
    target_months: int,
    full_months: int,
    currency: str,
) -> list[Signal]:
    """Cash and savings covering fewer than `target_months` of average
    spending (the FI method's emergency target), once a full month of
    spending has been seen. Graded: high under one month, medium under
    three, low under the target; nothing at it."""
    if full_months < 1 or monthly_spending <= 0 or target_months <= 0:
        return []
    covered = liquid / monthly_spending
    if covered >= target_months:
        return []
    severity: Severity = "high" if covered < 1 else "medium" if covered < 3 else "low"
    return [
        Signal(
            "emergency_fund_low",
            severity,
            "Your savings would not last long",
            f"If your income stopped, your cash and savings ({liquid} {currency}) would pay "
            f"for about {max(covered, Decimal(0)):.1f} months of your usual spending "
            f"({monthly_spending} {currency} a month).",
            "see_cash_flow",
            liquid,
            currency,
            rationale=(
                f"The FI method's emergency fund target is {target_months} months of average "
                "spending: high under one month, medium under three, low under the target."
            ),
        )
    ]


def expensive_debts(
    debts: Sequence[tuple[str, str, Decimal, Decimal]], currency: str
) -> list[Signal]:
    """A declared debt whose yearly rate is at or above `EXPENSIVE_DEBT_RATE`:
    (id, name, rate, balance) each, the balance in `currency`."""
    return [
        Signal(
            "expensive_debt",
            "medium",
            f"{name} costs a lot to borrow",
            f"You owe {balance} {currency} on {name}, and it adds {rate:.1%} of that in "
            "interest each year.",
            "see_debts",
            balance,
            currency,
            refs=(debt_id,),
            rationale=(
                f"Salli calls a debt costly at {EXPENSIVE_DEBT_RATE:.0%} a year or more: the "
                "placeholder real return plus a 4% margin, not any country's figure."
            ),
        )
        for debt_id, name, rate, balance in debts
        if rate >= EXPENSIVE_DEBT_RATE and balance > 0
    ]


def ranked(signals: Sequence[Signal]) -> list[Signal]:
    """Most pressing first: by severity, then by date (soonest first)."""
    return sorted(signals, key=lambda s: (_ORDER[s.severity], s.date or "9999", s.title))
