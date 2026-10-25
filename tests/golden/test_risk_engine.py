"""
Golden tests for the risk-tolerance scoring engine.

Hand-scored questionnaires against the rubric in `domain/risk/engine.py`:
each tolerance item 0-4 points, the score their share of the most they could
make over the items answered. Horizon, income and dependents are capacity,
and experience is never scored.
"""

import pytest

from salli.domain.risk.engine import compute
from salli.domain.risk.models import RiskQuestionnaireAnswers


def _answers(**items: object) -> RiskQuestionnaireAnswers:
    base: dict[str, object] = {
        "time_horizon_years": 10,
        "drawdown_reaction": "hold",
        "income_stability": "stable",
        "investment_experience": "some",
    }
    return RiskQuestionnaireAnswers(**{**base, **items})  # type: ignore[arg-type]


def test_all_cautious_answers_score_conservative():
    # 0 (sell_all) + 0 × 6 = 0 of 28.
    result = compute(
        _answers(
            drawdown_reaction="sell_all",
            loss_tolerance=1,
            certainty=1,
            volatility_comfort=1,
            self_rating=1,
            loss_focus=1,
            past_behaviour=1,
        )
    )
    assert result.score == 0
    assert result.category == "conservative"


def test_middling_answers_score_balanced():
    # 3 (hold) + 2 + 2 + 2 + 2 + 2 + 2 = 15 of 28 → 54.
    result = compute(
        _answers(
            loss_tolerance=3,
            certainty=3,
            volatility_comfort=3,
            self_rating=3,
            loss_focus=3,
            past_behaviour=3,
        )
    )
    assert result.score == 54
    assert result.category == "balanced"


def test_all_tolerant_answers_score_aggressive():
    result = compute(
        _answers(
            drawdown_reaction="buy_more",
            loss_tolerance=5,
            certainty=5,
            volatility_comfort=5,
            self_rating=5,
            loss_focus=5,
            past_behaviour=5,
        )
    )
    assert result.score == 100
    assert result.category == "aggressive"


def test_experience_and_capacity_answers_never_move_tolerance():
    one = compute(_answers(investment_experience="none", time_horizon_years=1, dependents_count=4))
    other = compute(
        _answers(investment_experience="experienced", time_horizon_years=30, dependents_count=0)
    )
    assert one == other


def test_the_score_is_over_the_items_answered():
    # hold (3) + 4 = 7 of 8.
    assert compute(_answers(loss_tolerance=5)).score == 88


def test_an_item_outside_one_to_five_is_refused():
    with pytest.raises(ValueError, match="1 to 5"):
        compute(_answers(certainty=6))
