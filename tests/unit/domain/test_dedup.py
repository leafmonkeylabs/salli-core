"""Unit tests for the duplicate detection matcher."""

from salli.domain.dedup.matcher import (
    CandidateTransaction,
    DedupStatus,
    batch_check,
    check_duplicates,
    compute_dedup_key,
)


def txn(
    id: str = "t1",
    account_id: str = "bank",
    entry_date: str = "2025-06-01",
    amount_minor: int = 30_000_00,  # LKR 300,000 in cents
    description: str = "Salary transfer",
    source: str = "statement",
    bank_ref: str | None = None,
) -> CandidateTransaction:
    return CandidateTransaction(
        id=id,
        account_id=account_id,
        entry_date=entry_date,
        amount_minor=amount_minor,
        currency="LKR",
        description=description,
        source=source,
        bank_ref=bank_ref,
    )


# ── Exact match ────────────────────────────────────────────────────────────────


def test_identical_transaction_is_exact_duplicate():
    t = txn()
    key = compute_dedup_key(t)
    result = check_duplicates(t, [], {key})
    assert result.status == DedupStatus.EXACT_DUPLICATE


def test_bank_ref_match_is_exact_duplicate():
    t1 = txn(id="t1", bank_ref="BREF001")
    t2 = txn(id="t2", bank_ref="BREF001")
    result = check_duplicates(t2, [t1], set())
    assert result.status == DedupStatus.EXACT_DUPLICATE
    assert result.duplicate_of == "t1"


def test_unique_transaction_passes():
    t = txn()
    result = check_duplicates(t, [], set())
    assert result.status == DedupStatus.UNIQUE


# ── Fuzzy match ────────────────────────────────────────────────────────────────


def test_same_amount_nearby_date_similar_desc_is_fuzzy():
    t1 = txn(id="t1", entry_date="2025-06-01", description="Salary transfer June")
    t2 = txn(id="t2", entry_date="2025-06-02", description="salary transfer june")
    result = check_duplicates(t2, [t1], set())
    assert result.status == DedupStatus.FUZZY_MATCH
    assert result.duplicate_of == "t1"
    assert result.similarity_score is not None and result.similarity_score >= 80


def test_different_account_is_not_fuzzy():
    t1 = txn(id="t1", account_id="bank_lkr")
    t2 = txn(id="t2", account_id="bank_usd")
    result = check_duplicates(t2, [t1], set())
    assert result.status == DedupStatus.UNIQUE


def test_different_amount_is_not_fuzzy():
    t1 = txn(id="t1", amount_minor=30_000_00)
    t2 = txn(id="t2", amount_minor=25_000_00)
    result = check_duplicates(t2, [t1], set())
    assert result.status == DedupStatus.UNIQUE


def test_date_outside_window_is_not_fuzzy():
    t1 = txn(id="t1", entry_date="2025-06-01")
    t2 = txn(id="t2", entry_date="2025-06-10")  # 9 days apart
    result = check_duplicates(t2, [t1], set())
    assert result.status == DedupStatus.UNIQUE


def test_date_at_window_boundary_is_fuzzy():
    t1 = txn(id="t1", entry_date="2025-06-01")
    t2 = txn(id="t2", entry_date="2025-06-04")  # exactly 3 days
    result = check_duplicates(t2, [t1], set())
    assert result.status == DedupStatus.FUZZY_MATCH


def test_dissimilar_description_is_unique():
    t1 = txn(id="t1", description="Salary transfer")
    t2 = txn(id="t2", description="Electricity bill payment CEB")
    result = check_duplicates(t2, [t1], set())
    assert result.status == DedupStatus.UNIQUE


# ── Batch check ────────────────────────────────────────────────────────────────


def test_batch_catches_intra_batch_duplicates():
    t1 = txn(id="t1")
    t2 = txn(id="t2")  # identical to t1
    results = batch_check([t1, t2], [], set())
    assert results[0].status == DedupStatus.UNIQUE
    assert results[1].status in (DedupStatus.EXACT_DUPLICATE, DedupStatus.FUZZY_MATCH)


def test_batch_all_unique():
    candidates = [
        txn(id="t1", amount_minor=10000, description="Coffee"),
        txn(id="t2", amount_minor=20000, description="Lunch"),
        txn(id="t3", amount_minor=30000, description="Taxi"),
    ]
    results = batch_check(candidates, [], set())
    assert all(r.status == DedupStatus.UNIQUE for r in results)


# ── Dedup key ──────────────────────────────────────────────────────────────────


def test_dedup_key_is_stable():
    t = txn()
    assert compute_dedup_key(t) == compute_dedup_key(t)


def test_dedup_key_differs_on_amount():
    t1 = txn(amount_minor=10000)
    t2 = txn(amount_minor=20000)
    assert compute_dedup_key(t1) != compute_dedup_key(t2)


def test_dedup_key_case_insensitive_description():
    t1 = txn(description="SALARY TRANSFER")
    t2 = txn(description="salary transfer")
    assert compute_dedup_key(t1) == compute_dedup_key(t2)
