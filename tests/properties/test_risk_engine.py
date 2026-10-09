"""
Property-based tests for the risk-scoring engine using Hypothesis.

Proves the score is monotonic in the conservative -> aggressive direction along each
dimension independently, holding the others fixed.
"""

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from salli.domain.risk.engine import compute
from salli.domain.risk.models import RiskQuestionnaireAnswers

_DRAWDOWN_ORDER = ["sell_all", "sell_some", "hold", "buy_more"]
_INCOME_ORDER = ["unstable", "moderate", "stable"]
_EXPERIENCE_ORDER = ["none", "some", "experienced"]

base_answers = st.fixed_dictionaries(
    {
        "time_horizon_years": st.integers(min_value=0, max_value=40),
        "drawdown_reaction": st.sampled_from(_DRAWDOWN_ORDER),
        "income_stability": st.sampled_from(_INCOME_ORDER),
        "investment_experience": st.sampled_from(_EXPERIENCE_ORDER),
        "dependents_count": st.integers(min_value=0, max_value=10),
    }
)


def _make(data: dict[str, Any]) -> RiskQuestionnaireAnswers:
    return RiskQuestionnaireAnswers(**data)


@given(data=base_answers, more_years=st.integers(min_value=0, max_value=40))
def test_longer_horizon_never_lowers_score(data: dict[str, Any], more_years: int):
    lower = _make(data)
    higher = _make({**data, "time_horizon_years": data["time_horizon_years"] + more_years})
    assert compute(higher).score >= compute(lower).score


@given(data=base_answers, steps=st.integers(min_value=0, max_value=3))
def test_calmer_drawdown_reaction_never_lowers_score(data: dict[str, Any], steps: int):
    start = _DRAWDOWN_ORDER.index(data["drawdown_reaction"])
    end = min(len(_DRAWDOWN_ORDER) - 1, start + steps)
    lower = _make(data)
    higher = _make({**data, "drawdown_reaction": _DRAWDOWN_ORDER[end]})
    assert compute(higher).score >= compute(lower).score


@given(data=base_answers, steps=st.integers(min_value=0, max_value=2))
def test_steadier_income_never_lowers_score(data: dict[str, Any], steps: int):
    start = _INCOME_ORDER.index(data["income_stability"])
    end = min(len(_INCOME_ORDER) - 1, start + steps)
    lower = _make(data)
    higher = _make({**data, "income_stability": _INCOME_ORDER[end]})
    assert compute(higher).score >= compute(lower).score


@given(data=base_answers, steps=st.integers(min_value=0, max_value=2))
def test_more_experience_never_lowers_score(data: dict[str, Any], steps: int):
    start = _EXPERIENCE_ORDER.index(data["investment_experience"])
    end = min(len(_EXPERIENCE_ORDER) - 1, start + steps)
    lower = _make(data)
    higher = _make({**data, "investment_experience": _EXPERIENCE_ORDER[end]})
    assert compute(higher).score >= compute(lower).score


@given(data=base_answers, more_dependents=st.integers(min_value=0, max_value=10))
def test_more_dependents_never_raises_score(data: dict[str, Any], more_dependents: int):
    lower = _make(data)
    higher = _make({**data, "dependents_count": data["dependents_count"] + more_dependents})
    assert compute(higher).score <= compute(lower).score


@given(data=base_answers)
def test_score_is_always_in_bounds(data: dict[str, Any]):
    result = compute(_make(data))
    assert 0 <= result.score <= 100


@given(data=base_answers)
def test_category_matches_documented_thresholds(data: dict[str, Any]):
    result = compute(_make(data))
    if result.score < 40:
        assert result.category == "conservative"
    elif result.score < 70:
        assert result.category == "balanced"
    else:
        assert result.category == "aggressive"
