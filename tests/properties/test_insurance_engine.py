"""
Property-based tests for the insurance coverage-gap engine using Hypothesis.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from salli.domain.insurance.engine import compute_report
from salli.domain.insurance.models import CoverageTarget, Policy

_POLICY_TYPES = ["life", "health", "motor", "property", "other"]
_TODAY = "2026-07-16"

money_amount = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("10_000_000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


@st.composite
def policy(draw: Any, name: str) -> Policy:
    policy_type = draw(st.sampled_from(_POLICY_TYPES))
    coverage = draw(money_amount)
    is_active = draw(st.booleans())
    expiry_offset = draw(st.integers(min_value=-365, max_value=365))
    expiry_date = (date.fromisoformat(_TODAY) + timedelta(days=expiry_offset)).isoformat()
    return Policy(
        name=name,
        policy_type=policy_type,  # type: ignore[arg-type]
        provider="Test Insurer",
        coverage_amount=coverage,
        premium_amount=Decimal("1000"),
        premium_frequency="monthly",
        expiry_date=expiry_date,
        is_active=is_active,
    )


@st.composite
def policies_list(draw: Any) -> list[Policy]:
    count = draw(st.integers(min_value=0, max_value=8))
    return [draw(policy(f"P{i}")) for i in range(count)]


@st.composite
def targets_list(draw: Any) -> list[CoverageTarget]:
    chosen_types = draw(
        st.lists(st.sampled_from(_POLICY_TYPES), min_size=0, max_size=5, unique=True)
    )
    return [
        CoverageTarget(policy_type=t, target_amount=draw(money_amount))  # type: ignore[arg-type]
        for t in chosen_types
    ]


@given(policies=policies_list(), targets=targets_list())
@settings(max_examples=200)
def test_gap_equals_target_minus_actual(policies: list[Policy], targets: list[CoverageTarget]):
    report = compute_report(policies, targets, today=_TODAY)
    for line in report.lines:
        assert line.gap == line.target_amount - line.actual_coverage


@given(policies=policies_list(), targets=targets_list())
@settings(max_examples=200)
def test_actual_coverage_matches_hand_summed_active_policies(
    policies: list[Policy], targets: list[CoverageTarget]
):
    report = compute_report(policies, targets, today=_TODAY)
    for line in report.lines:
        expected = sum(
            (
                p.coverage_amount
                for p in policies
                if p.is_active and p.policy_type == line.policy_type
            ),
            Decimal(0),
        )
        assert line.actual_coverage == expected


@given(policies=policies_list(), targets=targets_list())
@settings(max_examples=200)
def test_missing_types_only_when_actual_coverage_is_zero(
    policies: list[Policy], targets: list[CoverageTarget]
):
    report = compute_report(policies, targets, today=_TODAY)
    lines_by_type = {line.policy_type: line for line in report.lines}
    for missing in report.missing_types:
        assert lines_by_type[missing].actual_coverage == Decimal(0)
    for line in report.lines:
        if line.actual_coverage == Decimal(0):
            assert line.policy_type in report.missing_types


@given(policies=policies_list())
@settings(max_examples=200)
def test_expiring_soon_only_contains_active_policies_within_window(policies: list[Policy]):
    report = compute_report(policies, [], today=_TODAY, expiry_warning_days=30)
    active_names = {p.name for p in policies if p.is_active}
    for alert in report.expiring_soon:
        assert alert.policy_name in active_names
        assert 0 <= alert.days_until_expiry <= 30


@given(policies=policies_list())
@settings(max_examples=200)
def test_expiring_soon_days_until_expiry_matches_actual_date_diff(policies: list[Policy]):
    report = compute_report(policies, [], today=_TODAY, expiry_warning_days=30)
    by_name = {p.name: p for p in policies}
    today_date = date.fromisoformat(_TODAY)
    for alert in report.expiring_soon:
        p = by_name[alert.policy_name]
        expected_days = (date.fromisoformat(p.expiry_date) - today_date).days
        assert alert.days_until_expiry == expected_days
