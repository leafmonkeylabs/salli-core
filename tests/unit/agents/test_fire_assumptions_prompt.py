"""The FIRE strategy and the advisor say which planning assumptions they built
on, and never pass a default off as a forecast."""

from __future__ import annotations

from salli.domain.agents.advisor import ADVISOR_PROMPT
from salli.domain.agents.fire_strategy import FIRE_SYSTEM_PROMPT


def test_the_strategy_builds_on_the_assumptions_and_names_them():
    for phrase in (
        "`assumptions`",
        "`origin`",
        "consistent with that inflation",
        "Keep to any assumption whose origin is `user`",
        "say which assumptions you built on and where each came from",
        "never forecasts",
    ):
        assert phrase in FIRE_SYSTEM_PROMPT, phrase


def test_the_advisor_never_passes_a_default_off_as_a_forecast():
    assert "`assumptions`" in ADVISOR_PROMPT
    assert "Never present a default as a forecast" in ADVISOR_PROMPT
