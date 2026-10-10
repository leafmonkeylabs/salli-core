"""
Golden tests for the budget engine — hand-computed category-limit scenarios.
"""

from decimal import Decimal

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.budget.engine import compute
from salli.domain.budget.models import BudgetLineDef

_CASH = Account(id="cash", user_id="u1", code="1100", name="Cash", type="asset", currency="LKR")
_GROCERIES = Account(
    id="groceries", user_id="u1", code="5100", name="Groceries", type="expense", currency="LKR"
)
_TRANSPORT = Account(
    id="transport", user_id="u1", code="5200", name="Transport", type="expense", currency="LKR"
)
_SALARY = Account(
    id="salary", user_id="u1", code="4100", name="Salary", type="income", currency="LKR"
)


def _expense_entry(account_id: str, amount: str, entry_id: str) -> StoredJournalEntry:
    return StoredJournalEntry(
        id=entry_id,
        user_id="u1",
        entry_date="2026-07-05",
        description="spend",
        source="manual",
        postings=[
            Posting(
                account_id=account_id,
                direction=Direction.DEBIT,
                amount=Decimal(amount),
                currency="LKR",
            ),
            Posting(
                account_id="cash",
                direction=Direction.CREDIT,
                amount=Decimal(amount),
                currency="LKR",
            ),
        ],
    )


# ── Case 1: under budget in every category ──────────────────────────────────────


def test_under_budget_in_every_category():
    entries = [
        _expense_entry("groceries", "8000", "e1"),
        _expense_entry("transport", "3000", "e2"),
    ]
    budget_lines = [
        BudgetLineDef(account_id="groceries", limit_amount=Decimal("15000")),
        BudgetLineDef(account_id="transport", limit_amount=Decimal("5000")),
    ]
    summary = compute(entries, [_CASH, _GROCERIES, _TRANSPORT, _SALARY], budget_lines)

    assert summary.total_limit == Decimal("20000")
    assert summary.total_actual == Decimal("11000")
    assert summary.total_variance == Decimal("9000")

    groceries_line = next(line for line in summary.lines if line.account_id == "groceries")
    assert groceries_line.actual_amount == Decimal("8000")
    assert groceries_line.variance == Decimal("7000")


# ── Case 2: over budget in one category ─────────────────────────────────────────


def test_over_budget_in_one_category():
    entries = [
        _expense_entry("groceries", "18000", "e1"),
        _expense_entry("transport", "3000", "e2"),
    ]
    budget_lines = [
        BudgetLineDef(account_id="groceries", limit_amount=Decimal("15000")),
        BudgetLineDef(account_id="transport", limit_amount=Decimal("5000")),
    ]
    summary = compute(entries, [_CASH, _GROCERIES, _TRANSPORT, _SALARY], budget_lines)

    groceries_line = next(line for line in summary.lines if line.account_id == "groceries")
    assert groceries_line.variance == Decimal("-3000")
    assert summary.total_variance == Decimal(
        "-1000"
    )  # +2000 under on transport, -3000 over on groceries


# ── Case 3: a category with no spend yet still reports zero actual, not missing ─


def test_category_with_no_spend_reports_zero_actual():
    entries = [_expense_entry("groceries", "5000", "e1")]
    budget_lines = [
        BudgetLineDef(account_id="groceries", limit_amount=Decimal("15000")),
        BudgetLineDef(account_id="transport", limit_amount=Decimal("5000")),
    ]
    summary = compute(entries, [_CASH, _GROCERIES, _TRANSPORT, _SALARY], budget_lines)

    transport_line = next(line for line in summary.lines if line.account_id == "transport")
    assert transport_line.actual_amount == Decimal(0)
    assert transport_line.variance == Decimal("5000")


# ── Case 4: non-expense postings (income, transfers) are ignored ───────────────


def test_income_postings_do_not_count_as_expense_actuals():
    salary_entry = StoredJournalEntry(
        id="e1",
        user_id="u1",
        entry_date="2026-07-01",
        description="salary",
        source="manual",
        postings=[
            Posting(
                account_id="cash",
                direction=Direction.DEBIT,
                amount=Decimal("100000"),
                currency="LKR",
            ),
            Posting(
                account_id="salary",
                direction=Direction.CREDIT,
                amount=Decimal("100000"),
                currency="LKR",
            ),
        ],
    )
    budget_lines = [BudgetLineDef(account_id="groceries", limit_amount=Decimal("15000"))]
    summary = compute([salary_entry], [_CASH, _GROCERIES, _SALARY], budget_lines)

    assert summary.total_actual == Decimal(0)
