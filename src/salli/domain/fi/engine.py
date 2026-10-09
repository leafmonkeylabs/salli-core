"""
Deterministic Financial Independence engine.

Pure function: compute(snapshot, pack) -> FiScore. No I/O, no LLM, no Date.now —
the FI-date *years* are computed here; the calendar date is derived by the caller.

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

Two invariants this module exists to hold, both of which were previously broken
by having parallel implementations:
  1. ONE withdrawal rate drives the FI number, the progress and the projection.
     Callers pass `swr`; there is no second rate hiding in a service.
  2. ONE compounding routine (`_fv_after_months`) backs both the projected series
     and years-to-FI, so "13 years" always agrees with where the chart crosses.

Projections run in REAL terms (today's rupees): nominal return assumptions are
converted via the Fisher relation, which keeps the flat FI target line valid and
stops years-to-FI being flattered by inflation.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from salli.domain.fi.models import (
    FiComponent,
    FinancialSnapshot,
    FiPack,
    FireStrategy,
    FiScore,
    ProjectionPoint,
    PurchaseImpact,
    PurchaseOption,
    SurplusBreakdown,
)

_HUNDRED = Decimal(100)
_MAX_PROJECTION_YEARS = 100


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


def real_return(nominal: Decimal, inflation: Decimal) -> Decimal:
    """Fisher relation: strip inflation out of a nominal annual return."""
    if inflation <= Decimal(-1):
        return nominal
    return (Decimal(1) + nominal) / (Decimal(1) + inflation) - Decimal(1)


def _fv_after_months(
    pv: Decimal, monthly_contribution: Decimal, annual_rate: Decimal, months: int
) -> Decimal:
    """
    Future value of a lump sum plus an ordinary monthly annuity.

    The single compounding routine in this module — `project_portfolio` and
    `years_to_target` both call it, which is what guarantees the chart and the
    years-to-FI figure can never disagree. `annual_rate` is a nominal annual rate
    compounded monthly, so a stated 10% realises 10.47% effective; that is the
    convention, applied consistently.
    """
    r = annual_rate / Decimal(12)
    if r == 0:
        return pv + monthly_contribution * months
    growth = (Decimal(1) + r) ** months
    return pv * growth + monthly_contribution * (growth - Decimal(1)) / r


def fi_asset_base(snapshot: FinancialSnapshot) -> Decimal:
    """
    The assets that can actually fund a safe-withdrawal-rate drawdown: investable
    assets, net of debt.

    A primary residence does not fund a 4%-rule withdrawal, so total net worth
    overstates FI progress. This deliberately differs from `net_worth`, and is the
    base used by BOTH progress-to-FI and the projection so the two agree.
    """
    return snapshot.liquid_savings + snapshot.investments - snapshot.total_liabilities


def years_to_target(
    starting: Decimal,
    monthly_contribution: Decimal,
    annual_rate: Decimal,
    target: Decimal,
    max_years: int = _MAX_PROJECTION_YEARS,
) -> Decimal | None:
    """
    Years until `starting` plus monthly contributions reaches `target`.

    Returns None when the answer is unknowable rather than pretending it is zero:
    a user with no recorded expenses has no FI target yet, and answering "0 years"
    (as an earlier version did) told brand-new users they were already retired.
    """
    if target <= 0:
        return None
    if starting >= target:
        return Decimal(0)
    if monthly_contribution <= 0 and annual_rate <= 0:
        return None
    # Quantised to cents each year, exactly as `project_portfolio` does, so the
    # two walk identical values. Comparing full precision here against a
    # cents-rounded series made a balance of 299.996 cross in the chart (rounds to
    # 300.00) but not in the solver — a knife-edge one-year disagreement.
    value = _q2(starting)
    for year in range(1, max_years + 1):
        value = _q2(_fv_after_months(value, monthly_contribution, annual_rate, 12))
        if value >= target:
            return Decimal(year)
    return None


def _months_to_target(
    starting: Decimal,
    annual_rate: Decimal,
    target: Decimal,
    contribution_for_month: Callable[[int], Decimal],
    max_years: int = _MAX_PROJECTION_YEARS,
) -> int | None:
    """
    Months until `starting` plus a (possibly varying) monthly contribution reaches
    `target`. The month-resolution sibling of `years_to_target`.

    Quantisation is deliberately asymmetric: the running value is rounded to cents
    ONLY at year boundaries, while the target is checked every month. That is what
    makes this reconcile exactly with `years_to_target` — at month 12k the value is
    the same one that walk carries, so a crossing here at month m always satisfies
    `ceil(m / 12) == years_to_target(...)`. Rounding every month instead would
    accumulate twelve roundings a year against that walk's one and could report a
    crossing a year apart from the headline figure — the same class of
    chart-vs-solver disagreement the earlier FI audit had to fix.

    `contribution_for_month` takes a 1-based month index so a funding plan whose
    payments stop partway through (installments) can be expressed directly.
    """
    if target <= 0:
        return None
    value = _q2(starting)
    if value >= target:
        return 0
    for month in range(1, max_years * 12 + 1):
        value = _fv_after_months(value, contribution_for_month(month), annual_rate, 1)
        if month % 12 == 0:
            value = _q2(value)
        if value >= target:
            return month
    return None


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


def simulate_purchase(
    snapshot: FinancialSnapshot,
    pack: FiPack,
    amount: Decimal,
    *,
    swr: Decimal | None = None,
    target_monthly_expenses: Decimal | None = None,
    annual_real_return: Decimal | None = None,
    term_months: int | None = None,
    annual_interest_rate: Decimal = Decimal(0),
    data_as_of: str | None = None,
    is_stale: bool = False,
) -> PurchaseImpact:
    """
    Cost a prospective purchase in months of freedom.

    The two funding options are modelled so that neither double-counts:

    * **Cash** — the asset base drops by the full amount today; the monthly
      contribution is untouched. Total drag is exactly the purchase price.
    * **Installments** — the asset base is untouched today (the money is still
      invested; the debt is owed to the seller) and the monthly contribution
      falls by the payment for the length of the term. Total drag is
      `payment × term`, i.e. the price plus interest.

    Booking the liability *and* deducting the repayments would charge the
    principal twice, so exactly one of the two is applied per option.

    `swr` / `target_monthly_expenses` / `annual_real_return` mirror `compute()`
    and must be passed the same values, or the FI target this measures against
    will differ from the one on the user's dashboard.
    """
    swr_eff = swr if (swr is not None and swr > 0) else pack.safe_withdrawal_rate
    expenses = snapshot.monthly_expenses
    target_expenses = (
        target_monthly_expenses
        if (target_monthly_expenses is not None and target_monthly_expenses > 0)
        else expenses
    )
    annual_expenses = target_expenses * 12
    fi_number = (annual_expenses / swr_eff) if annual_expenses > 0 and swr_eff > 0 else Decimal(0)

    rate = annual_real_return if annual_real_return is not None else pack.expected_real_return
    base = fi_asset_base(snapshot)
    surplus = snapshot.monthly_income - expenses

    baseline = _months_to_target(base, rate, fi_number, lambda _m: surplus)

    def _delay(after: int | None) -> int | None:
        if after is None or baseline is None:
            return None
        return after - baseline

    options: list[PurchaseOption] = []

    # ── Option 1: pay cash ────────────────────────────────────────────────────
    cash_months = _months_to_target(base - amount, rate, fi_number, lambda _m: surplus)
    options.append(
        PurchaseOption(
            key="cash",
            label="Pay in full",
            total_cost=_q2(amount),
            interest_cost=Decimal("0.00"),
            monthly_payment=None,
            term_months=None,
            months_to_fi=cash_months,
            months_delay=_delay(cash_months),
            exceeds_monthly_surplus=False,
        )
    )

    # ── Option 2: installments ────────────────────────────────────────────────
    if term_months and term_months > 0:
        payment = installment_payment(amount, annual_interest_rate, term_months)
        total = payment * Decimal(term_months)
        term = term_months

        def _contribution(month: int, _p: Decimal = payment, _t: int = term) -> Decimal:
            return surplus - _p if month <= _t else surplus

        inst_months = _months_to_target(base, rate, fi_number, _contribution)
        options.append(
            PurchaseOption(
                key="installments",
                label=f"{term_months} monthly payments",
                total_cost=_q2(total),
                # Floored at zero. The annuity payment is an exact (often
                # repeating) decimal, so at 0% `payment × term` lands a hair
                # under the price and the raw difference quantises to "-0.00" —
                # a negative interest cost, which is both meaningless and, on a
                # product selling trustworthy figures, reads as broken.
                interest_cost=max(Decimal("0.00"), _q2(total - amount)),
                monthly_payment=_q2(payment),
                term_months=term_months,
                months_to_fi=inst_months,
                months_delay=_delay(inst_months),
                exceeds_monthly_surplus=payment > surplus,
            )
        )

    comparable = [o for o in options if o.months_delay is not None]
    cheapest = min(comparable, key=lambda o: o.months_delay or 0).key if comparable else None

    liquid = snapshot.liquid_savings
    return PurchaseImpact(
        amount=_q2(amount),
        currency=snapshot.currency,
        # NOT quantised, deliberately: `compute()` returns the raw quotient, and
        # these two must be bit-identical so a purchase can never be costed
        # against a different Freedom number than the dashboard shows. Rounding
        # for display is the client's job.
        fi_number=fi_number,
        fi_asset_base_before=_q2(base),
        monthly_surplus=_q2(surplus),
        baseline_months_to_fi=baseline,
        payable_from_liquid=liquid >= amount,
        emergency_months_before=_q2(liquid / expenses) if expenses > 0 else Decimal(0),
        emergency_months_after_cash=(
            _q2((liquid - amount) / expenses) if expenses > 0 else Decimal(0)
        ),
        emergency_fund_target_months=pack.emergency_fund_target_months,
        options=options,
        cheapest_option_key=cheapest,
        data_as_of=data_as_of,
        is_stale=is_stale,
    )


def compute(
    snapshot: FinancialSnapshot,
    pack: FiPack,
    *,
    swr: Decimal | None = None,
    target_monthly_expenses: Decimal | None = None,
    annual_real_return: Decimal | None = None,
) -> FiScore:
    """
    Score a snapshot.

    `swr`, `target_monthly_expenses` and `annual_real_return` come from the user's
    FIRE strategy when they have one; each falls back to the pack. They are
    parameters rather than pack lookups precisely so the projection path cannot
    diverge from this one — pass the same values to `project_portfolio` and every
    figure on the page reconciles.

    Note `target_monthly_expenses` moves the FI *target* only. Contributions stay
    at the actual surplus, because aspiring to spend less in retirement does not
    by itself free up cash to invest today.
    """
    income = snapshot.monthly_income
    expenses = snapshot.monthly_expenses
    surplus = income - expenses
    savings_rate = (surplus / income) if income > 0 else Decimal(0)

    swr_eff = swr if (swr is not None and swr > 0) else pack.safe_withdrawal_rate
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
    rr = annual_real_return if annual_real_return is not None else pack.expected_real_return
    projected_years = years_to_target(asset_base, surplus, rr, fi_number)

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
        projected_fi_years=projected_years,
        currency=snapshot.currency,
        components=components,
    )


def scenario_real_returns(strategy: FireStrategy, pack: FiPack) -> dict[str, Decimal]:
    """The strategy's three nominal assumptions, converted to real terms once."""
    return {
        "conservative": real_return(strategy.return_conservative, pack.expected_inflation),
        "base": real_return(strategy.return_base, pack.expected_inflation),
        "growth": real_return(strategy.return_growth, pack.expected_inflation),
    }


