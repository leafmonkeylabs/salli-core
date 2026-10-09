"""
Spending breakdown along the tag axes.

The chart of accounts used to be the only classification, and onboarding seeds
a single personal expense account — so every default user's breakdown was one
bar labelled "General Expenses". Tags give the detail without requiring anyone
to build a chart of accounts first.
"""

from __future__ import annotations

from decimal import Decimal

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.fi.engine import compute_surplus_breakdown


def _account(acc_id: str, name: str, acc_type: str) -> Account:
    return Account(id=acc_id, user_id="u1", code=acc_id, name=name, type=acc_type)  # type: ignore[arg-type]


def _entry(postings: list[Posting], date: str = "2025-06-01") -> StoredJournalEntry:
    return StoredJournalEntry(
        id=f"e-{date}-{len(postings)}",
        user_id="u1",
        entry_date=date,
        description="test",
        source="manual",
        postings=postings,
    )


def _spend(
    expense_acc: str, bank: str, amount: str, tags: dict[str, str] | None = None
) -> list[Posting]:
    return [
        Posting(
            account_id=expense_acc,
            direction=Direction.DEBIT,
            amount=Decimal(amount),
            currency="LKR",
            tags=tags or {},
        ),
        Posting(
            account_id=bank, direction=Direction.CREDIT, amount=Decimal(amount), currency="LKR"
        ),
    ]


ACCOUNTS = [
    _account("bank", "Bank Account (LKR)", "asset"),
    _account("exp", "General Expenses", "expense"),
    _account("inc", "Employment Income", "income"),
]


def test_category_tags_split_a_single_expense_account():
    """The whole point: one seeded expense account, several real categories."""
    entries = [
        _entry(_spend("exp", "bank", "30000", {"category": "groceries"})),
        _entry(_spend("exp", "bank", "18000", {"category": "transport"})),
        _entry(_spend("exp", "bank", "12000", {"category": "groceries"})),
    ]
    result = compute_surplus_breakdown(entries, ACCOUNTS, months=1)

    assert result.expense_by_category == {
        "groceries": Decimal("42000.00"),
        "transport": Decimal("18000.00"),
    }
    assert "General Expenses" not in result.expense_by_category


def test_untagged_spending_falls_back_to_the_account_name():
    """Tagging is optional — untagged spending must still be reported."""
    entries = [
        _entry(_spend("exp", "bank", "5000", {"category": "dining"})),
        _entry(_spend("exp", "bank", "7000")),
    ]
    result = compute_surplus_breakdown(entries, ACCOUNTS, months=1)

    assert result.expense_by_category["dining"] == Decimal("5000.00")
    assert result.expense_by_category["General Expenses"] == Decimal("7000.00")


def test_need_axis_produces_the_50_30_20_split():
    entries = [
        _entry(_spend("exp", "bank", "50000", {"category": "rent", "need": "essential"})),
        _entry(_spend("exp", "bank", "30000", {"category": "dining", "need": "discretionary"})),
        _entry(_spend("exp", "bank", "20000", {"category": "fund", "need": "savings"})),
    ]
    result = compute_surplus_breakdown(entries, ACCOUNTS, months=1)

    assert result.expense_by_need == {
        "essential": Decimal("50000.00"),
        "discretionary": Decimal("30000.00"),
        "savings": Decimal("20000.00"),
    }
    # Each axis sums to the same total — that is what one-tag-per-axis buys.
    assert sum(result.expense_by_need.values()) == sum(result.expense_by_category.values())


def test_need_breakdown_is_empty_when_nothing_is_tagged():
    """Clients must be able to tell "not classified yet" from "spent nothing"."""
    result = compute_surplus_breakdown([_entry(_spend("exp", "bank", "9000"))], ACCOUNTS, months=1)
    assert result.expense_by_need == {}
    assert result.expense_by_category == {"General Expenses": Decimal("9000.00")}


def _reverse(entry: StoredJournalEntry) -> StoredJournalEntry:
    """Mirror of LedgerService.reverse_entry, which also carries the tags over."""
    return _entry(
        [
            Posting(
                account_id=p.account_id,
                direction=Direction(-p.direction.value),
                amount=p.amount,
                currency=p.currency,
                tags=dict(p.tags),
            )
            for p in entry.postings
        ]
    )


def test_a_reversed_expense_leaves_the_breakdown():
    """Entries are immutable, so a reversal is the only correction. Counting the
    original and ignoring its reversal overstated that category forever."""
    original = _entry(_spend("exp", "bank", "25000", {"category": "groceries"}))
    kept = _entry(_spend("exp", "bank", "10000", {"category": "groceries"}))

    result = compute_surplus_breakdown([original, _reverse(original), kept], ACCOUNTS, months=1)
    assert result.expense_by_category == {"groceries": Decimal("10000.00")}


def test_a_fully_reversed_category_disappears_rather_than_showing_zero():
    original = _entry(_spend("exp", "bank", "25000", {"category": "groceries"}))
    result = compute_surplus_breakdown([original, _reverse(original)], ACCOUNTS, months=1)
    assert "groceries" not in result.expense_by_category


def test_reversed_income_leaves_the_breakdown_too():
    earn = _entry(
        [
            Posting(
                account_id="bank",
                direction=Direction.DEBIT,
                amount=Decimal("100000"),
                currency="LKR",
            ),
            Posting(
                account_id="inc",
                direction=Direction.CREDIT,
                amount=Decimal("100000"),
                currency="LKR",
            ),
        ]
    )
    result = compute_surplus_breakdown([earn, _reverse(earn)], ACCOUNTS, months=1)
    assert result.income_by_source == {}
    assert result.gross_monthly_income == Decimal("0.00")
