"""
Duplicate detection for imported transactions.

An import is checked against what came before it, never against itself: two
identical rows in one statement are two transactions (two coffees, same shop,
same day), so an import keeps every row it reads.

What came before is two things:

- **Earlier imports** (`Imported`): the user's parsed transactions from other
  statements and feeds, the ones the user discarded included (a discarded
  card hold stays gone across overlapping exports). A row is an *exact*
  duplicate of an earlier one, hidden from review and never posted, when

  - both carry the same bank *id* (`ref_kind="id"`: an OFX FITID, a camt
    AcctSvcrRef, a feed's id) from the same kind of source, for the same
    money, within `REFERENCE_WINDOW_DAYS` (a pending-to-booked move); or
  - they agree on everything a statement says — date, amount, currency,
    direction, description and any text reference — matched count for count,
    come from the same kind of source, and are both on the same, known
    account.

  A text reference (a cheque number, a statement's own entry number) never
  decides anything alone: it is only part of what the row says. Agreement
  short of that — rows from different kinds of source (a bank feed and a
  file), or a side that does not say which account it is on — is a *fuzzy*
  match: flagged for review against the earlier row, never dropped. So is a
  row from a different kind of source with the same money a few days apart.
- **The ledger** (`Booked`, from domain/rules/history.py): entries the user
  booked, by hand or otherwise. A row that looks like one — same amount,
  currency and direction, within a few days, a similar description — is a
  *fuzzy* match too. The user decides.

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
from typing import Literal

from rapidfuzz import fuzz

from salli.domain.money import to_minor
from salli.domain.rules.history import Booked

DATE_WINDOW_DAYS = 3  # how far apart a booked entry and a statement row can be
# How far apart two rows with the same bank id can be and be one transaction:
# a card hold books days after it was authorised.
REFERENCE_WINDOW_DAYS = 10
SIMILARITY_THRESHOLD = 80  # rapidfuzz token_sort_ratio, 0-100

RefKind = Literal["id", "text"]


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
    bank_ref: str = ""  # the bank's (or feed's) id for it, or a reference someone wrote
    #: "id" when `bank_ref` is the bank's own id, "text" when it is not.
    ref_kind: RefKind = "id"
    #: The kind of source it came from ("ofx", "csv", "feed:simplefin"). Ids
    #: are compared only within one kind; "" (rows imported before sources
    #: were recorded) is taken to be any.
    source: str = ""


@dataclass(frozen=True)
class Imported:
    """A row of an earlier import."""

    id: str
    row: Candidate
    account_id: str = ""  # its statement's account; "" when it had none
    #: The user discarded it. It still is that transaction, so it matches as
    #: any earlier import does; it is never a fuzzy match's reason.
    discarded: bool = False


@dataclass(frozen=True)
class Verdict:
    status: DedupStatus
    #: The earlier import's row (exact, or fuzzy against an import) or the
    #: journal entry (fuzzy against the ledger).
    duplicate_of: str = ""
    similarity: float | None = None


@dataclass(frozen=True)
class _Side:
    """One money posting of a booked entry, as a statement row would show it."""

    entry_id: str
    external_ref: str
    account_id: str
    row: Candidate


@dataclass(frozen=True)
class _Prepared:
    """What the fuzzy passes compare, worked out once per row or side."""

    money: tuple[str, bool, int]  # currency, direction, minor amount
    day: int  # the date's ordinal
    words: str  # the normalised description


def _prepared(row: Candidate) -> _Prepared:
    return _Prepared(
        (row.currency, row.money_in, to_minor(row.amount, row.currency)),
        date.fromisoformat(row.date).toordinal(),
        normalize_description(row.description),
    )


def normalize_description(text: str) -> str:
    """Lower case, punctuation as spaces, whitespace collapsed."""
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


def identity(row: Candidate) -> tuple[str, int, str, bool, str]:
    """Everything a statement says about a transaction but its bank id: two
    rows with the same identity are, as far as any statement can tell, the
    same transaction — or two alike. A text reference is part of it."""
    words = normalize_description(row.description)
    if row.bank_ref and row.ref_kind == "text":
        words = f"{words} | {normalize_description(row.bank_ref)}"
    return (row.date, to_minor(row.amount, row.currency), row.currency, row.money_in, words)


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
    `imported` the earlier imports' rows around its dates (none already found
    to duplicate another), `booked` the ledger's entries around them, and
    `money_accounts` the user's asset and liability accounts, which tell a
    transfer's two sides apart.
    """
    verdicts = [Verdict(DedupStatus.UNIQUE) for _ in rows]
    earlier = [e for e in imported if _same_account(account_id, e.account_id)]
    taken: set[str] = set()  # earlier rows matched already, each to one row

    # The bank's own id says it is the same transaction, whatever else
    # changed (a pending description, a booking date), as long as the money
    # agrees and the dates are close: an id reused for another amount, or
    # months later, is another transaction.
    by_id: dict[str, list[Imported]] = defaultdict(list)
    for e in earlier:
        if _has_id(e.row):
            by_id[e.row.bank_ref].append(e)
    for i, row in enumerate(rows):
        if not _has_id(row):
            continue
        match = next(
            (
                e
                for e in by_id.get(row.bank_ref, [])
                if e.id not in taken
                and _same_source(row, e.row)
                and _same_money(row, e.row)
                and _days(row, e.row) <= REFERENCE_WINDOW_DAYS
            ),
            None,
        )
        if match is not None:
            verdicts[i] = Verdict(DedupStatus.EXACT_DUPLICATE, match.id)
            taken.add(match.id)

    # Then everything else a statement says, count for count. Two rows whose
    # bank gave them different ids are different transactions. An exact match
    # needs the same kind of source and the same, known account; short of
    # that it is flagged.
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
                if e.id not in taken
                and not (_has_id(row) and _has_id(e.row) and _same_source(row, e.row))
                and (_exact(row, e, account_id) or not e.discarded)
            ),
            None,
        )
        if match is not None:
            status = (
                DedupStatus.EXACT_DUPLICATE
                if _exact(row, match, account_id)
                else DedupStatus.FUZZY_MATCH
            )
            verdicts[i] = Verdict(status, match.id)
            taken.add(match.id)

    # A row from another kind of source (a feed's, against a file's) says
    # things differently: the same money a few days apart is flagged.
    others = [
        (e, _prepared(e.row))
        for e in earlier
        if not e.discarded and e.row.source and e.id not in taken
    ]
    for i, row in enumerate(rows):
        if verdicts[i].status is not DedupStatus.UNIQUE or not row.source:
            continue
        mine = _prepared(row)
        best: tuple[float, int, Imported] | None = None
        for e, theirs in others:
            if e.id in taken or e.row.source == row.source or theirs.money != mine.money:
                continue
            days = abs(mine.day - theirs.day)
            if days > DATE_WINDOW_DAYS:
                continue
            score = fuzz.token_sort_ratio(mine.words, theirs.words)
            if best is None or (score, -days) > best[:2]:
                best = (score, -days, e)
        if best is not None:
            score, _, e = best
            verdicts[i] = Verdict(DedupStatus.FUZZY_MATCH, e.id, float(score))
            taken.add(e.id)

    # The ledger catches what was booked some other way, by hand above all.
    # An entry posted from an earlier import matched above is that match, not
    # another; and each entry stands for one row at most. Sides are grouped
    # by their money, so a row is compared with the few that could match it.
    groups: dict[tuple[str, bool, int], list[tuple[_Side, _Prepared]]] = defaultdict(list)
    for side in _sides(booked, money_accounts):
        if side.external_ref in taken or (account_id and side.account_id != account_id):
            continue
        prepared = _prepared(side.row)
        groups[prepared.money].append((side, prepared))
    used: set[str] = set()
    for i, row in enumerate(rows):
        if verdicts[i].status is not DedupStatus.UNIQUE:
            continue
        mine = _prepared(row)
        best_side: tuple[float, int, _Side] | None = None
        for side, theirs in groups.get(mine.money, ()):
            if side.entry_id in used:
                continue
            days = abs(mine.day - theirs.day)
            if days > DATE_WINDOW_DAYS:
                continue
            score = fuzz.token_sort_ratio(mine.words, theirs.words)
            if score >= SIMILARITY_THRESHOLD and (
                best_side is None or (score, -days) > best_side[:2]
            ):
                best_side = (score, -days, side)
        if best_side is not None:
            score, _, side = best_side
            verdicts[i] = Verdict(DedupStatus.FUZZY_MATCH, side.entry_id, float(score))
            used.add(side.entry_id)
    return verdicts


def _has_id(row: Candidate) -> bool:
    return bool(row.bank_ref) and row.ref_kind == "id"


def _same_source(a: Candidate, b: Candidate) -> bool:
    return not (a.source and b.source and a.source != b.source)


def _exact(row: Candidate, earlier: Imported, account_id: str) -> bool:
    """Whether an identity match is sure enough to hide the row: the same kind
    of source, on the same account, both known."""
    return bool(account_id and earlier.account_id) and _same_source(row, earlier.row)


def _days(a: Candidate, b: Candidate) -> int:
    return abs((date.fromisoformat(a.date) - date.fromisoformat(b.date)).days)


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
