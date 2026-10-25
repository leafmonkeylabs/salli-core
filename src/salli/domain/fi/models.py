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
    # The yearly rate, averaged over debts by balance, at which the debt
    # component scores nothing (a rate of 0 scores full marks).
    debt_rate_for_zero_score: Decimal = Decimal("0.20")
    # The debt-service ratio (scheduled payments ÷ income) at which its part
    # of the debt component scores nothing, and that part's share of the
    # component (the rest is the rate, or the share of assets).
    debt_service_for_zero_score: Decimal = Decimal("0.40")
    debt_service_weight: Decimal = Decimal(0)
    # The progress to FI below which the top grades are not given:
    # "FI-ready" and "Strong" each.
    progress_for_fi_ready: Decimal = Decimal(1)
    progress_for_strong: Decimal = Decimal("0.5")


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
    #: The debts with known terms: (yearly rate, balance owed) each.
    debt_rates: tuple[tuple[Decimal, Decimal], ...] = ()
    #: The debts' scheduled monthly payments, together.
    monthly_debt_payments: Decimal = Decimal(0)
    #: Full months of income and spending observed; None when not counted.
    full_months: int | None = None
    #: The emergency fund held out of the FI asset base (`baseline.fi.reserve`).
    held_out: Decimal = Decimal(0)


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
