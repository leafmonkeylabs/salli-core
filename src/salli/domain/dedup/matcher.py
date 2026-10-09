"""
Duplicate detection for imported transactions.

An import is checked against what came before it, never against itself: two
identical rows in one statement are two transactions (two coffees, same shop,
same day), so an import keeps every row it reads.

What came before is two things:

- **Earlier imports** (`Imported`): the user's parsed transactions from other
  statements and feeds. A row is an *exact* duplicate of an earlier one when
  both carry the same bank reference, or else when they agree on everything a
  statement says — date, amount, currency, direction and description —
  matched count for count: a file with two identical coffees against a history
  with one has one duplicate. Exact duplicates are kept for review but never
  posted.
- **The ledger** (`Booked`, from domain/rules/history.py): entries the user
  booked, by hand or otherwise. A row that looks like one — same amount,
  currency and direction, within a few days, a similar description — is a
  *fuzzy* match: flagged for review, never dropped. The user decides.

Rows on different accounts are never duplicates, when both say which account
they are on. Pure: no I/O.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from rapidfuzz import fuzz

from salli.domain.money import to_minor
from salli.domain.rules.history import Booked

DATE_WINDOW_DAYS = 3  # how far apart a booked entry and a statement row can be
SIMILARITY_THRESHOLD = 80  # rapidfuzz token_sort_ratio, 0-100


class DedupStatus(str, Enum):
    UNIQUE = "unique"
    EXACT_DUPLICATE = "exact_duplicate"
    FUZZY_MATCH = "fuzzy_match"  # needs the user to look


@dataclass(frozen=True)
class Candidate:
    """A transaction as a statement or feed states it."""

    date: str  # YYYY-MM-DD
    amount: Decimal  # always positive
    currency: str
    money_in: bool
    description: str
    bank_ref: str = ""  # the bank's (or feed's) id for it


@dataclass(frozen=True)
class Imported:
    """A row of an earlier import."""

    id: str
    row: Candidate
    account_id: str = ""  # its statement's account; "" when it had none


@dataclass(frozen=True)
class Verdict:
    status: DedupStatus
    #: The earlier import's row (exact) or the journal entry (fuzzy).
    duplicate_of: str = ""
    similarity: float | None = None


@dataclass(frozen=True)
class _Side:
    """One money posting of a booked entry, as a statement row would show it."""

    entry_id: str
    external_ref: str
    account_id: str
    row: Candidate


def normalize_description(text: str) -> str:
    """Lower case, punctuation as spaces, whitespace collapsed."""
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


def identity(row: Candidate) -> tuple[str, int, str, bool, str]:
    """Everything a statement says about a transaction but its reference: two
    rows with the same identity are, as far as any statement can tell, the
    same transaction — or two alike."""
    return (
        row.date,
        to_minor(row.amount, row.currency),
        row.currency,
        row.money_in,
        normalize_description(row.description),
    )


def dedup_key(row: Candidate) -> str:
    """A row's identity as a SHA-256 hex digest, for storing and indexing."""
    return hashlib.sha256("|".join(map(str, identity(row))).encode()).hexdigest()


