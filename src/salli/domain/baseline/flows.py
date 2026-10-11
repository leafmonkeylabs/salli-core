"""
Income and expenses, under one definition.

Signed amounts on income and expense accounts, in the base currency at the
rate each posting recorded, netted per calendar month: a reversal cancels
what it reverses, a refund cancels a purchase. The averages are over the full
calendar months observed: at most twelve, before the as-of month (a month
half over would understate it), and none before the month the user's record
of money in and out begins (a new user's three months are averaged over
three, not twelve). A ledger begun part-way through a month counts that
month.

Insights' monthly cash flow is the same netting (`insights.cash_flow`), so
the months it shows and the averages FI uses always agree.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from decimal import Decimal

from salli.domain.accounting.models import Account, StoredJournalEntry
from salli.domain.baseline.models import MONTHS_OBSERVED, Flows, MonthFlow
from salli.domain.reports import insights


def observed_months(
    as_of: dt.date, first_flow: str | None, cap: int = MONTHS_OBSERVED
) -> list[str]:
    """The full calendar months ("YYYY-MM") averaged over, oldest first: the
    `cap` months before `as_of`'s, from the month of `first_flow` on."""
    if first_flow is None:
        return []
    start = insights.month_of(first_flow)
    before = insights.last_months(as_of, cap + 1)[:-1]
    return [m for m in before if m >= start]


def monthly(
    entries: Sequence[StoredJournalEntry], accounts: Sequence[Account], months: Sequence[str]
) -> list[MonthFlow]:
    """Each month's income, expenses and essential spending, netted."""
    cash_flow = insights.cash_flow(entries, accounts, months)
    lines = insights.spending(entries, accounts, months, by="need")
    essential = next((line for line in lines if line.key == "essential"), None)
    classified = [line for line in lines if line.key != "unclassified"]
    return [
        MonthFlow(
            month=f.month,
            income=f.income,
            expenses=f.expenses,
            net=f.net,
            essential=essential.by_month.get(f.month, Decimal(0)) if essential else Decimal(0),
            classified=sum(
                (line.by_month.get(f.month, Decimal(0)) for line in classified), Decimal(0)
            ),
        )
        for f in cash_flow
    ]


def summarize(
    entries: Sequence[StoredJournalEntry],
    accounts: Sequence[Account],
    as_of: dt.date,
    first_flow: str | None,
    cap: int = MONTHS_OBSERVED,
) -> Flows:
    """The months observed, each month's figures, and their averages."""
    months = observed_months(as_of, first_flow, cap)
    rows = monthly(entries, accounts, months)
    n = Decimal(len(rows))
    if not rows:
        zero = Decimal(0)
        return Flows((), (), zero, zero, zero, None, None, None)

    income = sum((r.income for r in rows), Decimal(0)) / n
    expenses = sum((r.expenses for r in rows), Decimal(0)) / n
    surplus = income - expenses
    total_spent = sum((r.expenses for r in rows), Decimal(0))
    classified = sum((r.classified for r in rows), Decimal(0))
    tagged = any(r.classified != 0 for r in rows)
    return Flows(
        months=tuple(months),
        by_month=tuple(rows),
        income=income,
        expenses=expenses,
        surplus=surplus,
        savings_rate=(surplus / income) if income > 0 else None,
        essential=(sum((r.essential for r in rows), Decimal(0)) / n) if tagged else None,
        need_coverage=(classified / total_spent) if total_spent > 0 else None,
    )
