"""
Duplicate detection for parsed transactions.

Layered strategy (applied in order):
  1. Idempotency key — exact hash match (bank txn IDs are authoritative)
  2. Fuzzy match    — same account + exact amount + date ±N days + description similarity
  3. Source priority — bank statement > parsed SMS > manual
  4. Human gate     — ambiguous matches are flagged, never auto-merged
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum

from rapidfuzz import fuzz

# ── Config ─────────────────────────────────────────────────────────────────────

DATE_WINDOW_DAYS = 3  # ±3 days for cross-source fuzzy matching
SIMILARITY_THRESHOLD = 80  # rapidfuzz score 0-100

SOURCE_PRIORITY: dict[str, int] = {
    "statement": 3,
    "sms": 2,
    "manual": 1,
    "system": 0,
}


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CandidateTransaction:
    id: str
    account_id: str
    entry_date: str  # YYYY-MM-DD
    amount_minor: int  # always positive
    currency: str
    description: str
    source: str  # statement | sms | manual | system
    bank_ref: str | None = None  # bank-provided transaction ID (authoritative)


class DedupStatus(str, Enum):
    UNIQUE = "unique"
    EXACT_DUPLICATE = "exact_duplicate"
    FUZZY_MATCH = "fuzzy_match"  # needs human confirmation
    CONFIRMED_DUPLICATE = "confirmed_duplicate"  # human approved the merge


@dataclass
class DedupResult:
    candidate: CandidateTransaction
    status: DedupStatus
    duplicate_of: str | None = None  # id of the winning transaction
    similarity_score: float | None = None


# ── Key computation ────────────────────────────────────────────────────────────


def _normalize_description(desc: str) -> str:
    """Strip extra whitespace, lowercase, remove punctuation."""
    desc = desc.lower().strip()
    desc = re.sub(r"[^\w\s]", " ", desc)
    return re.sub(r"\s+", " ", desc)


def compute_dedup_key(txn: CandidateTransaction) -> str:
    """
    Idempotency key: SHA-256 of (account, date, amount_minor, currency,
    normalized_description, bank_ref).
    If bank_ref is provided it is the authoritative anchor.
    """
    parts = [
        txn.account_id,
        txn.entry_date,
        str(txn.amount_minor),
        txn.currency,
        _normalize_description(txn.description),
        txn.bank_ref or "",
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


# ── Core matching logic ────────────────────────────────────────────────────────


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def _within_date_window(a: str, b: str, window: int = DATE_WINDOW_DAYS) -> bool:
    return abs((_parse_date(a) - _parse_date(b)).days) <= window


def _description_similar(a: str, b: str) -> tuple[bool, float]:
    score = fuzz.token_sort_ratio(_normalize_description(a), _normalize_description(b))
    return score >= SIMILARITY_THRESHOLD, float(score)


def _bank_ref_matches(a: CandidateTransaction, b: CandidateTransaction) -> bool:
    """Bank refs are authoritative — if both present and equal, it's a definitive match."""
    return bool(a.bank_ref and b.bank_ref and a.bank_ref == b.bank_ref)


def _source_wins(incoming: CandidateTransaction, existing: CandidateTransaction) -> bool:
    """Return True if the existing record should be kept (higher or equal priority)."""
    return SOURCE_PRIORITY.get(existing.source, 0) >= SOURCE_PRIORITY.get(incoming.source, 0)


# ── Public API ─────────────────────────────────────────────────────────────────


def check_duplicates(
    incoming: CandidateTransaction,
    existing: Sequence[CandidateTransaction],
    existing_keys: set[str],
) -> DedupResult:
    """
    Compare `incoming` against the corpus of already-posted transactions.

    Returns a DedupResult with:
      - UNIQUE              → safe to post
      - EXACT_DUPLICATE     → definitive match; discard incoming
      - FUZZY_MATCH         → surface to user for confirmation before posting
    """
    incoming_key = compute_dedup_key(incoming)

    # ── 1. Exact key match ────────────────────────────────────────────────────
    if incoming_key in existing_keys:
        return DedupResult(
            candidate=incoming,
            status=DedupStatus.EXACT_DUPLICATE,
            duplicate_of=None,  # key is enough; caller resolves the ID
        )

    # ── 2. Bank-ref exact match ───────────────────────────────────────────────
    if incoming.bank_ref:
        for ex in existing:
            if _bank_ref_matches(incoming, ex):
                return DedupResult(
                    candidate=incoming,
                    status=DedupStatus.EXACT_DUPLICATE,
                    duplicate_of=ex.id,
                )

    # ── 3. Fuzzy cross-source match ───────────────────────────────────────────
    for ex in existing:
        if ex.account_id != incoming.account_id:
            continue
        if ex.amount_minor != incoming.amount_minor or ex.currency != incoming.currency:
            continue
        if not _within_date_window(incoming.entry_date, ex.entry_date):
            continue

        similar, score = _description_similar(incoming.description, ex.description)
        if similar:
            return DedupResult(
                candidate=incoming,
                status=DedupStatus.FUZZY_MATCH,
                duplicate_of=ex.id,
                similarity_score=score,
            )

    return DedupResult(candidate=incoming, status=DedupStatus.UNIQUE)


def batch_check(
    candidates: Sequence[CandidateTransaction],
    existing: Sequence[CandidateTransaction],
    existing_keys: set[str],
) -> list[DedupResult]:
    """
    Check a batch of incoming candidates against the existing corpus.
    Each unique candidate is added to the working set so intra-batch
    duplicates are also caught.
    """
    results: list[DedupResult] = []
    working_existing = list(existing)
    working_keys = set(existing_keys)

    for candidate in candidates:
        result = check_duplicates(candidate, working_existing, working_keys)
        results.append(result)
        if result.status == DedupStatus.UNIQUE:
            working_existing.append(candidate)
            working_keys.add(compute_dedup_key(candidate))

    return results
