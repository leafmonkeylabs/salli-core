"""
Cash-flow forecast: where the money in the user's cash accounts is heading.

From today's balances, day by day to a horizon, applying what the ledger says
keeps happening (insights.detect_recurring: the salary, the rent, the
subscriptions it has seen) and the subscriptions the user declared that it
has not seen yet. Pure: no I/O, and nothing here guesses beyond those rhythms.

- A transfer between two cash accounts (rent from checking to the card,
  savings to checking) moves both, so the total does not change.
- A charge a little overdue is expected today, not skipped: for planning,
  late is not never.
- A declared subscription with no history has no account to say which cash
  account pays it, so it moves the total only.
- Amounts in an account's own currency; the total in the base currency, at
  the rate the caller gives for each currency.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from salli.domain.reports.insights import Cadence, Recurring, add_period

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


def _dates(first: dt.date, cadence: Cadence, anchor_day: int | None, end: dt.date) -> list[dt.date]:
    dates: list[dt.date] = []
    day = first
    while day <= end:
        dates.append(day)
        day = add_period(day, cadence, anchor_day)
    return dates


def recurring_flows(
    found: Sequence[Recurring],
    cash: Mapping[str, str],
    start: dt.date,
    end: dt.date,
) -> list[Flow]:
    """Every occurrence from `start` to `end` of what keeps happening on a cash
    account. `cash` is account id → its currency."""
    flows: list[Flow] = []
    for r in found:
        if r.money_account_id not in cash:
            continue
        sign = Decimal(1) if r.direction == "in" else Decimal(-1)
        first = max(dt.date.fromisoformat(r.next_expected), start)  # late is not never
        for day in _dates(first, r.cadence, r.anchor_day, end):
            when = day.isoformat()
            flows.append(
                Flow(
                    when,
                    r.money_account_id,
                    sign * r.typical_amount,
                    r.currency,
                    r.payee,
                    "recurring",
                )
            )
            # Into or out of another cash account in the same currency: a
            # transfer, which moves that account the other way.
            if cash.get(r.account_id) == r.currency:
                flows.append(
                    Flow(
                        when,
                        r.account_id,
                        -sign * r.typical_amount,
                        r.currency,
                        r.payee,
                        "recurring",
                    )
                )
    return flows


def declared_flows(
    charges: Sequence[DeclaredCharge], base: str, start: dt.date, end: dt.date
) -> list[Flow]:
    """Declared subscriptions the ledger has not shown, as charges on the total."""
    flows: list[Flow] = []
    for c in charges:
        first = c.next_due
        while first < start:
            first = add_period(
                first, c.cadence, None if c.cadence in ("weekly", "biweekly") else c.next_due.day
            )
        anchor = None if c.cadence in ("weekly", "biweekly") else c.next_due.day
        for day in _dates(first, c.cadence, anchor, end):
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
                if running[f.account_id] < lowest[f.account_id][0]:
                    lowest[f.account_id] = (running[f.account_id], when)
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
