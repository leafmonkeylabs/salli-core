"""
Cash-flow forecast: where the money in the user's cash accounts is heading.

From today's balances, day by day to a horizon, applying what the ledger says
keeps happening (insights.detect_recurring: the salary, the rent, the
subscriptions it has seen) and the subscriptions the user declared that it
has not seen yet. Pure: no I/O, and nothing here guesses beyond those rhythms.

- Cash accounts are the ones money is spent from (`cash_accounts`): not a
  house, a pension fund or a loan whose only movements are an opening
  balance, contributions or interest.
- A transfer between two cash accounts (rent from checking to the card,
  savings to checking) moves both, each in its own currency, so the total
  does not change but by the exchange.
- A charge a little overdue is expected today, not skipped: for planning,
  late is not never. Only that one moves; the rest keep their schedule.
- A declared subscription with no history has no account to say which cash
  account pays it, so it moves the total only.
- Amounts in an account's own currency; the total in the base currency, at
  the rate the caller gives for each currency.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from salli.domain.accounting.models import Account
from salli.domain.reports.insights import CADENCES, Cadence, Recurring, add_period
from salli.domain.rules.history import Booked

FlowSource = Literal["recurring", "subscription"]


@dataclass(frozen=True)
class Flow:
    date: str
    #: The cash account it moves; None for a declared subscription the ledger
    #: has not shown, which moves only the total.
    account_id: str | None
    #: Signed: money in is positive.
    amount: Decimal
    currency: str
    description: str
    source: FlowSource


@dataclass(frozen=True)
class DeclaredCharge:
    """A subscription the user declared, in the base currency."""

    name: str
    amount: Decimal
    cadence: Cadence
    next_due: dt.date


@dataclass(frozen=True)
class AccountOutlook:
    account_id: str
    currency: str
    today: Decimal
    end: Decimal
    lowest: Decimal
    lowest_date: str


@dataclass(frozen=True)
class Forecast:
    start: str
    end: str
    #: Cash today, at the horizon and at its lowest, in the base currency.
    today: Decimal
    end_balance: Decimal
    lowest: Decimal
    lowest_date: str
    #: The total at the end of each day, from today to the horizon.
    daily: list[tuple[str, Decimal]] = field(default_factory=list[tuple[str, Decimal]])
    accounts: list[AccountOutlook] = field(default_factory=list[AccountOutlook])
    flows: list[Flow] = field(default_factory=list[Flow])


def cash_accounts(
    booked: Sequence[Booked],
    accounts: Sequence[Account],
    since: str,
    statement_accounts: Collection[str] = frozenset(),
) -> dict[str, str]:
    """The accounts money is spent from (account id → its currency): what a
    cash forecast is about.

    An account a statement or bank feed is imported into is one. Otherwise,
    from what was booked since `since` (opening balances, which are booked
    against equity, and the system's own entries left out), one that paid
    an expense: an asset (a bank or cash account) that did at all, a
    liability that paid several (a card, not a loan accruing its interest).
    A pension fund that only ever receives contributions, a house, and a
    loan are not cash, though money moved on them."""
    by_id = {a.id: a for a in accounts}
    spent: dict[str, set[str]] = defaultdict(set)  # money account -> expense accounts paid
    for b in booked:
        if b.entry.entry_date < since or b.entry.source == "system":
            continue
        counter = by_id.get(b.counter_account_id)
        if counter is None or counter.type != "expense" or b.facts.direction != "out":
            continue
        spent[b.money_account_id].add(counter.id)
    cash: dict[str, str] = {}
    for a in accounts:
        if not a.is_active or a.type not in ("asset", "liability"):
            continue
        paid = spent.get(a.id, set())
        if (
            a.id in statement_accounts
            or (a.type == "asset" and paid)
            or (a.type == "liability" and len(paid) >= 2)
        ):
            cash[a.id] = a.currency
    return cash


def schedule(
    first: dt.date,
    cadence: Cadence,
    anchor_days: Sequence[int],
    start: dt.date,
    end: dt.date,
) -> list[dt.date]:
    """The dates from `first` on, to `end`, that a rhythm lands on. If the
    first is already past (`start` is today), it is expected today — late is
    not never — and only it: the later ones keep their own dates."""
    dates: list[dt.date] = []
    day = first
    while day <= end:
        if day >= start:
            dates.append(day)
        elif not dates:
            dates.append(start)
        day = add_period(day, cadence, anchor_days)
    return list(dict.fromkeys(dates))  # a late one moved to a day already due


def recurring_flows(
    found: Sequence[Recurring],
    cash: Mapping[str, str],
    start: dt.date,
    end: dt.date,
    notes: list[str] | None = None,
) -> list[Flow]:
    """Every occurrence from `start` to `end` of what keeps happening on a cash
    account. `cash` is account id → its currency.

    Each side moves by its typical amount in its own account's currency
    (`Recurring.money_amount`, `counter_amount`): a USD salary into a rupee
    account in rupees. A side whose amount can't be known in its account's
    currency is left out, and said in `notes`."""
    flows: list[Flow] = []
    for r in found:
        currency = cash.get(r.money_account_id)
        if currency is None:
            continue
        amount = r.money_amount
        if amount is None and r.currency == currency:
            amount = r.typical_amount  # asked without the accounts' currencies
        if amount is None:
            if notes is not None:
                notes.append(f"{r.payee}: its amount in {currency} can't be known; left out")
            continue
        sign = Decimal(1) if r.direction == "in" else Decimal(-1)
        # Into or out of another cash account: a transfer, which moves that
        # account the other way, in its own currency.
        other = cash.get(r.account_id) if r.account_id != r.money_account_id else None
        other_amount = r.counter_amount
        if other is not None and other_amount is None and other == r.currency:
            other_amount = r.typical_amount
        if other is not None and other_amount is None and notes is not None:
            notes.append(f"{r.payee}: its amount in {other} can't be known; that side left out")
        due = dt.date.fromisoformat(r.next_expected)
        for day in schedule(due, r.cadence, r.anchor_days, start, end):
            when = day.isoformat()
            flows.append(
                Flow(when, r.money_account_id, sign * amount, currency, r.payee, "recurring")
            )
            if other is not None and other_amount is not None:
                flows.append(
                    Flow(when, r.account_id, -sign * other_amount, other, r.payee, "recurring")
                )
    return flows


def declared_flows(
    charges: Sequence[DeclaredCharge], base: str, start: dt.date, end: dt.date
) -> list[Flow]:
    """Declared subscriptions the ledger has not shown, as charges on the
    total, on the day of the month (or week) their next due date gives."""
    flows: list[Flow] = []
    for c in charges:
        anchors = (c.next_due.day,) if CADENCES[c.cadence].kind == "month_days" else ()
        first = c.next_due
        while first < start:  # a due date the user has not moved on since
            first = add_period(first, c.cadence, anchors)
        for day in schedule(first, c.cadence, anchors, start, end):
            flows.append(Flow(day.isoformat(), None, -c.amount, base, c.name, "subscription"))
    return flows


def project(
    balances: Mapping[str, tuple[str, Decimal]],
    flows: Sequence[Flow],
    to_base: Mapping[str, Decimal],
    base: str,
    start: dt.date,
    end: dt.date,
) -> Forecast:
    """Balances (account id → its currency and balance today) carried day by
    day through `flows`. `to_base` is base-currency units per unit of each
    other currency; an account in a currency it lacks counts in its own
    outlook but not in the total."""

    def in_base(currency: str, amount: Decimal) -> Decimal | None:
        if currency == base:
            return amount
        rate = to_base.get(currency)
        return None if rate is None else amount * rate

    by_day: dict[str, list[Flow]] = defaultdict(list)
    for f in flows:
        by_day[f.date].append(f)

    running = {account_id: amount for account_id, (_, amount) in balances.items()}
    lowest = {account_id: (amount, start.isoformat()) for account_id, amount in running.items()}

    def total() -> Decimal:
        values = (in_base(balances[a][0], v) for a, v in running.items())
        return sum((v for v in values if v is not None), Decimal(0)) + unassigned

    unassigned = Decimal(0)
    today_total = total()
    daily: list[tuple[str, Decimal]] = []
    low, low_date = today_total, start.isoformat()
    day = start
    while day <= end:
        when = day.isoformat()
        for f in by_day.get(when, []):
            if f.account_id is None:
                moved = in_base(f.currency, f.amount)
                unassigned += moved if moved is not None else Decimal(0)
            elif f.account_id in running:
                running[f.account_id] += f.amount
        # Each account's low point is where it ends a day, after all of the
        # day's flows: the rent and the salary landing on one day are not a
        # dip in between.
        for account_id, value in running.items():
            if value < lowest[account_id][0]:
                lowest[account_id] = (value, when)
        balance = total()
        daily.append((when, balance))
        if balance < low:
            low, low_date = balance, when
        day += dt.timedelta(days=1)

    outlooks = [
        AccountOutlook(
            account_id=account_id,
            currency=balances[account_id][0],
            today=balances[account_id][1],
            end=running[account_id],
            lowest=lowest[account_id][0],
            lowest_date=lowest[account_id][1],
        )
        for account_id in sorted(balances)
    ]
    return Forecast(
        start=start.isoformat(),
        end=end.isoformat(),
        today=today_total,
        end_balance=daily[-1][1] if daily else today_total,
        lowest=low,
        lowest_date=low_date,
        daily=daily,
        accounts=outlooks,
        flows=sorted(flows, key=lambda f: (f.date, f.description)),
    )
