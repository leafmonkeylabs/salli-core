"""
Reading booked entries as the transactions rules are written about.

A rule talks about a transaction the way a bank statement does: money in or
out of one of the user's accounts, for some amount, described somehow. A
journal entry has postings instead, so this finds the money side (the cash,
bank or card account) and the other side (where the money came from or went),
for the simple two-posting entries rules are about. Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from salli.domain.accounting.models import Account, Direction, StoredJournalEntry
from salli.domain.rules.engine import Facts

_MONEY_TYPES = ("asset", "liability")


@dataclass(frozen=True)
class Booked:
    entry: StoredJournalEntry
    facts: Facts
    #: The account on the money side (the bank account, the card).
    money_account_id: str
    #: Where the other side went: what a rule's `account_id` would set.
    counter_account_id: str


def booked_transactions(
    entries: Iterable[StoredJournalEntry], accounts: Iterable[Account]
) -> list[Booked]:
    """Every two-posting entry with a money side, as a rule would see it.

    Reversals and reversed entries are left out: neither is a transaction the
    user made, and both would teach a rule the wrong thing. When both sides
    are money accounts (a transfer), the one money left is the money side.
    """
    kinds = {a.id: a.type for a in accounts}
    booked: list[Booked] = []
    for entry in entries:
        if entry.reversed_by or entry.source == "system" or len(entry.postings) != 2:
            continue
        if entry.description.startswith("REVERSAL:"):
            continue
        first, second = entry.postings
        money = [p for p in entry.postings if kinds.get(p.account_id) in _MONEY_TYPES]
        if not money:
            continue
        if len(money) == 2:
            side = first if first.direction == Direction.CREDIT else second
        else:
            side = money[0]
        other = second if side is first else first
        booked.append(
            Booked(
                entry=entry,
                facts=Facts(
                    description=entry.description,
                    amount=side.amount,
                    direction="in" if side.direction == Direction.DEBIT else "out",
                    currency=side.currency,
                ),
                money_account_id=side.account_id,
                counter_account_id=other.account_id,
            )
        )
    return booked
