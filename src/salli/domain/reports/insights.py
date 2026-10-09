"""
Insights: where the money goes, month by month, and what keeps coming back.

Everything here is computed from the ledger in the base currency, netting
signed amounts so a reversing entry cancels the one it reverses. Pure: no I/O.

- cash flow: income, spending, what is left, and the savings rate, per month;
- spending: by category tag (falling back to the account), account or need,
  with each month's figure;
- net worth: the book value of everything owned less everything owed, at
  each month's end;
- recurring payments: charges from one payee at a regular rhythm — what
  subscriptions look like before anyone has written them down.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from statistics import median
from typing import Literal, get_args

from salli.domain.accounting.ledger import owned_and_owed
from salli.domain.accounting.models import Account, StoredJournalEntry
from salli.domain.rules.engine import payee_name, payee_word
from salli.domain.rules.history import Booked

Cadence = Literal["weekly", "monthly", "quarterly", "yearly"]
SpendingAxis = Literal["category", "account", "need"]
SPENDING_AXES: tuple[SpendingAxis, ...] = get_args(SpendingAxis)

# (cadence, period in days, tolerance in days)
_CADENCES: tuple[tuple[Cadence, int, int], ...] = (
    ("weekly", 7, 2),
    ("monthly", 30, 5),
    ("quarterly", 91, 10),
    ("yearly", 365, 15),
)


def month_of(day: str) -> str:
    return day[:7]


def last_months(end: dt.date, count: int) -> list[str]:
    """The `count` calendar months ending with `end`'s, oldest first ("YYYY-MM")."""
    year, month = end.year, end.month
    months: list[str] = []
    for _ in range(count):
        months.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return months[::-1]


def _types(accounts: Iterable[Account]) -> dict[str, Account]:
    return {a.id: a for a in accounts}


@dataclass(frozen=True)
class MonthFlow:
    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    #: Share of income kept (net / income); None when there was no income.
    savings_rate: Decimal | None


def cash_flow(
    entries: Sequence[StoredJournalEntry], accounts: Sequence[Account], months: Sequence[str]
) -> list[MonthFlow]:
    by_id = _types(accounts)
    income: dict[str, Decimal] = defaultdict(Decimal)
    expenses: dict[str, Decimal] = defaultdict(Decimal)
    wanted = set(months)
    for entry in entries:
        month = month_of(entry.entry_date)
        if month not in wanted:
            continue
        for p in entry.postings:
            account = by_id.get(p.account_id)
            if account is None:
                continue
            if account.type == "income":
                income[month] -= p.base_signed  # credits raise income
            elif account.type == "expense":
                expenses[month] += p.base_signed
    flows: list[MonthFlow] = []
    for month in months:
        net = income[month] - expenses[month]
        rate = (net / income[month]) if income[month] > 0 else None
        flows.append(MonthFlow(month, income[month], expenses[month], net, rate))
    return flows


@dataclass(frozen=True)
class SpendingLine:
    key: str
    total: Decimal
    by_month: dict[str, Decimal]
    #: Its share of all spending in the period (0..1), over the lines that
    #: spent; None for a line that netted to money back (refunds only).
    share: Decimal | None


def spending(
    entries: Sequence[StoredJournalEntry],
    accounts: Sequence[Account],
    months: Sequence[str],
    by: SpendingAxis = "category",
) -> list[SpendingLine]:
    by_id = _types(accounts)
    wanted = set(months)
    totals: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for entry in entries:
        month = month_of(entry.entry_date)
        if month not in wanted:
            continue
        for p in entry.postings:
            account = by_id.get(p.account_id)
            if account is None or account.type != "expense":
                continue
            if by == "account":
                key = account.name
            elif by == "need":
                key = p.tags.get("need") or "unclassified"
            else:
                key = p.tags.get("category") or account.name
            totals[key][month] += p.base_signed
    sums = {key: sum(per_month.values(), Decimal(0)) for key, per_month in totals.items()}
    # Shares of what was spent: a line of refunds alone would push the others
    # past 100% and itself below zero.
    spent = sum((total for total in sums.values() if total > 0), Decimal(0))
    lines = [
        SpendingLine(
            key=key,
            total=sums[key],
            by_month={m: per_month.get(m, Decimal(0)) for m in months},
            share=(sums[key] / spent) if sums[key] > 0 and spent else None,
        )
        for key, per_month in totals.items()
    ]
    lines.sort(key=lambda line: (-line.total, line.key))
    return [line for line in lines if line.total != 0]


@dataclass(frozen=True)
class NetWorthPoint:
    month: str
    assets: Decimal
    liabilities: Decimal
    net_worth: Decimal


def net_worth_series(
    entries: Sequence[StoredJournalEntry],
    accounts: Sequence[Account],
    months: Sequence[str],
    opening: Mapping[str, Decimal] | None = None,
) -> list[NetWorthPoint]:
    """Book value at each month's end, judged per account on its own sign
    (`ledger.owned_and_owed`, as FiService does): an overdrawn bank account
    counts as owed, not as a smaller asset. Every account counts, closed ones
    too: a deactivated account with a balance is still owned or owed.

    `opening` is each account's balance before `entries` begin, when they
    are only the window's: the sum of everything earlier."""
    by_id = _types(accounts)
    balances: dict[str, Decimal] = defaultdict(Decimal, opening or {})
    ordered = sorted(entries, key=lambda e: e.entry_date)
    points: list[NetWorthPoint] = []
    i = 0
    for month in months:
        while i < len(ordered) and month_of(ordered[i].entry_date) <= month:
            for p in ordered[i].postings:
                balances[p.account_id] += p.base_signed
            i += 1
        assets = Decimal(0)
        liabilities = Decimal(0)
        for account_id, balance in balances.items():
            account = by_id.get(account_id)
            if account is None:
                continue
            owned, owed = owned_and_owed(account.type, balance)
            assets += owned
            liabilities += owed
        points.append(NetWorthPoint(month, assets, liabilities, assets - liabilities))
    return points


