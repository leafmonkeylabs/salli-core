"""
Property-based tests for the FI ("Freedom") engine using Hypothesis.

The headline property here is SCALE INVARIANCE, and it is the one this repo was
missing. Every other engine's property tests assert self-consistency (a trial
balance nets zero, total_gain == value − cost), which holds at *any* scale and so
cannot catch a units error. Multiplying every money input by k must leave the
dimensionless outputs — savings rate, progress, scores — completely unchanged.
A ×100 slip anywhere in the ratio path breaks that immediately.

The engine works in real terms, and takes the withdrawal rate explicitly (the
pack holds none). These properties hold for any such figure; the round one
below stands in for whatever applies to a user.

When FI is reached, and what a purchase costs, are the baseline timeline's
and the scenarios' now (tests/properties/test_scenarios.py): the engine's own
walks and purchase costing, and the properties that held them to each other,
are gone. The instalment maths stays: a scenario's loan is amortised with it.
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


def _score(s: FinancialSnapshot, **over: Any):
    return engine.compute(s, PACK, **{"swr": SWR, **over})


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


# ── The instalment maths a scenario's loan is amortised with ──────────────────

purchase = st.decimals(
    min_value=Decimal("1000"),
    max_value=Decimal("5000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


@given(purchase, st.integers(min_value=1, max_value=60))
@settings(max_examples=100, deadline=None)
def test_zero_interest_installments_total_the_price(amount: Decimal, term: int) -> None:
    """
    At 0%, the payments must sum to the price — no phantom interest.

    Compared to the cent, not bit-exactly: the level payment is an exact division
    that often repeats (1000/9 = 111.111…), so full-precision arithmetic lands a
    hair under. The engine keeps that precision internally and quantises at the
    boundary.
    """
    cents = Decimal("0.01")
    payment = engine.installment_payment(amount, Decimal("0"), term)
    assert (payment * term).quantize(cents) == amount.quantize(cents)


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
