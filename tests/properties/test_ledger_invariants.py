"""
Property-based tests for core ledger invariants using Hypothesis.
These prove the rules hold for arbitrary inputs, not just hand-crafted examples.
"""

from decimal import Decimal
from typing import Any

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from salli.domain.accounting.ledger import (
    account_running_balance,
    assert_trial_balance,
    build_reversing_entry,
    trial_balance,
)
from salli.domain.accounting.models import Direction, JournalEntry, Posting, StoredJournalEntry

# ── strategies ────────────────────────────────────────────────────────────────


lkr_amount = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("100_000_000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

account_id = st.sampled_from(["bank", "salary", "rent", "fees", "equity"])


@st.composite
def balanced_entry(draw: Any) -> JournalEntry:
    """Draw a random balanced two-posting journal entry."""
    amount = draw(lkr_amount)
    debit_acc = draw(account_id)
    credit_acc = draw(account_id)
    assume(debit_acc != credit_acc)
    return JournalEntry(
        entry_date="2025-06-01",
        description="property test entry",
        source="manual",
        postings=[
            Posting(
                account_id=debit_acc,
                direction=Direction.DEBIT,
                amount=amount,
                currency="LKR",
            ),
            Posting(
                account_id=credit_acc,
                direction=Direction.CREDIT,
                amount=amount,
                currency="LKR",
            ),
        ],
    )


def as_stored(entry: JournalEntry, id: str = "e1") -> StoredJournalEntry:
    return StoredJournalEntry(id=id, user_id="u1", **entry.model_dump())


# ── invariant: single balanced entry always passes trial balance ───────────────


@given(entry=balanced_entry())
def test_single_balanced_entry_passes_trial_balance(entry: JournalEntry):
    assert_trial_balance([as_stored(entry)])


# ── invariant: any list of balanced entries passes trial balance ───────────────


@given(entries=st.lists(balanced_entry(), min_size=1, max_size=20))
@settings(max_examples=200)
def test_many_balanced_entries_pass_trial_balance(entries: list[JournalEntry]):
    stored = [as_stored(e, id=f"e{i}") for i, e in enumerate(entries)]
    assert_trial_balance(stored)


# ── invariant: entry + its reversal nets every account to zero ────────────────


@given(entry=balanced_entry())
def test_entry_plus_reversal_nets_to_zero(entry: JournalEntry):
    stored = as_stored(entry, id="e1")
    reversal = build_reversing_entry(stored)
    stored_reversal = as_stored(reversal, id="e2")
    assert_trial_balance([stored, stored_reversal])


# ── invariant: Posting.base_signed is always direction * (amount * fx_rate) ───


@given(
    amount=lkr_amount,
    fx_rate=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("1000"),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_base_signed_debit_positive(amount: Decimal, fx_rate: Decimal):
    p = Posting(
        account_id="bank",
        direction=Direction.DEBIT,
        amount=amount,
        currency="LKR",
        fx_rate=fx_rate,
    )
    assert p.base_signed > Decimal(0)


@given(amount=lkr_amount)
def test_base_signed_credit_negative(amount: Decimal):
    p = Posting(
        account_id="income",
        direction=Direction.CREDIT,
        amount=amount,
        currency="LKR",
    )
    assert p.base_signed < Decimal(0)


# ── invariant: an account's final running balance equals its trial-balance figure ─


@given(entries=st.lists(balanced_entry(), min_size=0, max_size=20), acc=account_id)
@settings(max_examples=200)
def test_running_balance_final_value_matches_trial_balance(entries: list[JournalEntry], acc: str):
    stored = [as_stored(e, id=f"e{i}") for i, e in enumerate(entries)]
    history = account_running_balance(stored, acc)
    expected = trial_balance(stored).get(acc, Decimal(0))
    final = history[-1][1] if history else Decimal(0)
    assert final == expected


@given(entries=st.lists(balanced_entry(), min_size=1, max_size=20), acc=account_id)
@settings(max_examples=200)
def test_running_balance_only_includes_entries_touching_the_account(
    entries: list[JournalEntry], acc: str
):
    stored = [as_stored(e, id=f"e{i}") for i, e in enumerate(entries)]
    history = account_running_balance(stored, acc)
    touching_ids = {e.id for e in stored if any(p.account_id == acc for p in e.postings)}
    assert {e.id for e, _ in history} == touching_ids
