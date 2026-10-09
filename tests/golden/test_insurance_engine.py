"""
Golden tests for the insurance coverage-gap engine — hand-computed scenarios.
"""

from decimal import Decimal

from salli.domain.insurance.engine import compute_report
from salli.domain.insurance.models import CoverageTarget, Policy


def _policy(
    name: str, policy_type: str, coverage: str, expiry: str, is_active: bool = True
) -> Policy:
    return Policy(
        name=name,
        policy_type=policy_type,  # type: ignore[arg-type]
        provider="Test Insurer",
        coverage_amount=Decimal(coverage),
        premium_amount=Decimal("1000"),
        premium_frequency="monthly",
        expiry_date=expiry,
        is_active=is_active,
    )


# ── Case 1: coverage meets target — gap is zero/negative, not under-covered ────


def test_coverage_meets_target_produces_no_gap():
    policies = [_policy("Life Basic", "life", "5000000", "2027-01-01")]
    targets = [CoverageTarget(policy_type="life", target_amount=Decimal("5000000"))]

    report = compute_report(policies, targets, today="2026-07-16")

    assert len(report.lines) == 1
    assert report.lines[0].gap == Decimal(0)
    assert report.missing_types == []


# ── Case 2: coverage under target — positive gap ────────────────────────────────


def test_coverage_under_target_produces_positive_gap():
    policies = [_policy("Life Basic", "life", "2000000", "2027-01-01")]
    targets = [CoverageTarget(policy_type="life", target_amount=Decimal("5000000"))]

    report = compute_report(policies, targets, today="2026-07-16")

    assert report.lines[0].actual_coverage == Decimal("2000000")
    assert report.lines[0].gap == Decimal("3000000")
    assert report.missing_types == []


# ── Case 3: no policy at all for a declared target type — missing_types ────────


def test_no_policy_for_declared_target_is_missing():
    targets = [CoverageTarget(policy_type="health", target_amount=Decimal("1000000"))]

    report = compute_report([], targets, today="2026-07-16")

    assert report.lines[0].actual_coverage == Decimal(0)
    assert report.missing_types == ["health"]


# ── Case 4: multiple active policies of the same type sum together ─────────────


def test_multiple_policies_same_type_sum_coverage():
    policies = [
        _policy("Life A", "life", "1000000", "2027-01-01"),
        _policy("Life B", "life", "1500000", "2027-06-01"),
    ]
    targets = [CoverageTarget(policy_type="life", target_amount=Decimal("2000000"))]

    report = compute_report(policies, targets, today="2026-07-16")

    assert report.lines[0].actual_coverage == Decimal("2500000")
    assert report.lines[0].gap == Decimal("-500000")


# ── Case 5: inactive policies don't count toward coverage ───────────────────────


def test_inactive_policy_excluded_from_coverage():
    policies = [
        _policy("Life Lapsed", "life", "5000000", "2026-08-01", is_active=False),
    ]
    targets = [CoverageTarget(policy_type="life", target_amount=Decimal("1000000"))]

    report = compute_report(policies, targets, today="2026-07-16")

    assert report.lines[0].actual_coverage == Decimal(0)
    assert report.missing_types == ["life"]


# ── Case 6: expiring-soon alert fires within the warning window ────────────────


def test_expiring_soon_alert_within_window():
    policies = [_policy("Motor Policy", "motor", "800000", "2026-08-01")]

    report = compute_report(policies, [], today="2026-07-16", expiry_warning_days=30)

    assert len(report.expiring_soon) == 1
    assert report.expiring_soon[0].policy_name == "Motor Policy"
    assert report.expiring_soon[0].days_until_expiry == 16


# ── Case 7: expiry far in the future does not alert ─────────────────────────────


def test_expiry_far_in_future_does_not_alert():
    policies = [_policy("Property Policy", "property", "10000000", "2030-01-01")]

    report = compute_report(policies, [], today="2026-07-16", expiry_warning_days=30)

    assert report.expiring_soon == []


# ── Case 8: already-expired policy does not alert (past due, not "soon") ───────


def test_already_expired_policy_does_not_alert():
    policies = [_policy("Health Policy", "health", "3000000", "2026-01-01")]

    report = compute_report(policies, [], today="2026-07-16", expiry_warning_days=30)

    assert report.expiring_soon == []
