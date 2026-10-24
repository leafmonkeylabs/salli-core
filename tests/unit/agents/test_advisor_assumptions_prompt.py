"""The advisor works in real terms, says which planning assumptions it built
on, and never passes a placeholder off as a forecast."""

from __future__ import annotations

from salli.domain.agents.advisor import ADVISOR_PROMPT


def test_the_advisor_never_passes_a_placeholder_off_as_a_forecast():
    assert "`assumptions`" in ADVISOR_PROMPT
    assert "real terms" in ADVISOR_PROMPT
    assert "Never present a placeholder as a forecast" in ADVISOR_PROMPT
    assert "`assumptions.status` is `placeholder`" in ADVISOR_PROMPT
