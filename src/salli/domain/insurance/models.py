"""
Insurance domain models — pure, frozen dataclasses, Decimal money. No I/O.

Mirrors the budget domain's declared-vs-actual shape: a `CoverageTarget` is a
declared desired coverage amount per policy type (analogous to a budget line's
limit), and the engine compares it against the sum of active policies' coverage
for that type. Policy inventory (motor/property/other) with no declared target
is tracked for expiry alerts only — there is no universally "correct" coverage
amount for those types the way there might be for life/health, so no gap is
computed unless the user declares one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

PolicyType = Literal["life", "health", "motor", "property", "other"]
PremiumFrequency = Literal["monthly", "quarterly", "yearly"]


@dataclass(frozen=True)
class Policy:
    """A declared insurance policy — the input side, before a gap report is computed."""

    name: str
    policy_type: PolicyType
    provider: str
    coverage_amount: Decimal
    premium_amount: Decimal
    premium_frequency: PremiumFrequency
    expiry_date: str  # YYYY-MM-DD
    is_active: bool = True


@dataclass(frozen=True)
class CoverageTarget:
    """A declared desired coverage amount for a policy type — the input side,
    before actual coverage is aggregated."""

    policy_type: PolicyType
    target_amount: Decimal


@dataclass(frozen=True)
class CoverageGapLine:
    policy_type: PolicyType
    target_amount: Decimal
    actual_coverage: Decimal
    gap: Decimal  # target - actual; positive means under-covered


@dataclass(frozen=True)
class ExpiryAlert:
    policy_name: str
    policy_type: PolicyType
    expiry_date: str
    days_until_expiry: int


@dataclass(frozen=True)
class CoverageGapReport:
    lines: list[CoverageGapLine] = field(default_factory=list[CoverageGapLine])
    missing_types: list[PolicyType] = field(default_factory=list[PolicyType])
    expiring_soon: list[ExpiryAlert] = field(default_factory=list[ExpiryAlert])