def project_portfolio(
    snapshot: FinancialSnapshot,
    strategy: FireStrategy,
    pack: FiPack,
    horizon_years: int = 15,
) -> list[ProjectionPoint]:
    """
    Project the FI asset base forward under three REAL return scenarios.

    Real, not nominal: the FI target is expressed in today's rupees, so growing the
    portfolio at nominal rates against it would cross years too early. Starts from
    `fi_asset_base` — the same base `compute()` measures progress against.
    """
    starting = fi_asset_base(snapshot)
    monthly_contribution = snapshot.monthly_income - snapshot.monthly_expenses
    rates = scenario_real_returns(strategy, pack)

    start = _q2(starting)
    points: list[ProjectionPoint] = [
        ProjectionPoint(year=0, conservative=start, base=start, growth=start)
    ]

    # Values are carried forward already quantised to cents — the same walk
    # `years_to_target` performs, which is what keeps the crossing year and the
    # headline figure identical.
    #
    # Deliberately NOT floored at zero: flooring made a net-debt starting position
    # climb faster here than in the solver. A line that dips below zero is the
    # honest picture for someone whose debts exceed their investments.
    values = {name: start for name in rates}
    for year in range(1, horizon_years + 1):
        values = {
            name: _q2(_fv_after_months(values[name], monthly_contribution, rate, 12))
            for name, rate in rates.items()
        }
        points.append(
            ProjectionPoint(
                year=year,
                conservative=values["conservative"],
                base=values["base"],
                growth=values["growth"],
            )
        )

    return points


def compute_surplus_breakdown(
    entries: list[Any],
    accounts: list[Any],
    months: int = 12,
) -> SurplusBreakdown:
    """Group income and expenses from trailing-N-month entries.

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

    m = Decimal(months)
    # Drop anything that nets to zero or below — a fully reversed category is
    # not a category the user spent in.
    income_monthly = {k: _q2(v / m) for k, v in income_by_source.items() if v > 0}
    expense_monthly = {k: _q2(v / m) for k, v in expense_by_category.items() if v > 0}
    need_monthly = {k: _q2(v / m) for k, v in expense_by_need.items() if v > 0}

    gross_income = sum(income_monthly.values(), Decimal(0))
    gross_expenses = sum(expense_monthly.values(), Decimal(0))
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
