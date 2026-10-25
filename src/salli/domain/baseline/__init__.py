"""
The baseline: one consistent, dated model of a user's money, as of a day.

Pure: no I/O, no model, Decimal throughout. The application gathers the
inputs (`BaselineInputs`); `build` turns them into a `Baseline`; `cash` and
`timeline` project it: a daily cash timeline for the next twelve months, in
nominal money, and a monthly timeline to a horizon of up to 50 years, in
today's money. FI, insights, the cash forecast, safe-to-spend and the debt
plan all read their figures from it, so they never disagree about what a
user earns, spends, owns or owes. docs/baseline.md explains the definitions.
"""

from salli.domain.baseline.build import build, worth, worth_by_day
from salli.domain.baseline.models import (
    Balance,
    Baseline,
    BaselineDebt,
    BaselineHolding,
    BaselineInputs,
    BaselineTax,
    DeclaredDebt,
    Flows,
    HoldingInputs,
    MonthFlow,
    Rate,
    Role,
    TaxInputs,
    TaxRules,
    Worth,
)

__all__ = [
    "Balance",
    "Baseline",
    "BaselineDebt",
    "BaselineHolding",
    "BaselineInputs",
    "BaselineTax",
    "DeclaredDebt",
    "Flows",
    "HoldingInputs",
    "MonthFlow",
    "Rate",
    "Role",
    "TaxInputs",
    "TaxRules",
    "Worth",
    "build",
    "worth",
    "worth_by_day",
]
