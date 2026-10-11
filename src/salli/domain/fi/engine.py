"""
Deterministic Financial Independence engine.

Pure function: compute(snapshot, pack) -> FiScore. No I/O, no LLM, no Date.now.

Methodology (FIRE composite):
  • FI number      = target annual expenses / safe withdrawal rate (4% rule → ×25)
  • Progress to FI = FI asset base / FI number
  • Savings rate   = (income − expenses) / income
  • Emergency fund = liquid savings / monthly expenses  (target 3–6 months)
  • Debt load      = liabilities / assets  (lower is better)
  • Goal progress  = weighted progress across the user's active goals
The 0–100 score is a weighted blend of the five component scores.

Units: every ratio returned here is a FRACTION (0..1), never a percentage. Only
`overall_score` and `FiComponent.score` are on a 0..100 scale. Clients must
multiply the fractions by 100 themselves.

ONE withdrawal rate drives the FI number and the progress: callers pass
`swr`; there is no second rate hiding in a service.

When FI is reached is not walked here. It comes from the baseline's monthly
timeline (domain/baseline/fi.py), where cash, investments and debts are kept
apart, and the caller passes the month in (`projected_fi_months`), so the
score, the projections and every scenario say the same month.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from salli.domain.fi.assumptions import nominal_return, real_return
from salli.domain.fi.models import (
    FiComponent,
    FinancialSnapshot,
    FiPack,
    FiScore,
    SurplusBreakdown,
)

__all__ = [
    "compute",
    "compute_surplus_breakdown",
    "fi_asset_base",
    "installment_payment",
    "nominal_return",
    "real_return",
]

_HUNDRED = Decimal(100)


def _clamp(value: Decimal, lo: Decimal = Decimal(0), hi: Decimal = _HUNDRED) -> Decimal:
    return max(lo, min(hi, value))


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _grade(score: Decimal) -> str:
    if score >= 80:
        return "FI-ready"
    if score >= 60:
        return "Strong"
    if score >= 40:
        return "On track"
    if score >= 20:
        return "Building"
    return "Just starting"


def fi_asset_base(snapshot: FinancialSnapshot) -> Decimal:
    """
    The assets that can actually fund a safe-withdrawal-rate drawdown: investable
    assets, net of debt.

    A primary residence does not fund a 4%-rule withdrawal, so total net worth
    overstates FI progress. This deliberately differs from `net_worth`, and is the
    base used by BOTH progress-to-FI and the projection so the two agree.
    """
    return snapshot.liquid_savings + snapshot.investments - snapshot.total_liabilities


def installment_payment(amount: Decimal, annual_rate: Decimal, term_months: int) -> Decimal:
    """
    Level payment on an amortising loan — the standard annuity formula.

    Deterministic engine math, never the LLM: this figure decides whether a user
    takes on debt, so it is held to the same rule as tax.
    """
    if term_months <= 0:
        return Decimal(0)
    r = annual_rate / Decimal(12)
    if r <= 0:
        return amount / Decimal(term_months)
    discount = (Decimal(1) + r) ** -term_months
    return amount * r / (Decimal(1) - discount)


def compute(
    snapshot: FinancialSnapshot,
    pack: FiPack,
    *,
    swr: Decimal,
    target_monthly_expenses: Decimal | None = None,
    projected_fi_months: int | None = None,
) -> FiScore:
    """
    Score a snapshot.

    `swr` is the withdrawal rate that applies to the user;
    `target_monthly_expenses` comes from their FIRE strategy when it names
    one. They are parameters, never pack lookups, so the FI number here is
    the one the baseline's timeline measures FI against
    (domain/baseline/fi.py, given the same values). `projected_fi_months` is
    that timeline's answer: months from the as-of month to the month FI is
    reached, or None.

    Note `target_monthly_expenses` moves the FI *target* only. Contributions stay
    at the actual surplus, because aspiring to spend less in retirement does not
    by itself free up cash to invest today.
    """
    income = snapshot.monthly_income
    expenses = snapshot.monthly_expenses
    surplus = income - expenses
    savings_rate = (surplus / income) if income > 0 else Decimal(0)

    swr_eff = swr
    target_expenses = (
        target_monthly_expenses
        if (target_monthly_expenses is not None and target_monthly_expenses > 0)
        else expenses
    )
    annual_expenses = target_expenses * 12
    fi_number = (annual_expenses / swr_eff) if annual_expenses > 0 and swr_eff > 0 else Decimal(0)

    net_worth = snapshot.total_assets - snapshot.total_liabilities
    asset_base = fi_asset_base(snapshot)
    # Floored at 0 but NOT capped at 1: someone whose debts exceed their
    # investable assets has made no progress (rather than negative progress —
    # meaningless in a "% of target" reading, and unrenderable in a ring), while
    # someone past their number should still see >100%. `fi_asset_base` itself is
    # reported unfloored, so the underwater position stays visible.
    raw_progress = (asset_base / fi_number) if fi_number > 0 else Decimal(0)
    progress = max(Decimal(0), raw_progress)
    progress_clamped = min(Decimal(1), progress)
    ef_months = (snapshot.liquid_savings / expenses) if expenses > 0 else Decimal(0)
    debt_ratio = (
        snapshot.total_liabilities / snapshot.total_assets
        if snapshot.total_assets > 0
        else Decimal(0)
    )

    # ── Component scores (0..100) ──────────────────────────────────────────────
    sr_score = _clamp(savings_rate / pack.savings_rate_for_full_score * _HUNDRED)
    ef_target = Decimal(pack.emergency_fund_target_months)
    ef_score = _clamp(ef_months / ef_target * _HUNDRED) if ef_target > 0 else Decimal(0)
    fi_score_c = _clamp(progress_clamped * _HUNDRED)
    debt_score = _clamp((Decimal(1) - debt_ratio) * _HUNDRED)

    comp_defs = [
        ("savings_rate", "Savings rate", sr_score, f"Saving {_q2(savings_rate * 100)}% of income"),
        (
            "emergency_fund",
            "Emergency fund",
            ef_score,
            f"{_q2(ef_months)} of {pack.emergency_fund_target_months} months covered",
        ),
        ("fi_progress", "Progress to FI", fi_score_c, f"{_q2(progress * 100)}% of your FI number"),
        ("debt", "Debt load", debt_score, f"Liabilities are {_q2(debt_ratio * 100)}% of assets"),
    ]
    if snapshot.goal_progress is not None:
        goal_score = _clamp(snapshot.goal_progress * _HUNDRED)
        comp_defs.append(
            (
                "goals",
                "Goal progress",
                goal_score,
                f"{_q2(snapshot.goal_progress * 100)}% toward your goals",
            )
        )

    # Effective weights: drop missing components (e.g. goals) and renormalise.
    raw = {k: pack.weights.get(k, Decimal(0)) for k, *_ in comp_defs}
    total_w = sum(raw.values(), Decimal(0)) or Decimal(1)
    components: list[FiComponent] = []
    overall = Decimal(0)
    for key, label, score, detail in comp_defs:
        w = raw[key] / total_w
        overall += score * w
        components.append(
            FiComponent(key=key, label=label, score=_q2(score), weight=_q2(w), detail=detail)
        )

    overall = _q2(_clamp(overall))

    return FiScore(
        pack_version=pack.version,
        overall_score=overall,
        grade=_grade(overall),
        monthly_income=income,
        monthly_expenses=expenses,
        monthly_surplus=surplus,
        savings_rate=savings_rate,
        swr=swr_eff,
        annual_expenses=annual_expenses,
        fi_number=fi_number,
        net_worth=net_worth,
        fi_asset_base=asset_base,
        progress_to_fi=progress,
        emergency_fund_months=ef_months,
        debt_to_asset=debt_ratio,
        projected_fi_months=projected_fi_months,
        currency=snapshot.currency,
        components=components,
    )


def compute_surplus_breakdown(
    entries: list[Any],
    accounts: list[Any],
    months: int,
) -> SurplusBreakdown:
    """Group income and expenses over `months` months, monthly.

    `entries` are the months' own: the baseline's months observed
    (domain/baseline), so the totals here are its monthly income and
    expenses, every posting counted, a category that netted to money back
    included. Only the breakdowns leave out what nets to nothing or less.

    Expenses group by their `category` tag where one exists, falling back to the
    account name. That fallback matters: onboarding seeds a single personal
    expense account, so grouping by account alone gave every default user a
    one-bar breakdown. Tags give the detail without forcing anyone to build a
    chart of accounts before their spending is legible.

    Amounts are netted signed rather than filtered by direction, so a reversing
    entry cancels the original. Filtering on `Direction` counted the original and
    ignored its reversal, permanently overstating whatever was reversed.
    """
    acc_map = {a.id: a for a in accounts}
    income_by_source: dict[str, Decimal] = {}
    expense_by_category: dict[str, Decimal] = {}
    expense_by_need: dict[str, Decimal] = {}

    for entry in entries:
        for p in entry.postings:
            acc = acc_map.get(p.account_id)
            if acc is None:
                continue
            tags = getattr(p, "tags", {}) or {}
            if acc.type == "income":
                # CR increases income, so a reversing DR subtracts.
                income_by_source[acc.name] = (
                    income_by_source.get(acc.name, Decimal(0)) - p.base_signed
                )
            elif acc.type == "expense":
                label = tags.get("category") or acc.name
                expense_by_category[label] = (
                    expense_by_category.get(label, Decimal(0)) + p.base_signed
                )
                need = tags.get("need")
                if need:
                    expense_by_need[need] = expense_by_need.get(need, Decimal(0)) + p.base_signed

    if months <= 0:
        zero = Decimal("0.00")
        return SurplusBreakdown({}, {}, zero, zero, zero, zero, {})
    m = Decimal(months)
    # Drop anything that nets to zero or below — a fully reversed category is
    # not a category the user spent in.
    income_monthly = {k: _q2(v / m) for k, v in income_by_source.items() if v > 0}
    expense_monthly = {k: _q2(v / m) for k, v in expense_by_category.items() if v > 0}
    need_monthly = {k: _q2(v / m) for k, v in expense_by_need.items() if v > 0}

    # The totals: every posting, before any rounding of the parts.
    gross_income = sum(income_by_source.values(), Decimal(0)) / m
    gross_expenses = sum(expense_by_category.values(), Decimal(0)) / m
    surplus = gross_income - gross_expenses
    savings_rate = (surplus / gross_income) if gross_income > 0 else Decimal(0)

    # Keep only top 6 expense categories by amount
    top_expenses = dict(sorted(expense_monthly.items(), key=lambda x: x[1], reverse=True)[:6])

    return SurplusBreakdown(
        income_by_source=income_monthly,
        expense_by_category=top_expenses,
        expense_by_need=need_monthly,
        gross_monthly_income=_q2(gross_income),
        gross_monthly_expenses=_q2(gross_expenses),
        monthly_surplus=_q2(surplus),
        savings_rate=_q2(savings_rate),
    )
