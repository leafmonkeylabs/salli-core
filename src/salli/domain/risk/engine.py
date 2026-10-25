"""
Deterministic risk-tolerance scoring. Pure: compute(answers) -> RiskProfile.

Tolerance is attitude to loss and uncertainty only, in the structure of
validated psychometric questionnaires: several items on one scale, each
worth 0-4 points, the score their share of the most they could make over the
items answered (0-100), then bucketed. The horizon, income stability and
dependents are capacity (`capacity.py`), not tolerance; experience is
recorded and never scored. The profile is the lower of tolerance and
capacity, with need (the return a plan requires) beside it.
"""

from __future__ import annotations

from salli.domain.risk.models import RiskCategory, RiskProfile, RiskQuestionnaireAnswers

_DRAWDOWN_POINTS = {"sell_all": 0, "sell_some": 1, "hold": 3, "buy_more": 4}

#: The 1-5 items: the question, and what 1 and 5 mean. A higher answer is
#: more tolerant.
ITEMS: dict[str, str] = {
    "loss_tolerance": "The largest fall in a year you could accept: 1 none, 5 forty per cent or more",
    "certainty": "A sure gain or an uncertain larger one: 1 always the sure one, 5 always the uncertain",
    "volatility_comfort": "Values that swing from month to month: 1 very uncomfortable, 5 at ease",
    "self_rating": "How you see yourself with money: 1 very cautious, 5 very adventurous",
    "loss_focus": "After a decision, what you dwell on: 1 the possible loss, 5 the possible gain",
    "past_behaviour": "In a fall you lived through: 1 sold everything, 5 bought more",
}


def _category(score: int) -> RiskCategory:
    if score < 40:
        return "conservative"
    if score < 70:
        return "balanced"
    return "aggressive"


def check(answers: RiskQuestionnaireAnswers) -> None:
    """A ValueError for an item outside 1-5."""
    for item in ITEMS:
        value = getattr(answers, item)
        if value is not None and not 1 <= value <= 5:
            raise ValueError(f"{item} is answered from 1 to 5")


def compute(answers: RiskQuestionnaireAnswers) -> RiskProfile:
    check(answers)
    breakdown = {"drawdown_reaction": _DRAWDOWN_POINTS[answers.drawdown_reaction]}
    for item in ITEMS:
        value = getattr(answers, item)
        if value is not None:
            breakdown[item] = value - 1
    score = round(sum(breakdown.values()) * 100 / (4 * len(breakdown)))
    return RiskProfile(score=score, category=_category(score), breakdown=breakdown)
