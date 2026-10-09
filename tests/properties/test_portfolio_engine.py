"""
Property-based tests for the investment portfolio engine using Hypothesis.
"""

from decimal import Decimal
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from salli.domain.portfolio.engine import compute_summary
from salli.domain.portfolio.models import Holding

_ASSET_CLASSES = ["equity", "bond", "cash", "real_estate", "crypto"]

money_amount = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1_000_000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


@st.composite
def holding(draw: Any, symbol: str) -> Holding:
    asset_class = draw(st.sampled_from(_ASSET_CLASSES))
    cost_basis = draw(money_amount)
    current_value = draw(money_amount)
    return Holding(
        symbol=symbol,
        name=symbol,
        asset_class=asset_class,
        cost_basis=cost_basis,
        current_value=current_value,
    )


@st.composite
def holdings_list(draw: Any) -> list[Holding]:
    count = draw(st.integers(min_value=0, max_value=6))
    return [draw(holding(f"H{i}")) for i in range(count)]


@given(holdings=holdings_list())
@settings(max_examples=200)
def test_total_gain_equals_value_minus_cost_basis(holdings: list[Holding]):
    summary = compute_summary(holdings)
    assert summary.total_gain == summary.total_value - summary.total_cost_basis


@given(holdings=holdings_list())
@settings(max_examples=200)
def test_allocation_percentages_sum_to_one_when_total_value_positive(holdings: list[Holding]):
    summary = compute_summary(holdings)
    if summary.total_value > 0:
        total_pct = sum((a.pct_of_portfolio for a in summary.allocation), Decimal(0))
        # Each slice is independently rounded to 4dp, so the sum can be off by a
        # few ten-thousandths — bounded by the number of slices being summed.
        assert abs(total_pct - Decimal(1)) <= Decimal("0.0001") * len(summary.allocation)


@given(holdings=holdings_list())
@settings(max_examples=200)
def test_allocation_current_values_sum_to_total_value(holdings: list[Holding]):
    summary = compute_summary(holdings)
    assert sum((a.current_value for a in summary.allocation), Decimal(0)) == summary.total_value


@given(
    holdings=holdings_list(),
    target=st.dictionaries(
        st.sampled_from(_ASSET_CLASSES),
        st.decimals(
            min_value=Decimal(0),
            max_value=Decimal(1),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=1,
        max_size=len(_ASSET_CLASSES),
    ),
)
@settings(max_examples=200)
def test_alerts_only_appear_when_drift_meets_threshold(
    holdings: list[Holding], target: dict[str, Decimal]
):
    threshold = Decimal("0.05")
    summary = compute_summary(holdings, target_allocation=target, drift_threshold=threshold)
    for alert in summary.alerts:
        assert abs(alert.drift_pct) >= threshold - Decimal("0.0001")  # rounding tolerance
