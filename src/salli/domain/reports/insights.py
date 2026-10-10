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
from dataclasses import dataclass, field, replace
from decimal import Decimal
from statistics import median
from typing import Literal, get_args

from salli.domain.accounting.ledger import native_signed, owned_and_owed
from salli.domain.accounting.models import Account, StoredJournalEntry
from salli.domain.rules.engine import Direction, payee_name, payee_word
from salli.domain.rules.history import Booked

Cadence = Literal["weekly", "biweekly", "semimonthly", "monthly", "quarterly", "yearly"]
SpendingAxis = Literal["category", "account", "need"]
SPENDING_AXES: tuple[SpendingAxis, ...] = get_args(SpendingAxis)


@dataclass(frozen=True)
class CadenceSpec:
    """What a rhythm is, as data every reader of it (`add_period`,
    `detect_recurring`, the forecast) goes by.

    A day-of-month rhythm falls on the same days of the month: every
    `months` months on one anchor day (monthly, quarterly, yearly), or on two
    anchor days each month (semimonthly). A rhythm in days repeats every
    `days`, wherever that falls in the month (weekly, biweekly)."""

    #: "month_days": anchored to days of the month; "days": every `days` days.
    kind: Literal["month_days", "days"]
    #: The period in days (nominal for a day-of-month rhythm), and how far a
    #: gap may stray from it.
    days: int
    tolerance: int
    #: Months between occurrences of a one-anchor day-of-month rhythm.
    months: int = 0
    #: Anchor days a month: 1, or 2 for twice a month.
    anchors: int = 1


CADENCES: dict[Cadence, CadenceSpec] = {
    "weekly": CadenceSpec("days", 7, 2),
    # Every other week, drifting through the month: how many people in the
    # US are paid. Tight, so the 15th-and-last rhythm is not taken for it.
    "biweekly": CadenceSpec("days", 14, 1),
    # Twice a month on two set days (the 15th and the last, the 1st and the
    # 16th): the other common payroll.
    "semimonthly": CadenceSpec("month_days", 15, 3, months=0, anchors=2),
    "monthly": CadenceSpec("month_days", 30, 5, months=1),
    "quarterly": CadenceSpec("month_days", 91, 10, months=3),
    "yearly": CadenceSpec("month_days", 365, 15, months=12),
}

# The rhythms found by the gaps between charges; twice a month is found by
# the days of the month they fall on instead.
_BY_GAP: tuple[Cadence, ...] = ("monthly", "quarterly", "yearly", "weekly", "biweekly")


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
    #: Money out (a payment) or in (a salary), of `money_account_id`: the
    #: bank account or card it moves.
    direction: Direction = "out"
    money_account_id: str = ""
    #: The days of the month it falls on, for a day-of-month rhythm (one, or
    #: two for twice a month; 31 is the month's last day): a bill on the 31st
    #: is on the 30th in a short month, and the 31st again after it.
    anchor_days: tuple[int, ...] = ()
    #: The typical amount on `money_account_id`, in that account's currency
    #: (a USD salary into an LKR account, in rupees); None when it can't be
    #: known (no rate into the account's currency) or wasn't asked for.
    money_amount: Decimal | None = None
    #: The same for the other side, when it is another account of the
    #: user's in its own currency (a transfer); None otherwise.
    counter_amount: Decimal | None = None
    #: The amount it was charged steadily before the latest charge, when the
    #: latest differs from that steady run (a price change); None otherwise.
    #: In `currency`, like `typical_amount`.
    previous_amount: Decimal | None = None
    #: The latest charge's amount, in `currency`, and the first charge's day.
    latest_amount: Decimal | None = None
    first_date: str = ""


def _on(year: int, month: int, day: int) -> dt.date:
    """`day` of the month, kept to it (31 is its last day)."""
    total = month - 1
    year, month = year + total // 12, total % 12 + 1
    return dt.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _month_day(day: dt.date) -> int:
    """The day of the month, with its last day as 31."""
    return 31 if day.day == calendar.monthrange(day.year, day.month)[1] else day.day


