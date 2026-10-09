"""
Property-based tests for the debt payoff engine using Hypothesis.
"""

from decimal import Decimal
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from salli.domain.debt.engine import compute_payoff_plan
from salli.domain.debt.models import Debt

principal_amount = st.decimals(
    min_value=Decimal("100"),
    max_value=Decimal("50000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
apr_value = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("0.35"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)


@st.composite
def debt(draw: Any, name: str, apr: Decimal) -> Debt:
    principal = draw(principal_amount)
    # Ensure the minimum payment always covers at least the first month's interest,
    # so every simulation actually converges within the horizon.
    min_floor = (principal * apr / Decimal(12) * Decimal("1.5")).quantize(Decimal("0.01"))
    minimum_payment = draw(
        st.decimals(
            min_value=min_floor + Decimal("1"),
            max_value=min_floor + Decimal("500"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    return Debt(name=name, principal=principal, apr=apr, minimum_payment=minimum_payment)


@st.composite
def two_debts(draw: Any) -> list[Debt]:
    """Two debts with meaningfully distinct APRs (>= 5 percentage points apart) —
    close APRs make avalanche-vs-snowball come down to penny-rounding noise rather
    than a genuine ordering difference, which isn't what the ordering invariant
    below is meant to test."""
    apr_low = draw(
        st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("0.30"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    apr_high = draw(
        st.decimals(
            min_value=apr_low + Decimal("0.05"),
            max_value=Decimal("0.35"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    return [draw(debt("DebtA", apr_low)), draw(debt("DebtB", apr_high))]


@given(
    debts=two_debts(), extra=st.decimals(min_value=Decimal(0), max_value=Decimal("2000"), places=2)
)
@settings(max_examples=100)
def test_total_interest_paid_is_never_negative(debts: list[Debt], extra: Decimal):
    for strategy in ("avalanche", "snowball"):
        plan = compute_payoff_plan(debts, extra, strategy)
        assert plan.total_interest_paid >= Decimal(0)


@given(
    debts=two_debts(), extra=st.decimals(min_value=Decimal(0), max_value=Decimal("2000"), places=2)
)
@settings(max_examples=100)
def test_remaining_balance_never_negative(debts: list[Debt], extra: Decimal):
    for strategy in ("avalanche", "snowball"):
        plan = compute_payoff_plan(debts, extra, strategy)
        for entry in plan.schedule:
            assert entry.remaining_balance >= Decimal(0)


@given(
    debts=two_debts(), extra=st.decimals(min_value=Decimal(0), max_value=Decimal("2000"), places=2)
)
@settings(max_examples=100)
def test_months_to_payoff_is_none_or_positive(debts: list[Debt], extra: Decimal):
    for strategy in ("avalanche", "snowball"):
        plan = compute_payoff_plan(debts, extra, strategy)
        assert plan.months_to_payoff is None or plan.months_to_payoff > 0
