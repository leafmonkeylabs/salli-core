"""
Risk profiling domain models — pure, frozen dataclasses. No I/O.

A structured input (`RiskQuestionnaireAnswers`) and a fully recorded output
(`RiskProfile`, the tolerance) produced by the pure `engine.compute`. The
questionnaire keeps three things apart: tolerance (attitude to loss, scored),
capacity (what the finances can take: the horizon, income stability and
dependents asked here, with the baseline's figures, `capacity.py`) and
experience, recorded but never scored: knowing markets is not wanting risk.
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
    """The tolerance items (`drawdown_reaction` and the 1-5 items of
    `engine.ITEMS`, each optional but the first), the capacity items
    (horizon, income stability, dependents) and experience (not scored)."""

    time_horizon_years: int
    drawdown_reaction: DrawdownReaction
    income_stability: IncomeStability
    investment_experience: InvestmentExperience
    dependents_count: int = 0
    #: Tolerance items on a 1-5 scale (`engine.ITEMS`); None: not answered.
    loss_tolerance: int | None = None
    certainty: int | None = None
    volatility_comfort: int | None = None
    self_rating: int | None = None
    loss_focus: int | None = None
    past_behaviour: int | None = None


@dataclass(frozen=True)
class RiskProfile:
    """The tolerance: attitude only."""

    score: int  # 0..100, over the items answered
    category: RiskCategory
    breakdown: dict[str, int] = field(default_factory=dict[str, int])  # per-item points, 0-4
