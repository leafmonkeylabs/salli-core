"""
Deterministic budget engine.

Pure function: compute(entries, accounts, budget_lines) -> BudgetSummary. No I/O.
Callers are responsible for scoping `entries` to the budget period (mirroring
`fi/engine.py`'s convention of trusting pre-filtered ledger data) — the engine only
aggregates actual expense-account spend and compares it against the declared limits.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from salli.domain.accounting.models import Direction
from salli.domain.budget.models import BudgetLine, BudgetLineDef, BudgetSummary


def compute(
    entries: list[Any],
    accounts: list[Any],
    budget_lines: list[BudgetLineDef],
) -> BudgetSummary:
    acc_map = {a.id: a for a in accounts}
    actuals: dict[str, Decimal] = {}
    for entry in entries:
        for p in entry.postings:
            acc = acc_map.get(p.account_id)
            if acc is None or acc.type != "expense" or p.direction != Direction.DEBIT:
                continue
            actuals[p.account_id] = actuals.get(p.account_id, Decimal(0)) + abs(p.base_signed)

    lines: list[BudgetLine] = []
    for bl in budget_lines:
        actual = actuals.get(bl.account_id, Decimal(0))
        acc = acc_map.get(bl.account_id)
        category = acc.name if acc is not None else bl.account_id
        lines.append(
            BudgetLine(
                account_id=bl.account_id,
                category=category,
                limit_amount=bl.limit_amount,
                actual_amount=actual,
                variance=bl.limit_amount - actual,
            )
        )

    total_limit = sum((line.limit_amount for line in lines), Decimal(0))
    total_actual = sum((line.actual_amount for line in lines), Decimal(0))
    return BudgetSummary(
        lines=lines,
        total_limit=total_limit,
        total_actual=total_actual,
        total_variance=total_limit - total_actual,
    )
