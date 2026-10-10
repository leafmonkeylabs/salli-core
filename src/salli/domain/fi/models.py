"""
Financial Independence domain models — pure, frozen dataclasses, Decimal money.

Mirrors the tax domain: a versioned `FiPack` (the methodology + assumptions), an
aggregated input `FinancialSnapshot`, and a fully-recorded `FiScore` output. No I/O.
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
    return_conservative: Decimal
    return_base: Decimal
    return_growth: Decimal
    target_monthly_expenses: Decimal | None  # None = use actual from ledger
    target_age: int | None
    buckets: list[AllocationBucket]
    ai_rationale: str  # markdown explanation
    theories_applied: list[str]
    created_at: str  # ISO datetime string
    is_initial: bool  # True for first setup, False for refreshes


@dataclass(frozen=True)
class ProjectionPoint:
    """A single year's projected portfolio value under each return scenario."""

    year: int
    conservative: Decimal
    base: Decimal
    growth: Decimal


@dataclass(frozen=True)
class PurchaseOption:
    """One way of funding a purchase, costed in months of freedom."""

    key: str  # "cash" | "installments"
    label: str
    total_cost: Decimal  # total rupees handed over across the whole term
    interest_cost: Decimal  # total_cost − purchase amount (0 for cash)
    monthly_payment: Decimal | None  # None for cash
    term_months: int | None  # None for cash
    months_to_fi: int | None  # None = target not reachable within the horizon
    # Months of freedom this option costs, vs. not buying at all. None when
    # either figure is unknowable — never 0, which would read as "costs nothing".
    months_delay: int | None
    # True when the monthly payment exceeds the user's current monthly surplus:
    # the purchase is not merely slower, it is cash-flow negative.
    exceeds_monthly_surplus: bool


@dataclass(frozen=True)
class PurchaseImpact:
    """
    What a prospective purchase does to a user's balance sheet and FI date.

    Every figure here is computed deterministically by the engine. The LLM may
    narrate this object but must never derive a number of its own from it
    (CLAUDE.md: "LLM never computes money or tax").
    """

    amount: Decimal
    currency: str
    fi_number: Decimal
    fi_asset_base_before: Decimal
    monthly_surplus: Decimal
    baseline_months_to_fi: int | None  # None = not reachable within the horizon
    # Cash-flow feasibility, distinct from FI impact: can this be paid outright
    # from liquid savings, and what does that leave in the emergency fund?
    payable_from_liquid: bool
    emergency_months_before: Decimal
    emergency_months_after_cash: Decimal
    emergency_fund_target_months: int
    options: list[PurchaseOption]
    # Key of the option costing the fewest months of freedom, or None when no
    # option produced a comparable figure.
    cheapest_option_key: str | None
    # ISO date of the newest ledger entry behind this snapshot, and whether that
    # is fresh enough to answer on. A confident answer from a stale balance sheet
    # is worse than no answer.
    data_as_of: str | None = None
    is_stale: bool = False


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
    """Versioned FIRE methodology + assumptions (reviewable, like a tax pack)."""

    version: str
    # Fallback 4% rule → FI number = annual_expenses / safe_withdrawal_rate (= ×25
    # at 0.04). Used only when the user has no FIRE strategy of their own; when
    # they do, the strategy's validated SWR wins so one rate drives every figure.
    safe_withdrawal_rate: Decimal
    emergency_fund_target_months: int
    # Annual real (post-inflation) return assumed for the FI-date projection
    expected_real_return: Decimal
    # Assumed long-run annual inflation, used to convert the strategy's NOMINAL
    # return assumptions to real terms. Projections run in today's rupees, so the
    # FI target stays flat and comparable to the projected balances.
    expected_inflation: Decimal
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

    # Figures (all recorded for transparency, like TaxComputation.band_workings)
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
    projected_fi_years: Decimal | None  # None = not reachable / not yet knowable
    currency: str

    components: list[FiComponent] = field(default_factory=list)