@dataclass(frozen=True)
class Recurring:
    #: Who is paid, to show ("City Power"), and the one word the charges were
    #: grouped by ("city").
    payee: str
    key: str
    cadence: Cadence
    #: The middle amount; `varies` when charges differ by more than 10%.
    typical_amount: Decimal
    varies: bool
    currency: str
    #: Where these charges were booked.
    account_id: str
    occurrences: int
    last_date: str
    next_expected: str
    examples: tuple[str, ...] = field(default_factory=tuple)
    #: The journal entries the charges were booked as.
    entry_ids: tuple[str, ...] = field(default_factory=tuple)


def _add_period(day: dt.date, cadence: Cadence) -> dt.date:
    if cadence == "weekly":
        return day + dt.timedelta(days=7)
    months = {"monthly": 1, "quarterly": 3, "yearly": 12}[cadence]
    total = day.month - 1 + months
    year, month = day.year + total // 12, total % 12 + 1
    return dt.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _amount_clusters(rows: list[Booked]) -> list[list[Booked]]:
    """A payee's charges split where their amounts jump by more than 15%
    (sorted, single-linkage): APPLE.COM/BILL at 2.99 and at 10.99 are two
    subscriptions, while a bill drifting from 80 to 120 stays one."""
    ordered = sorted(rows, key=lambda b: b.facts.amount)
    clusters: list[list[Booked]] = [[ordered[0]]] if ordered else []
    for previous, b in zip(ordered, ordered[1:], strict=False):
        if b.facts.amount > previous.facts.amount * _CLUSTER_STEP:
            clusters.append([])
        clusters[-1].append(b)
    return clusters


# How far apart two amounts may be and still be one subscription's.
_CLUSTER_STEP = Decimal("1.15")


def detect_recurring(booked: Sequence[Booked], today: dt.date) -> list[Recurring]:
    """Payments out to one payee, at least three, at a regular rhythm, and
    still going: one more than a quarter of a period overdue has stopped.

    A payee's charges at clearly different amounts are looked at apart first
    (two subscriptions from one merchant); if none of those has a rhythm,
    all of them together (a price that changed)."""
    groups: dict[tuple[str, str], list[Booked]] = defaultdict(list)
    for b in booked:
        if b.facts.direction != "out":
            continue
        word = payee_word(b.facts.description)
        if word:
            groups[(word, b.facts.currency)].append(b)

    found: list[Recurring] = []
    for (word, currency), rows in groups.items():
        clusters = _amount_clusters(rows)
        series = (
            [r for c in clusters if (r := _series(word, currency, c, today))]
            if (len(clusters) > 1)
            else []
        )
        if not series:
            whole = _series(word, currency, rows, today)
            series = [whole] if whole else []
        found.extend(series)
    found.sort(key=lambda r: (r.next_expected, r.payee))
    return found


def _series(word: str, currency: str, rows: list[Booked], today: dt.date) -> Recurring | None:
    """One payee's charges as a recurring payment, or None if they have no
    regular rhythm, are fewer than three, or have stopped."""
    rows = sorted(rows, key=lambda b: b.entry.entry_date)
    days = [dt.date.fromisoformat(b.entry.entry_date) for b in rows]
    if len(set(days)) < 3:
        return None
    gaps = [(b - a).days for a, b in zip(days, days[1:], strict=False) if (b - a).days > 0]
    if not gaps:
        return None
    typical_gap = median(gaps)
    rhythm = next(
        (c for c in _CADENCES if abs(typical_gap - c[1]) <= c[2]),
        None,
    )
    if rhythm is None:
        return None
    cadence, period, tolerance = rhythm
    regular = sum(1 for g in gaps if abs(g - period) <= tolerance)
    if regular / len(gaps) < 0.75:
        return None
    if (today - days[-1]).days > period + max(tolerance, period // 4):
        return None  # it stopped
    amounts = [b.facts.amount for b in rows]
    typical = median(amounts)
    varies = any(abs(a - typical) > typical * Decimal("0.10") for a in amounts)
    accounts = Counter(b.counter_account_id for b in rows)
    names = Counter(payee_name(b.facts.description) for b in rows)
    return Recurring(
        # The way it is most often written; of those, the shortest.
        payee=min(names, key=lambda n: (-names[n], len(n), n)) or word.title(),
        key=word,
        cadence=cadence,
        typical_amount=typical,
        varies=varies,
        currency=currency,
        account_id=max(accounts, key=lambda k: (accounts[k], k)),
        occurrences=len(rows),
        last_date=days[-1].isoformat(),
        next_expected=_add_period(days[-1], cadence).isoformat(),
        examples=tuple(dict.fromkeys(b.facts.description for b in rows))[:3],
        entry_ids=tuple(b.entry.id for b in rows),
    )