def add_period(day: dt.date, cadence: Cadence, anchor_days: Sequence[int] = ()) -> dt.date:
    """The next date a `cadence` lands on after `day`.

    A rhythm in days adds its days. Twice a month is the next of its two
    anchor days. Monthly and longer move on by their months, to the anchor
    day (or `day`'s own), kept to that month."""
    spec = CADENCES[cadence]
    if spec.kind == "days":
        return day + dt.timedelta(days=spec.days)
    if spec.anchors == 2 and len(anchor_days) == 2:
        candidates = [
            _on(day.year, day.month + shift, anchor)
            for shift in (0, 1)
            for anchor in sorted(anchor_days)
        ]
        return min(c for c in candidates if c > day)
    wanted = anchor_days[0] if anchor_days else day.day
    return _on(day.year, day.month + spec.months, wanted)


def next_due(last: dt.date, cadence: Cadence, anchor_days: Sequence[int] = ()) -> dt.date:
    """When the occurrence after `last` is due.

    On a monthly or longer rhythm with an anchor day, the anchor-day date
    nearest a period after `last`: a charge that slipped across a month's
    end (paid 30 October for 1 November, rent paid 1 October for
    30 September) is still followed by the next one on its anchor day, not a
    month off."""
    spec = CADENCES[cadence]
    if spec.kind == "days" or spec.anchors != 1 or not anchor_days:
        return add_period(last, cadence, anchor_days)
    target = add_period(last, cadence)  # a whole period on
    candidates = [_on(target.year, target.month + shift, anchor_days[0]) for shift in (-1, 0, 1)]
    return min(candidates, key=lambda c: (abs((c - target).days), c))


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


def detect_recurring(
    booked: Sequence[Booked],
    today: dt.date,
    direction: Direction | None = "out",
    *,
    currencies: Mapping[str, str] | None = None,
    base: str = "",
) -> list[Recurring]:
    """Money to or from one payee, at least three times, at a regular rhythm,
    and still going: one more than a quarter of a period overdue has stopped.

    Payments out by default; `direction="in"` finds income (a salary), and
    None both. A payee's charges at clearly different amounts are looked at
    apart first (two subscriptions from one merchant); if none of those has a
    rhythm, all of them together (a price that changed).

    With `currencies` (account id → its currency) and the `base` currency,
    each series also says its typical amount in its accounts' own currencies
    (`money_amount`, `counter_amount`)."""
    groups: dict[tuple[str, str, Direction], list[Booked]] = defaultdict(list)
    for b in booked:
        if direction is not None and b.facts.direction != direction:
            continue
        word = payee_word(b.facts.description)
        if word:
            groups[(word, b.facts.currency, b.facts.direction)].append(b)

    found: list[Recurring] = []
    for (word, currency, moved), rows in groups.items():
        clusters = _amount_clusters(rows)
        series = (
            [r for c in clusters if (r := _series(word, currency, moved, c, today))]
            if len(clusters) > 1
            else []
        )
        if not series:
            whole = _series(word, currency, moved, rows, today)
            series = [whole] if whole else []
        if currencies is not None:
            series = [_in_account_currencies(r, rows, currencies, base) for r in series]
        found.extend(series)
    found.sort(key=lambda r: (r.next_expected, r.payee))
    return found


