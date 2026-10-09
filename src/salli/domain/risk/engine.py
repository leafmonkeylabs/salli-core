"""
Deterministic risk-tolerance scoring engine.

Pure function: compute(answers) -> RiskProfile. No I/O, no LLM.

Methodology: five standard risk-tolerance dimensions each contribute points toward a
0-100 score, which is then bucketed into a category.
  • Time horizon          — longer horizons tolerate more volatility (0-20)
  • Drawdown reaction      — how the user reacts to a hypothetical portfolio drop (0-25)
  • Income stability       — steadier income affords more risk-taking (0-20)
  • Investment experience  — more experience, more tolerance (0-20)
  • Dependents             — more dependents pulls toward caution (0-15)
"""

from __future__ import annotations

from salli.domain.risk.models import RiskCategory, RiskProfile, RiskQuestionnaireAnswers

_DRAWDOWN_POINTS = {"sell_all": 0, "sell_some": 8, "hold": 18, "buy_more": 25}
_INCOME_STABILITY_POINTS = {"unstable": 5, "moderate": 12, "stable": 20}
_EXPERIENCE_POINTS = {"none": 3, "some": 10, "experienced": 20}


def _time_horizon_points(years: int) -> int:
    if years >= 15:
        return 20
    if years >= 10:
        return 15
    if years >= 5:
        return 10
    if years >= 2:
        return 5
    return 0


def _dependents_points(count: int) -> int:
    if count <= 0:
        return 15
    if count <= 2:
        return 8
    return 0


def _category(score: int) -> RiskCategory:
    if score < 40:
        return "conservative"
    if score < 70:
        return "balanced"
    return "aggressive"


def compute(answers: RiskQuestionnaireAnswers) -> RiskProfile:
    breakdown = {
        "time_horizon": _time_horizon_points(answers.time_horizon_years),
        "drawdown_reaction": _DRAWDOWN_POINTS[answers.drawdown_reaction],
        "income_stability": _INCOME_STABILITY_POINTS[answers.income_stability],
        "investment_experience": _EXPERIENCE_POINTS[answers.investment_experience],
        "dependents": _dependents_points(answers.dependents_count),
    }
    score = sum(breakdown.values())
    return RiskProfile(score=score, category=_category(score), breakdown=breakdown)
