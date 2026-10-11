"""
Financial Independence domain models — pure, frozen dataclasses, Decimal money.

A versioned `FiPack` (the scoring method), an aggregated input
`FinancialSnapshot`, and a fully-recorded `FiScore` output. The planning
assumptions (returns, withdrawal rate, inflation) are not the pack's: they are
the user's, or labelled placeholders (domain/fi/assumptions.py). No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class AllocationBucket:
    """AI-generated allocation bucket within a FIRE strategy."""

    key: str  # e.g. "emergency_moat"
    name: str  # e.g. "Emergency Moat"
    target_pct: Decimal  # e.g. Decimal("0.20")
    description: str  # AI-generated rationale for this bucket
    color: str  # display color key (e.g. "emerald", "blue", "amber")


@dataclass(frozen=True)
class FireStrategy:
    """Versioned AI-generated FIRE configuration for a user."""

    version: int
    fire_style: str  # "lean" | "standard" | "fat" | "coast"
    swr: Decimal  # safe withdrawal rate, e.g. Decimal("0.04")
    # Yearly returns AFTER inflation, per scenario.
    real_return_conservative: Decimal
    real_return_base: Decimal
    real_return_growth: Decimal
    target_monthly_expenses: Decimal | None  # None = use actual from ledger
    target_age: int | None
    buckets: list[AllocationBucket]
    ai_rationale: str  # markdown explanation
    theories_applied: list[str]
    created_at: str  # ISO datetime string
    is_initial: bool  # True for first setup, False for refreshes


@dataclass(frozen=True)
class SurplusBreakdown:
    """Ledger-derived income and expense breakdown for the surplus flow chart."""

    income_by_source: dict[str, Decimal]  # account name → monthly avg
    expense_by_category: dict[str, Decimal]  # category tag (or account name) → monthly avg
    gross_monthly_income: Decimal
    gross_monthly_expenses: Decimal
    monthly_surplus: Decimal
    savings_rate: Decimal
    # need tag slug → monthly avg. Empty until spending is tagged on the `need`
    # axis; the 50/30/20 split is built from this. Defaulted and last so older
    # callers constructing this positionally keep working.
    expense_by_need: dict[str, Decimal] = field(default_factory=dict[str, Decimal])


@dataclass(frozen=True)
class FiPack:
    """Versioned FIRE scoring method, reviewable. Holds no planning
    assumption: the withdrawal rate and returns are passed to the engine from
    domain/fi/assumptions.py, so one set of them drives every figure."""

    version: str
    emergency_fund_target_months: int
    # Savings rate that earns a full component score (e.g. 0.50 = 50%)
    savings_rate_for_full_score: Decimal
    # Component weights — must sum to 1. Keys: savings_rate, emergency_fund,
    # fi_progress, debt, goals. (When the user has no goals, the goals weight is
    # dropped and the rest are renormalised by the engine.)
    weights: dict[str, Decimal]


@dataclass(frozen=True)
class FinancialSnapshot:
    """Aggregated inputs derived from the ledger (built by FiService, never the LLM)."""

    monthly_income: Decimal
    monthly_expenses: Decimal
    liquid_savings: Decimal  # cash + bank + savings (emergency-fund eligible)
    investments: Decimal  # FD / stocks / funds / bonds, etc.
    total_assets: Decimal
    total_liabilities: Decimal  # positive magnitude
    goal_progress: Decimal | None  # 0..1 weighted across active goals; None if none
    currency: str  # the owner's base currency, which every figure above is in


@dataclass(frozen=True)
class FiComponent:
    key: str
    label: str
    score: Decimal  # 0..100
    weight: Decimal  # effective weight used (after renormalisation)
    detail: str


@dataclass(frozen=True)
class FiScore:
    pack_version: str
    overall_score: Decimal  # 0..100
    grade: str

    # Figures (all recorded for transparency, as a tax computation's lines are)
    monthly_income: Decimal
    monthly_expenses: Decimal
    monthly_surplus: Decimal
    savings_rate: Decimal  # 0..1 — a FRACTION, not a percentage
    swr: Decimal  # 0..1 — the rate this fi_number was actually derived from
    annual_expenses: Decimal  # target annual expenses (the FI basis)
    fi_number: Decimal  # annual_expenses / swr
    net_worth: Decimal  # total assets − liabilities (all assets, incl. property)
    # Assets that can actually fund withdrawals: investable assets net of debt.
    # This — not net_worth — is what progress_to_fi and the projection measure.
    fi_asset_base: Decimal
    progress_to_fi: Decimal  # 0..1+ — UNCLAMPED, so ≥100% is visible
    emergency_fund_months: Decimal
    debt_to_asset: Decimal  # 0..1 — a FRACTION, not a percentage
    currency: str

    components: list[FiComponent] = field(default_factory=list[FiComponent])
    #: Months from the as-of month to the month FI is reached, from the
    #: baseline's monthly timeline (domain/baseline/fi.py). None when it
    #: isn't reached within 50 years, or there is no FI number yet.
    projected_fi_months: int | None = None
