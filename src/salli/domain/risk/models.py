"""
Risk profiling domain models — pure, frozen dataclasses. No I/O.

Mirrors the tax/fi domains: a structured input (`RiskQuestionnaireAnswers`) and a
fully-recorded output (`RiskProfile`) produced by the pure `engine.compute` function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DrawdownReaction = Literal["sell_all", "sell_some", "hold", "buy_more"]
IncomeStability = Literal["unstable", "moderate", "stable"]
InvestmentExperience = Literal["none", "some", "experienced"]
RiskCategory = Literal["conservative", "balanced", "aggressive"]


@dataclass(frozen=True)
class RiskQuestionnaireAnswers:
    """Standard risk-tolerance dimensions: horizon, loss reaction, income stability,
    experience, and dependents (a higher dependents count pulls toward caution)."""

    time_horizon_years: int
    drawdown_reaction: DrawdownReaction
    income_stability: IncomeStability
    investment_experience: InvestmentExperience
    dependents_count: int = 0


@dataclass(frozen=True)
class RiskProfile:
    score: int  # 0..100
    category: RiskCategory
    breakdown: dict[str, int] = field(default_factory=dict[str, int])  # per-dimension points
