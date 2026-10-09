"""
Budget domain models — pure, frozen dataclasses, Decimal money. No I/O.

Mirrors the tax/fi domains: a declared input (a list of per-account `BudgetLineDef`
limits) and a fully-recorded output (`BudgetSummary`) produced by the pure
`engine.compute` function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class BudgetLineDef:
    """A declared category limit — the input side, before actuals are computed."""

    account_id: str
    limit_amount: Decimal


@dataclass(frozen=True)
class BudgetLine:
    """A category limit compared against actual ledger spend for the period."""

    account_id: str
    category: str  # the expense account's display name
    limit_amount: Decimal
    actual_amount: Decimal
    variance: Decimal  # limit - actual; negative means over budget


@dataclass(frozen=True)
class BudgetSummary:
    lines: list[BudgetLine] = field(default_factory=list[BudgetLine])
    total_limit: Decimal = Decimal(0)
    total_actual: Decimal = Decimal(0)
    total_variance: Decimal = Decimal(0)