def _twice_a_month(days: list[dt.date], amounts: list[Decimal]) -> tuple[int, int] | None:
    """The two anchor days of charges that fall twice a month on set days (the
    15th and the last, the 1st and the 16th), at a fixed amount; or None.

    Groceries bought on the 1st and 16th at varying amounts are not a rhythm
    to plan by; a salary on the 15th and the last is."""
    if len(days) < 4:
        return None
    gaps = {(b - a).days for a, b in zip(days, days[1:], strict=False)}
    if len(gaps) == 1:
        return None  # one fixed gap (every 14 days): a rhythm in days, drifting
    typical = median(amounts)
    if any(abs(a - typical) > typical * Decimal("0.10") for a in amounts):
        return None
    marks = sorted(_month_day(d) for d in days)
    # Split where the days of the month jump most: two tight groups, apart.
    split = max(range(1, len(marks)), key=lambda i: marks[i] - marks[i - 1])
    low, high = marks[:split], marks[split:]
    if max(low) - min(low) > 3 or max(high) - min(high) > 3 or min(high) - max(low) < 10:
        return None
    # Each month from the first to the last has one of each.
    months: dict[tuple[int, int], list[int]] = defaultdict(list)
    for d in days:
        months[(d.year, d.month)].append(_month_day(d))
    spanned = (days[-1].year - days[0].year) * 12 + days[-1].month - days[0].month + 1
    both = sum(
        1
        for marked in months.values()
        if any(m <= max(low) for m in marked) and any(m >= min(high) for m in marked)
    )
    if both < max(2, (spanned - 1) * 3 // 4):
        return None
    common = Counter(marks)
    return (
        max(low, key=lambda m: (common[m], m)),
        max(high, key=lambda m: (common[m], m)),
    )


def _series(
    word: str, currency: str, moved: Direction, rows: list[Booked], today: dt.date
) -> Recurring | None:
    """One payee's charges as a recurring payment, or None if they have no
    regular rhythm, are fewer than three, or have stopped.

    Days of the month first: twice a month on two set days, or monthly and
    longer on one. A rhythm in days (weekly, biweekly) only when the day of
    the month drifts."""
    rows = sorted(rows, key=lambda b: b.entry.entry_date)
    days = [dt.date.fromisoformat(b.entry.entry_date) for b in rows]
    if len(set(days)) < 3:
        return None
    amounts = [b.facts.amount for b in rows]
    anchors: tuple[int, ...] = ()
    twice = _twice_a_month(days, amounts)
    if twice is not None:
        cadence: Cadence = "semimonthly"
        anchors = twice
    else:
        gaps = [(b - a).days for a, b in zip(days, days[1:], strict=False) if (b - a).days > 0]
        if not gaps:
            return None
        typical_gap = median(gaps)
        rhythm: Cadence | None = next(
            (c for c in _BY_GAP if abs(typical_gap - CADENCES[c].days) <= CADENCES[c].tolerance),
            None,
        )
        if rhythm is None:
            return None
        spec = CADENCES[rhythm]
        regular = sum(1 for g in gaps if abs(g - spec.days) <= spec.tolerance)
        if regular / len(gaps) < 0.75:
            return None
        cadence = rhythm
        if spec.kind == "month_days":
            marks = Counter(d.day for d in days)
            anchors = (max(marks, key=lambda d: (marks[d], d)),)
    spec = CADENCES[cadence]
    if (today - days[-1]).days > spec.days + max(spec.tolerance, spec.days // 4):
        return None  # it stopped
    typical = median(amounts)
    varies = any(abs(a - typical) > typical * Decimal("0.10") for a in amounts)
    accounts = Counter(b.counter_account_id for b in rows)
    money_accounts = Counter(b.money_account_id for b in rows)
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
        next_expected=next_due(days[-1], cadence, anchors).isoformat(),
        examples=tuple(dict.fromkeys(b.facts.description for b in rows))[:3],
        entry_ids=tuple(b.entry.id for b in rows),
        direction=moved,
        money_account_id=max(money_accounts, key=lambda k: (money_accounts[k], k)),
        anchor_days=anchors,
        previous_amount=_previous_amount(amounts),
        latest_amount=amounts[-1],
        first_date=days[0].isoformat(),
    )


def _previous_amount(amounts: list[Decimal]) -> Decimal | None:
    """The steady amount before the last charge, when the last one differs
    from at least two equal charges before it."""
    *earlier, last = amounts
    if len(earlier) >= 2 and len(set(earlier)) == 1 and last != earlier[0]:
        return earlier[0]
    return None


def _in_account_currencies(
    r: Recurring, rows: list[Booked], currencies: Mapping[str, str], base: str
) -> Recurring:
    """`r` with its typical amount on each side in that side's account
    currency, from the postings themselves (`ledger.native_signed`)."""
    mine = [b for b in rows if b.entry.id in set(r.entry_ids)]

    def typical_on(account_id: str) -> Decimal | None:
        currency = currencies.get(account_id)
        if currency is None:
            return None
        values: list[Decimal] = []
        for b in mine:
            posting = next((p for p in b.entry.postings if p.account_id == account_id), None)
            native = native_signed(posting, currency, base) if posting is not None else None
            if native is None:
                return None
            values.append(abs(native))
        return median(values) if values else None

    return replace(
        r,
        money_amount=typical_on(r.money_account_id),
        counter_amount=typical_on(r.account_id) if r.account_id != r.money_account_id else None,
    )
