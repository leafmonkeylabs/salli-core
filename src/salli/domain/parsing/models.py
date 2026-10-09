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
    notes: str = ""
    confidence: float = 1.0
    dedup_key: str = ""  # SHA-256 idempotency key (filled by dedup module)
    dedup_status: str = "pending"  # UNIQUE | EXACT_DUPLICATE | FUZZY_MATCH
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
