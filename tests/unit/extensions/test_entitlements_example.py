"""examples/entitlements: tiers shape only by leaving parts out, and say so."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from salli.application.ports import Surface

_PATH = Path(__file__).parents[3] / "examples" / "entitlements" / "policy.py"
_spec = importlib.util.spec_from_file_location("entitlements_example", _PATH)
assert _spec and _spec.loader
policy = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = policy  # its dataclasses look themselves up
_spec.loader.exec_module(policy)

PROJECTIONS = {"currency": "EUR", "points": [{"year": y} for y in range(30)]}
BRIEFING = {"summary": "A quiet month.", "notes": [{"text": "x"}], "figures": {}}


async def _tier(name: str | None):
    async def tier_of(user_id: str) -> str | None:
        return name

    return await policy.TierPolicy(tier_of).for_user("u1")


async def test_a_paying_or_pilot_tier_sees_everything():
    for name in (
        "self_hosted",
        "pilot",
        "hosted_person",
        "hosted_household",
        "practice",
        "developer",
    ):
        view = await _tier(name)
        assert view.shape(Surface.FI_PROJECTIONS, PROJECTIONS) == PROJECTIONS
        assert view.shape(Surface.ADVISOR_REPORT, BRIEFING) == BRIEFING


async def test_a_trial_leaves_parts_out_and_says_which():
    for name in ("trial", None, "unknown"):
        view = await _tier(name)
        shaped = view.shape(Surface.FI_PROJECTIONS, PROJECTIONS)
        assert shaped["points"] == PROJECTIONS["points"][:5] and shaped["withheld"] == ["points"]
        brief = view.shape(Surface.ADVISOR_REPORT, BRIEFING)
        assert "notes" not in brief and brief["summary"] == BRIEFING["summary"]
    assert len(PROJECTIONS["points"]) == 30  # the payload itself is never changed


def test_every_tier_names_the_thesis_row_it_tests():
    thesis = (Path(__file__).parents[3] / "business" / "thesis.md").read_text()
    for tier in policy.TIERS.values():
        assert tier.tests.split(":")[0] in thesis
