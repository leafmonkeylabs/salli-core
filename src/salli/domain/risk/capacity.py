"""
Risk capacity: how much loss a household's finances can take, beside how much
the person says they can stomach (tolerance, engine.py). Pure: figures in,
a profile out.

Four measures from the baseline, each worth 0-25 points:
  • Emergency months  — cash and savings ÷ average monthly spending
  • Income stability  — how much monthly income varies (its coefficient of
                        variation over the months observed; three at least)
  • Horizon           — years until the money is needed
  • Debt service      — scheduled debt payments ÷ monthly income
A measure that can't be had is left out and named, and the score is scaled
over the rest. The profile is the lower of tolerance and capacity. It gates
nothing: it is shown beside allocation checks, and an investment policy whose
equity target is above the profile's band is flagged.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from salli.domain.risk.models import RiskCategory

_ORDER: dict[RiskCategory, int] = {"conservative": 0, "balanced": 1, "aggressive": 2}

#: The most of a portfolio in equity each profile is described as suited to.
#: Part of Salli's method, not any country's or product's figure.
EQUITY_BANDS: dict[RiskCategory, Decimal] = {
    "conservative": Decimal("0.40"),
    "balanced": Decimal("0.70"),
    "aggressive": Decimal("1.00"),
}


@dataclass(frozen=True)
class RiskCapacity:
    score: int  # 0..100, over the measures present
    category: RiskCategory
    breakdown: dict[str, int] = field(default_factory=dict[str, int])
    #: Measures left out for want of figures.
    missing: tuple[str, ...] = ()


def _tiers(value: Decimal, steps: Sequence[tuple[Decimal, int]], rest: int) -> int:
    for bound, points in steps:
        if value >= bound:
            return points
    return rest


def _category(score: int) -> RiskCategory:
    if score < 40:
        return "conservative"
    if score < 70:
        return "balanced"
    return "aggressive"


def income_variation(incomes: Sequence[Decimal]) -> Decimal | None:
    """Monthly income's standard deviation ÷ its mean; None under three
    months or with no income."""
    if len(incomes) < 3:
        return None
    mean = sum(incomes, Decimal(0)) / len(incomes)
    if mean <= 0:
        return None
    variance = sum(((i - mean) ** 2 for i in incomes), Decimal(0)) / len(incomes)
    return variance.sqrt() / mean


def compute(
    emergency_months: Decimal | None,
    income_variation: Decimal | None,
    horizon_years: int | None,
    debt_service: Decimal | None,
) -> RiskCapacity:
    breakdown: dict[str, int] = {}
    missing: list[str] = []
    if emergency_months is None:
        missing.append("emergency_months")
    else:
        breakdown["emergency_months"] = _tiers(
            emergency_months, [(Decimal(6), 25), (Decimal(3), 15), (Decimal(1), 5)], 0
        )
    if income_variation is None:
        missing.append("income_stability")
    else:
        breakdown["income_stability"] = _tiers(
            -income_variation,
            [(Decimal("-0.10"), 25), (Decimal("-0.25"), 15), (Decimal("-0.50"), 8)],
            0,
        )
    if horizon_years is None:
        missing.append("horizon")
    else:
        breakdown["horizon"] = _tiers(
            Decimal(horizon_years), [(Decimal(15), 25), (Decimal(10), 20), (Decimal(5), 12)], 0
        ) or (5 if horizon_years >= 2 else 0)
    if debt_service is None:
        missing.append("debt_service")
    else:
        breakdown["debt_service"] = _tiers(
            -debt_service,
            [(Decimal("-0.10"), 25), (Decimal("-0.20"), 18), (Decimal("-0.35"), 8)],
            0,
        )
    score = round(sum(breakdown.values()) * 100 / (25 * len(breakdown))) if breakdown else 0
    return RiskCapacity(score, _category(score), breakdown, tuple(missing))


def profile(tolerance: RiskCategory | None, capacity: RiskCategory) -> RiskCategory:
    """The lower of the two; capacity alone when tolerance is unknown."""
    if tolerance is None:
        return capacity
    return min(tolerance, capacity, key=_ORDER.__getitem__)
