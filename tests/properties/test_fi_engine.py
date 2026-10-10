"""
Property-based tests for the FI ("Freedom") engine using Hypothesis.

The headline property here is SCALE INVARIANCE, and it is the one this repo was
missing. Every other engine's property tests assert self-consistency (a trial
balance nets zero, total_gain == value − cost), which holds at *any* scale and so
cannot catch a units error. Multiplying every money input by k must leave the
dimensionless outputs — savings rate, progress, scores — completely unchanged.
A ×100 slip anywhere in the ratio path breaks that immediately.

The engine works in real terms, and takes the withdrawal rate and real returns
explicitly (the pack holds none). These properties hold for any such figures;
the round ones below stand in for whatever applies to a user.
"""

from decimal import Decimal
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from salli.domain.fi import engine
from salli.domain.fi.models import FinancialSnapshot, FiPack

PACK = FiPack(
    version="prop-1",
    emergency_fund_target_months=6,
    savings_rate_for_full_score=Decimal("0.50"),
    weights={
        "savings_rate": Decimal("0.25"),
        "emergency_fund": Decimal("0.15"),
        "fi_progress": Decimal("0.35"),
        "debt": Decimal("0.10"),
        "goals": Decimal("0.15"),
    },
)

SWR = Decimal("0.04")
REAL = Decimal("0.05")
RATES = {"conservative": Decimal("0.03"), "base": REAL, "growth": Decimal("0.07")}


def _score(s: FinancialSnapshot, **over: Any):
    return engine.compute(s, PACK, **{"swr": SWR, "annual_real_return": REAL, **over})


def _impact(s: FinancialSnapshot, amount: Decimal, **over: Any):
    return engine.simulate_purchase(
        s, PACK, amount, **{"swr": SWR, "annual_real_return": REAL, **over}
    )


money = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("10000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
positive_money = st.decimals(
    min_value=Decimal("1000"),
    max_value=Decimal("10000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
scale_factor = st.sampled_from([Decimal("2"), Decimal("10"), Decimal("100"), Decimal("0.5")])


@st.composite
def snapshot(draw: Any) -> FinancialSnapshot:
    income = draw(positive_money)
    expenses = draw(st.decimals(min_value=Decimal("1"), max_value=income, places=2))
    liquid = draw(money)
    investments = draw(money)
    liabilities = draw(money)
    return FinancialSnapshot(
        monthly_income=income,
        monthly_expenses=expenses,
        liquid_savings=liquid,
        investments=investments,
        total_assets=liquid + investments,
        total_liabilities=liabilities,
        goal_progress=None,
        currency="EUR",
    )


def _scaled(s: FinancialSnapshot, k: Decimal) -> FinancialSnapshot:
    return FinancialSnapshot(
        monthly_income=s.monthly_income * k,
        monthly_expenses=s.monthly_expenses * k,
        liquid_savings=s.liquid_savings * k,
        investments=s.investments * k,
        total_assets=s.total_assets * k,
        total_liabilities=s.total_liabilities * k,
        goal_progress=s.goal_progress,
        currency="EUR",
    )


# ── The unit-bug catcher ──────────────────────────────────────────────────────


@given(snapshot(), scale_factor)
@settings(max_examples=100, deadline=None)
def test_dimensionless_outputs_are_scale_invariant(s: FinancialSnapshot, k: Decimal) -> None:
    """Scaling all money by k must not move any ratio or score."""
    a = _score(s)
    b = _score(_scaled(s, k))

    assert a.savings_rate == b.savings_rate
    assert a.debt_to_asset == b.debt_to_asset
    assert a.emergency_fund_months == b.emergency_fund_months
    assert a.progress_to_fi == b.progress_to_fi
    assert a.overall_score == b.overall_score
    assert a.grade == b.grade


@given(snapshot(), scale_factor)
@settings(max_examples=50, deadline=None)
def test_money_outputs_scale_linearly(s: FinancialSnapshot, k: Decimal) -> None:
    """The converse: money outputs must scale exactly with the inputs."""
    a = _score(s)
    b = _score(_scaled(s, k))

    assert b.fi_number == a.fi_number * k
    assert b.net_worth == a.net_worth * k
    assert b.fi_asset_base == a.fi_asset_base * k
    assert b.monthly_surplus == a.monthly_surplus * k


# ── Range invariants: fractions stay fractions, scores stay 0..100 ────────────


@given(snapshot())
@settings(max_examples=100, deadline=None)
def test_ratios_stay_in_fraction_range(s: FinancialSnapshot) -> None:
    score = _score(s)
    # savings_rate: expenses <= income by construction, so 0..1.
    assert Decimal(0) <= score.savings_rate <= Decimal(1)
    assert Decimal(0) <= score.debt_to_asset
    assert score.progress_to_fi >= Decimal(0)


@given(snapshot())
@settings(max_examples=100, deadline=None)
def test_scores_stay_in_percent_range(s: FinancialSnapshot) -> None:
    score = _score(s)
    assert Decimal(0) <= score.overall_score <= Decimal(100)
    for c in score.components:
        assert Decimal(0) <= c.score <= Decimal(100)


@given(snapshot())
@settings(max_examples=100, deadline=None)
def test_effective_weights_always_sum_to_one(s: FinancialSnapshot) -> None:
    score = _score(s)
    total = sum((c.weight for c in score.components), Decimal(0))
    # Quantised to 2dp per component, so allow a rounding cent.
    assert abs(total - Decimal(1)) <= Decimal("0.01")


# ── Monotonicity: the engine must respond in the right direction ──────────────


@given(positive_money, positive_money)
@settings(max_examples=50, deadline=None)
def test_fi_number_rises_with_expenses(a: Decimal, b: Decimal) -> None:
    lo, hi = min(a, b), max(a, b)
    income = hi * 2
    s_lo = FinancialSnapshot(
        monthly_income=income,
        monthly_expenses=lo,
        liquid_savings=Decimal(0),
        investments=Decimal(0),
        total_assets=Decimal(0),
        total_liabilities=Decimal(0),
        goal_progress=None,
        currency="EUR",
    )
    s_hi = FinancialSnapshot(
        monthly_income=income,
        monthly_expenses=hi,
        liquid_savings=Decimal(0),
        investments=Decimal(0),
        total_assets=Decimal(0),
        total_liabilities=Decimal(0),
        goal_progress=None,
        currency="EUR",
    )
    assert _score(s_lo).fi_number <= _score(s_hi).fi_number


@given(
    st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.10"), places=4),
    st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.10"), places=4),
)
@settings(max_examples=50, deadline=None)
def test_lower_swr_means_a_larger_target(a: Decimal, b: Decimal) -> None:
    """A more conservative withdrawal rate must require a bigger pot."""
    lo, hi = min(a, b), max(a, b)
    s = FinancialSnapshot(
        monthly_income=Decimal("100000"),
        monthly_expenses=Decimal("50000"),
        liquid_savings=Decimal(0),
        investments=Decimal(0),
        total_assets=Decimal(0),
        total_liabilities=Decimal(0),
        goal_progress=None,
        currency="EUR",
    )
    assert _score(s, swr=lo).fi_number >= _score(s, swr=hi).fi_number


@given(
    st.decimals(min_value=Decimal("100"), max_value=Decimal("100000"), places=2),
    st.decimals(min_value=Decimal("100"), max_value=Decimal("100000"), places=2),
)
@settings(max_examples=50, deadline=None)
def test_more_contribution_never_takes_longer(a: Decimal, b: Decimal) -> None:
    lo, hi = min(a, b), max(a, b)
    target = Decimal("10000000")
    y_lo = engine.years_to_target(Decimal(0), lo, Decimal("0.05"), target)
    y_hi = engine.years_to_target(Decimal(0), hi, Decimal("0.05"), target)
    if y_lo is not None and y_hi is not None:
        assert y_hi <= y_lo


# ── Real returns ──────────────────────────────────────────────────────────────


@given(
    st.decimals(min_value=Decimal("0"), max_value=Decimal("0.40"), places=4),
    st.decimals(min_value=Decimal("0"), max_value=Decimal("0.30"), places=4),
)
@settings(max_examples=100, deadline=None)
def test_real_return_never_exceeds_nominal_under_positive_inflation(
    nominal: Decimal, inflation: Decimal
) -> None:
    r = engine.real_return(nominal, inflation)
    if inflation > 0:
        assert r < nominal
    else:
        assert r == nominal


# ── The projected series and the solver must never disagree ────────────────────


@given(snapshot())
@settings(max_examples=50, deadline=None)
def test_projection_crossing_matches_the_solver(s: FinancialSnapshot) -> None:
    score = _score(s, annual_real_return=RATES["base"])
    if score.fi_number <= 0 or score.projected_fi_years is None:
        return
    horizon = int(score.projected_fi_years) + 1
    points = engine.project_portfolio(s, RATES, horizon_years=horizon)
    crossing = next((p.year for p in points if p.base >= score.fi_number), None)
    assert crossing == int(score.projected_fi_years)


@given(snapshot(), st.decimals(min_value=Decimal("0"), max_value=Decimal("0.30"), places=4))
@settings(max_examples=50, deadline=None)
def test_inflation_never_moves_the_real_projection(
    s: FinancialSnapshot, inflation: Decimal
) -> None:
    """The user's inflation only adds future-money figures: the real walk, and
    so the year FI is reached, is exactly the same with it as without."""
    real = engine.project_portfolio(s, RATES, horizon_years=20)
    both = engine.project_portfolio(s, RATES, horizon_years=20, inflation=inflation)
    for r, b in zip(real, both, strict=True):
        assert (r.conservative, r.base, r.growth) == (b.conservative, b.base, b.growth)
        assert b.nominal is not None
        if r.base >= 0:
            # Positive inflation never makes a future amount less money.
            assert b.nominal.base >= r.base.quantize(Decimal("0.01"))


# ── simulate_purchase: costing a decision in months of freedom ────────────────
#
# This output tells a user whether to spend money, so the invariants below are
# the ones that matter: it must never flatter a purchase (report it as free, or
# as bringing FI closer), and its month-resolution answer must reconcile with the
# year-resolution figure the dashboard shows.

purchase = st.decimals(
    min_value=Decimal("1000"),
    max_value=Decimal("5000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


@given(snapshot())
@settings(max_examples=100, deadline=None)
def test_zero_purchase_costs_nothing(s: FinancialSnapshot) -> None:
    """A purchase of nothing must not move the FI date. Guards off-by-one drift."""
    impact = _impact(s, Decimal("0"))
    cash = impact.options[0]
    assert cash.months_to_fi == impact.baseline_months_to_fi
    if impact.baseline_months_to_fi is not None:
        assert cash.months_delay == 0


@given(snapshot(), purchase)
@settings(max_examples=100, deadline=None)
def test_a_purchase_never_brings_fi_closer(s: FinancialSnapshot, amount: Decimal) -> None:
    """Spending money cannot accelerate financial independence."""
    impact = _impact(s, amount)
    for option in impact.options:
        if option.months_delay is not None:
            assert option.months_delay >= 0


@given(snapshot(), purchase, purchase)
@settings(max_examples=100, deadline=None)
def test_bigger_purchases_cost_at_least_as_much(
    s: FinancialSnapshot, a: Decimal, b: Decimal
) -> None:
    """Monotonicity: a larger purchase never delays FI by fewer months."""
    small, large = min(a, b), max(a, b)
    d_small = _impact(s, small).options[0].months_delay
    d_large = _impact(s, large).options[0].months_delay
    if d_small is not None and d_large is not None:
        assert d_large >= d_small


@given(snapshot(), purchase, scale_factor)
@settings(max_examples=100, deadline=None)
def test_months_of_freedom_are_scale_invariant(
    s: FinancialSnapshot, amount: Decimal, k: Decimal
) -> None:
    """
    The unit-bug catcher, applied to the purchase path: scaling every money input
    AND the purchase by k must leave the months-of-freedom answer unchanged. This
    is the property that catches a ×100 slip in the funding comparison.

    Unchanged to the month, give or take one: the walk rounds to cents at each
    year's end, and no scaling preserves rounding, so a value that lands within
    a cent of the target can cross a month apart. A unit slip moves it by years.
    """
    a = _impact(s, amount).options[0].months_delay
    b = _impact(_scaled(s, k), amount * k).options[0].months_delay
    assert (a is None) == (b is None)
    if a is not None and b is not None:
        assert abs(a - b) <= 1


@given(snapshot(), purchase)
@settings(max_examples=100, deadline=None)
def test_month_answer_reconciles_with_the_year_solver(
    s: FinancialSnapshot, amount: Decimal
) -> None:
    """
    The month walk must agree with `years_to_target`, which drives the dashboard.

    `ceil(months / 12) == years` is guaranteed by quantising only at year
    boundaries; if that ever drifts the two surfaces would quote FI dates a year
    apart for the same user — the exact failure the FI audit fixed once already.
    """
    impact = _impact(s, amount)
    if impact.fi_number <= 0:
        return
    surplus = s.monthly_income - s.monthly_expenses
    base = engine.fi_asset_base(s)
    for starting, months in (
        (base, impact.baseline_months_to_fi),
        (base - amount, impact.options[0].months_to_fi),
    ):
        years = engine.years_to_target(starting, surplus, REAL, impact.fi_number)
        if months is None or years is None:
            continue
        assert -(-months // 12) == int(years)


@given(purchase, st.integers(min_value=1, max_value=60))
@settings(max_examples=100, deadline=None)
def test_zero_interest_installments_total_the_price(amount: Decimal, term: int) -> None:
    """
    At 0%, the payments must sum to the price — no phantom interest.

    Compared to the cent, not bit-exactly: the level payment is an exact division
    that often repeats (1000/9 = 111.111…), so full-precision arithmetic lands a
    hair under. The engine keeps that precision internally and quantises at the
    boundary, matching how `_fv_after_months` is used everywhere else here.
    """
    cents = Decimal("0.01")
    payment = engine.installment_payment(amount, Decimal("0"), term)
    assert (payment * term).quantize(cents) == amount.quantize(cents)


@given(purchase, st.integers(min_value=1, max_value=60))
@settings(max_examples=100, deadline=None)
def test_zero_interest_is_never_reported_as_negative(amount: Decimal, term: int) -> None:
    """A 0% plan must show exactly 0.00 interest, never "-0.00"."""
    snap = FinancialSnapshot(
        monthly_income=Decimal("200000"),
        monthly_expenses=Decimal("150000"),
        liquid_savings=Decimal("500000"),
        investments=Decimal("500000"),
        total_assets=Decimal("1000000"),
        total_liabilities=Decimal("0"),
        goal_progress=None,
        currency="EUR",
    )
    impact = _impact(snap, amount, term_months=term, annual_interest_rate=Decimal("0"))
    interest = impact.options[1].interest_cost
    assert interest == 0
    assert not str(interest).startswith("-")


@given(
    purchase,
    st.integers(min_value=2, max_value=60),
    st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.40"), places=4),
)
@settings(max_examples=100, deadline=None)
def test_interest_makes_installments_strictly_dearer(
    amount: Decimal, term: int, rate: Decimal
) -> None:
    """Any positive rate must cost strictly more in total than paying cash."""
    payment = engine.installment_payment(amount, rate, term)
    assert payment * term > amount
    assert payment < amount  # ...but each instalment is smaller than the price


@given(snapshot(), purchase, st.integers(min_value=1, max_value=48))
@settings(max_examples=100, deadline=None)
def test_installments_never_beat_cash_on_total_cost(
    s: FinancialSnapshot, amount: Decimal, term: int
) -> None:
    """Financing is never cheaper in absolute money than paying outright."""
    impact = _impact(s, amount, term_months=term, annual_interest_rate=Decimal("0.18"))
    cash, installments = impact.options[0], impact.options[1]
    assert installments.total_cost > cash.total_cost
    assert installments.interest_cost > 0
