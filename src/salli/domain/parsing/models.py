"""
Domain models for statement parsing.

Flow:
  raw bytes (OFX/QFX, QIF, camt.053, MT940, CSV, PDF, XLSX)
  → list[RawRow]          (extracted by format-specific adapter — no LLM)
  → list[ParsedTransaction] (classified by LLM — account debit/credit, category)
  → dedup check
  → user review
  → list[JournalEntry]    (posted to ledger)

The LLM touches ParsedTransaction only. Numbers come from the raw extractor;
the LLM assigns accounts and categories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

#: Where a parsed transaction stands. "pending": waiting for review (nothing
#: found like it); "unique": the same, as rows saved early on say;
#: "fuzzy_match": waiting, flagged as maybe booked already; "exact_duplicate":
#: booked already, never posted; "posted"; "discarded" by the user.
DedupState = Literal["pending", "unique", "fuzzy_match", "exact_duplicate", "posted", "discarded"]


@dataclass(frozen=True)
class RawRow:
    """
    One row as extracted from the source file — no interpretation yet.
    The extractor guarantees that `amount` is always positive; direction
    is conveyed by `credit_flag` (True = money coming in).
    """

    date: str  # YYYY-MM-DD (normalised by extractor)
    description: str  # raw description text from the statement
    amount: Decimal  # always positive
    credit_flag: bool  # True = credit (money in), False = debit (money out)
    currency: str  # ISO 4217 — the file's own where it names one, else the caller's
    bank_ref: str = ""  # reference / transaction ID from the bank
    source_page: int = 0
    #: "id": the bank's (or feed's) own id for the transaction, which may
    #: identify it alone; "text": a reference someone wrote (a cheque number,
    #: a customer reference), only ever part of what the row says.
    ref_kind: str = "id"
    #: The account in the file the row is on, when the file holds several.
    source_account: str = ""
    #: Where the row came from ("ofx", "csv", "feed:simplefin"...). An id is
    #: only compared with ids from the same kind of source.
    ref_source: str = ""


@dataclass
class ParsedTransaction:
    """
    A RawRow enriched by the LLM with account classification.
    Mutable — the user may edit debit_account_id / credit_account_id before posting.
    """

    raw: RawRow
    debit_account_id: str  # account to debit
    credit_account_id: str  # account to credit
    category: str = ""  # e.g. "salary", "bank_charge", "transfer"
    need: str = ""  # essential | discretionary | savings, when a rule says
    # What the entry is booked as, when that should not be the bank's text (a
    # rule's clean name for "AMZN MKTP US*2K4…"). Empty: the bank's.
    description: str = ""
    notes: str = ""
    confidence: float = 1.0
    rule_id: str = ""  # the rule that decided the row, if one did
    dedup_key: str = ""  # SHA-256 idempotency key (filled by dedup module)
    dedup_status: DedupState = "pending"
    # What it duplicates: an earlier parsed transaction (exact) or a journal
    # entry (fuzzy).
    duplicate_of: str = ""
    id: str = ""  # DB primary key, populated after persistence
    statement_id: str = ""  # parent Statement's ID, populated after persistence
    # The statement's account, when it has one: the money side of this row
    # (debited for money in, credited for money out).
    account_id: str = ""


@dataclass
class ParseResult:
    """Outcome of parsing one statement file."""

    statement_id: str
    bank: str
    period_start: str
    period_end: str
    transactions: list[ParsedTransaction] = field(default_factory=list)
    raw_rows: list[RawRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    #: Rows left out as already imported (a bank feed's overlap), not kept.
    duplicates_dropped: int = 0
