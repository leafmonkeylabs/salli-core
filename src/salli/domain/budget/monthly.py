"""
The monthly budget: a limit per expense account that recurs every calendar
month, optionally rolling over (what is left of a month carries to the next;
an overspend carries nothing). Pure: entries and accounts in, figures out.

Spending is an expense account's net in the base currency over the month
(debits less credits), so a reversal or a recategorised entry nets out.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from salli.domain.reports.insights import last_months

#: How many months back a rollover is carried from, at most.
CARRY_MONTHS = 12


@dataclass(frozen=True)
class MonthlyLine:
    """A recurring limit on one expense account, from the month it was set."""

    account_id: str
    limit: Decimal
    rollover: bool
    #: The first month it applies to ("YYYY-MM").
    since: str


@dataclass(frozen=True)
class CurrentLine:
    account_id: str
    category: str
    limit: Decimal
    #: Carried from the months before (rollover only; never below zero).
    carried: Decimal
    #: limit + carried.
    available: Decimal
    spent: Decimal
    #: available - spent: negative means over.
    left: Decimal
    #: The share of `available` matching the share of the month gone.
    expected_by_now: Decimal
    #: "over" when spent is more than expected by now, else "within".
    pace: Literal["over", "within"]


def month_of(day: dt.date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def month_gone(today: dt.date) -> Decimal:
    """The share of `today`'s month gone, today included."""
    days = calendar.monthrange(today.year, today.month)[1]
    return Decimal(today.day) / Decimal(days)


def spend_by_month(
    entries: Iterable[Any], accounts: Iterable[Any]
) -> dict[tuple[str, str], Decimal]:
    """(account id, "YYYY-MM") -> the expense account's net in the base
    currency that month."""
    expense = {a.id for a in accounts if a.type == "expense"}
    spent: dict[tuple[str, str], Decimal] = {}
    for entry in entries:
        month = str(entry.entry_date)[:7]
        for p in entry.postings:
            if p.account_id in expense:
                key = (p.account_id, month)
                spent[key] = spent.get(key, Decimal(0)) + p.base_signed
    return spent


def carried(line: MonthlyLine, spent: dict[tuple[str, str], Decimal], month: str) -> Decimal:
    """What rolls into `month` from the line's months before it."""
    if not line.rollover:
        return Decimal(0)
    end = dt.date.fromisoformat(f"{month}-01")
    carry = Decimal(0)
    for m in last_months(end, CARRY_MONTHS + 1)[:-1]:
        if m < line.since:
            continue
        carry = max(Decimal(0), line.limit + carry - spent.get((line.account_id, m), Decimal(0)))
    return carry


def current(
    lines: Sequence[MonthlyLine],
    spent: dict[tuple[str, str], Decimal],
    names: dict[str, str],
    today: dt.date,
) -> list[CurrentLine]:
    """Each line for `today`'s month: limit, carried, spent, left and pace."""
    month = month_of(today)
    gone = month_gone(today)
    out: list[CurrentLine] = []
    for line in lines:
        carry = carried(line, spent, month)
        available = line.limit + carry
        used = spent.get((line.account_id, month), Decimal(0))
        expected = available * gone
        out.append(
            CurrentLine(
                account_id=line.account_id,
                category=names.get(line.account_id, line.account_id),
                limit=line.limit,
                carried=carry,
                available=available,
                spent=used,
                left=available - used,
                expected_by_now=expected,
                pace="over" if used > expected else "within",
            )
        )
    return out


def trend(spent: dict[tuple[str, str], Decimal], months: Sequence[str]) -> dict[str, list[Decimal]]:
    """Account id -> its spending in each of `months`, for every expense
    account with any in them."""
    ids = sorted({a for a, m in spent if m in months})
    return {a: [spent.get((a, m), Decimal(0)) for m in months] for a in ids}
