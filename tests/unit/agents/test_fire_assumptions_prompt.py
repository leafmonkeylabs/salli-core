"""The FIRE strategy and the advisor work in real terms, say which planning
assumptions they built on, and never pass a placeholder off as a forecast."""

from __future__ import annotations

from salli.domain.agents.advisor import ADVISOR_PROMPT
from salli.domain.agents.fire_strategy import FIRE_SYSTEM_PROMPT, FireStrategySchema


def test_the_strategy_builds_on_the_assumptions_and_names_them():
    for phrase in (
        "REAL terms",
        "`assumptions`",
        "`origin`",
        "`placeholder`",
        "three REAL yearly returns",
        "after inflation: never",
        "Keep to any assumption whose origin is `user`",
        "say which assumptions you built on and where each came from",
        "suggest the user set their own figures, with sources",
    ):
        assert phrase in FIRE_SYSTEM_PROMPT, phrase


def test_the_strategy_chooses_real_returns_within_plausible_bounds():
    fields = FireStrategySchema.model_fields
    assert {"real_return_conservative", "real_return_base", "real_return_growth"} <= set(fields)
    assert not {"return_conservative", "return_base", "return_growth"} & set(fields)
    assert "REAL" in (fields["real_return_base"].description or "")


def test_the_advisor_never_passes_a_placeholder_off_as_a_forecast():
    assert "`assumptions`" in ADVISOR_PROMPT
    assert "real terms" in ADVISOR_PROMPT
    assert "Never present a placeholder as a forecast" in ADVISOR_PROMPT
    assert "`assumptions.status` is `placeholder`" in ADVISOR_PROMPT
