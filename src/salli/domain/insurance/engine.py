"""
Deterministic insurance coverage-gap engine.

Pure function: compute_report(policies, targets, today, expiry_warning_days) ->
CoverageGapReport. No I/O, no wall-clock reads — `today` is passed in.

Coverage per policy type is the sum of active policies' coverage_amount for that
type. A gap line is only produced for policy types the user has declared a target
for (mirroring the budget engine's "only declared categories get a line"
behaviour) — there is no universal "correct" coverage amount to assume otherwise.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from salli.domain.insurance.models import (
    CoverageGapLine,
    CoverageGapReport,
    CoverageTarget,
    ExpiryAlert,
    Policy,
    PolicyType,
)


def compute_report(
    policies: list[Policy],
    targets: list[CoverageTarget],
    today: str,
    expiry_warning_days: int = 30,
) -> CoverageGapReport:
    coverage_by_type: dict[str, Decimal] = {}
    for p in policies:
        if not p.is_active:
            continue
        coverage_by_type[p.policy_type] = (
            coverage_by_type.get(p.policy_type, Decimal(0)) + p.coverage_amount
        )

    lines: list[CoverageGapLine] = []
    missing_types: list[PolicyType] = []
    for target in targets:
        actual = coverage_by_type.get(target.policy_type, Decimal(0))
        lines.append(
            CoverageGapLine(
                policy_type=target.policy_type,
                target_amount=target.target_amount,
                actual_coverage=actual,
                gap=target.target_amount - actual,
            )
        )
        if actual == Decimal(0):
            missing_types.append(target.policy_type)

    today_date = date.fromisoformat(today)
    expiring_soon: list[ExpiryAlert] = []
    for p in policies:
        if not p.is_active:
            continue
        days_until = (date.fromisoformat(p.expiry_date) - today_date).days
        if 0 <= days_until <= expiry_warning_days:
            expiring_soon.append(
                ExpiryAlert(
                    policy_name=p.name,
                    policy_type=p.policy_type,
                    expiry_date=p.expiry_date,
                    days_until_expiry=days_until,
                )
            )

    return CoverageGapReport(
        lines=lines,
        missing_types=missing_types,
        expiring_soon=expiring_soon,
    )
