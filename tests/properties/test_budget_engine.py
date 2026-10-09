"""
Property-based tests for the budget engine using Hypothesis.

Proves the core aggregation invariant holds for arbitrary entry sets: the sum of
per-category actuals always equals the total actual spend for the period.
"""

from decimal import Decimal
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.budget.engine import compute
from salli.domain.budget.models import BudgetLineDef

_EXPENSE_ACCOUNT_IDS = ["groceries", "transport", "utilities"]
_ACCOUNTS = [
    Account(id="cash", user_id="u1", code="1100", name="Cash", type="asset"),
    *[
        Account(id=aid, user_id="u1", code=f"5{i}00", name=aid.title(), type="expense")
        for i, aid in enumerate(_EXPENSE_ACCOUNT_IDS)
    ],
]
_BUDGET_LINES = [
    BudgetLineDef(account_id=aid, limit_amount=Decimal("50000")) for aid in _EXPENSE_ACCOUNT_IDS
]

lkr_amount = st.decimals(
    min_value=Decimal("1"),
    max_value=Decimal("1_000_000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


@st.composite
def expense_entry(draw: Any) -> StoredJournalEntry:
    account_id = draw(st.sampled_from(_EXPENSE_ACCOUNT_IDS))
    amount = draw(lkr_amount)
    return StoredJournalEntry(
        id="e",
        user_id="u1",
        entry_date="2026-07-01",
        description="spend",
        source="manual",
        postings=[
            Posting(
                account_id=account_id, direction=Direction.DEBIT, amount=amount, currency="LKR"
            ),
            Posting(account_id="cash", direction=Direction.CREDIT, amount=amount, currency="LKR"),
        ],
    )


@given(entries=st.lists(expense_entry(), min_size=0, max_size=20))
@settings(max_examples=200)
def test_sum_of_category_actuals_equals_total_actual(entries: list[StoredJournalEntry]):
    summary = compute(entries, _ACCOUNTS, _BUDGET_LINES)
    assert sum((line.actual_amount for line in summary.lines), Decimal(0)) == summary.total_actual


@given(entries=st.lists(expense_entry(), min_size=0, max_size=20))
@settings(max_examples=200)
def test_total_actual_equals_sum_of_all_expense_debits(entries: list[StoredJournalEntry]):
    summary = compute(entries, _ACCOUNTS, _BUDGET_LINES)

    expected = Decimal(0)
    for entry in entries:
        for p in entry.postings:
            if p.account_id in _EXPENSE_ACCOUNT_IDS and p.direction == Direction.DEBIT:
                expected += p.amount
    assert summary.total_actual == expected


@given(entries=st.lists(expense_entry(), min_size=0, max_size=20))
@settings(max_examples=200)
def test_total_variance_equals_limit_minus_actual(entries: list[StoredJournalEntry]):
    summary = compute(entries, _ACCOUNTS, _BUDGET_LINES)
    assert summary.total_variance == summary.total_limit - summary.total_actual