def find_duplicates(
    rows: Sequence[Candidate],
    *,
    account_id: str = "",
    imported: Sequence[Imported] = (),
    booked: Sequence[Booked] = (),
    money_accounts: Collection[str] = frozenset(),
) -> list[Verdict]:
    """A verdict for each of an import's `rows`, in order.

    `account_id` is the account the import is on ("" when it does not say),
    `imported` the earlier imports' rows around its dates (none the user
    discarded, none already found to duplicate another), `booked` the ledger's
    entries around them, and `money_accounts` the user's asset and liability
    accounts, which tell a transfer's two sides apart.
    """
    verdicts = [Verdict(DedupStatus.UNIQUE) for _ in rows]
    earlier = [e for e in imported if _same_account(account_id, e.account_id)]
    taken: set[str] = set()  # earlier rows matched already, each to one row

    # The bank's own reference says it is the same transaction, whatever else
    # changed (a pending description, a booking date), as long as the money
    # agrees: a reference reused for another amount is another transaction.
    by_reference: dict[str, list[Imported]] = defaultdict(list)
    for e in earlier:
        if e.row.bank_ref:
            by_reference[e.row.bank_ref].append(e)
    for i, row in enumerate(rows):
        if not row.bank_ref:
            continue
        match = next(
            (
                e
                for e in by_reference.get(row.bank_ref, [])
                if e.id not in taken and _same_money(row, e.row)
            ),
            None,
        )
        if match is not None:
            verdicts[i] = Verdict(DedupStatus.EXACT_DUPLICATE, match.id)
            taken.add(match.id)

    # Then everything else a statement says, count for count. Two rows whose
    # banks gave them different references are different transactions.
    by_identity: dict[tuple[str, int, str, bool, str], list[Imported]] = defaultdict(list)
    for e in earlier:
        by_identity[identity(e.row)].append(e)
    for i, row in enumerate(rows):
        if verdicts[i].status is not DedupStatus.UNIQUE:
            continue
        match = next(
            (
                e
                for e in by_identity.get(identity(row), [])
                if e.id not in taken and not (row.bank_ref and e.row.bank_ref)
            ),
            None,
        )
        if match is not None:
            verdicts[i] = Verdict(DedupStatus.EXACT_DUPLICATE, match.id)
            taken.add(match.id)

    # The ledger catches what was booked some other way, by hand above all.
    # An entry posted from an earlier import matched above is that match, not
    # another; and each entry stands for one row at most.
    sides = [
        s
        for s in _sides(booked, money_accounts)
        if s.external_ref not in taken and (not account_id or s.account_id == account_id)
    ]
    used: set[str] = set()
    for i, row in enumerate(rows):
        if verdicts[i].status is not DedupStatus.UNIQUE:
            continue
        best: tuple[float, int, _Side] | None = None
        for side in sides:
            if side.entry_id in used or not _same_money(row, side.row):
                continue
            days = abs((date.fromisoformat(row.date) - date.fromisoformat(side.row.date)).days)
            if days > DATE_WINDOW_DAYS:
                continue
            score = fuzz.token_sort_ratio(
                normalize_description(row.description),
                normalize_description(side.row.description),
            )
            if score >= SIMILARITY_THRESHOLD and (best is None or (score, -days) > best[:2]):
                best = (score, -days, side)
        if best is not None:
            score, _, side = best
            verdicts[i] = Verdict(DedupStatus.FUZZY_MATCH, side.entry_id, float(score))
            used.add(side.entry_id)
    return verdicts


def _same_account(a: str, b: str) -> bool:
    return not (a and b and a != b)


def _same_money(a: Candidate, b: Candidate) -> bool:
    return (
        a.currency == b.currency
        and a.money_in == b.money_in
        and to_minor(a.amount, a.currency) == to_minor(b.amount, b.currency)
    )


def _sides(booked: Sequence[Booked], money_accounts: Collection[str]) -> list[_Side]:
    """Each money posting of each booked entry. A transfer between two of the
    user's own accounts is on both, so it shows on both their statements."""
    sides: list[_Side] = []
    for b in booked:
        row = Candidate(
            date=b.entry.entry_date,
            amount=b.facts.amount,
            currency=b.facts.currency,
            money_in=b.facts.direction == "in",
            description=b.entry.description,
        )
        ref = b.entry.external_ref or ""
        sides.append(_Side(b.entry.id, ref, b.money_account_id, row))
        if b.counter_account_id in money_accounts:
            mirrored = Candidate(
                row.date, row.amount, row.currency, not row.money_in, row.description
            )
            sides.append(_Side(b.entry.id, ref, b.counter_account_id, mirrored))
    return sides
