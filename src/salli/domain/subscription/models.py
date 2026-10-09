"""
Recurring-subscription domain models — pure, frozen dataclasses, Decimal money.
No I/O.

A Subscription is a declared recurring expectation (name, amount, frequency, next
due date) — never a live integration with a bank or merchant. Matching against
posted ledger entries, and the resulting missed-charge/price-change alerts, are
computed at query time; a Subscription never mutates a JournalEntry (entries are
immutable per the ledger's double-entry invariant) — the association is always
derived, not stored on the entry.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, cast, get_args

Frequency = Literal["weekly", "monthly", "quarterly", "yearly"]
AlertKind = Literal["missed_charge", "price_change"]

FREQUENCIES: tuple[Frequency, ...] = get_args(Frequency)


def normalize_frequency(value: str) -> Frequency:
    """One of `FREQUENCIES`, whatever its case ("Monthly" is "monthly").
    ValueError for anything else: an unknown frequency stored would break every
    report and forecast that reads it later."""
    folded = str(value).strip().casefold()
    if folded not in FREQUENCIES:
        raise ValueError(f"Unknown frequency {value!r}: use one of {', '.join(FREQUENCIES)}")
    return cast(Frequency, folded)


def normalize_due_date(value: str) -> str:
    """A next due date as YYYY-MM-DD. ValueError for anything that isn't one."""
    try:
        return datetime.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError as exc:
        raise ValueError(f"Invalid next due date {value!r}: use YYYY-MM-DD") from exc


@dataclass(frozen=True)
class Subscription:
    name: str
    amount: Decimal  # expected charge amount
    frequency: Frequency
    next_due_date: str  # YYYY-MM-DD — anchor date when no match has occurred yet
    account_id: str | None = None  # restrict matching to this expense account, if set
    grace_days: int = 5
    amount_tolerance_pct: Decimal = Decimal("0.05")


@dataclass(frozen=True)
class SubscriptionMatch:
    entry_id: str
    entry_date: str
    amount: Decimal


@dataclass(frozen=True)
class SubscriptionAlert:
    kind: AlertKind
    message: str
    expected_amount: Decimal | None = None
    actual_amount: Decimal | None = None


@dataclass(frozen=True)
class SubscriptionReport:
    matches: list[SubscriptionMatch] = field(default_factory=list[SubscriptionMatch])
    alerts: list[SubscriptionAlert] = field(default_factory=list[SubscriptionAlert])
