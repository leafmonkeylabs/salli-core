"""
The advisor's gather step reads and never writes: it used to store an FI
score every time it computed one. Its run, which writes a report, records the
score it advised on.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from salli.application.services.advisor_service import AdvisorService
from salli.application.services.baseline_service import BaselineService
from salli.application.services.fi_service import FiService
from tests.golden import household as h

pytestmark = pytest.mark.asyncio


def _advisor(uow, monkeypatch) -> AdvisorService:
    today = lambda: h.AS_OF  # noqa: E731
    fi = FiService(
        uow.factory(),
        baselines=BaselineService(uow.factory(), fx=h.fx(), today=today),
        today=today,
    )
    advisor = AdvisorService(uow.factory(), fi, SimpleNamespace(charge=AsyncMock()))
    monkeypatch.setattr(advisor, "_research_rates", AsyncMock(return_value=""))
    return advisor


async def test_gathering_the_context_stores_no_score(monkeypatch):
    uow = h.uow()
    context = await _advisor(uow, monkeypatch).gather_context(h.USER)

    assert uow.fi_scores.rows == []
    # 1b: was 2043-03 (197 months): FI's month is the baseline timeline's
    # now (tests/golden/test_household_fi.py says why).
    assert context["fi_score"]["projected_fi_month"] == "2047-05"
    assert context["fire_projections"]["fi_by"]["base"] == {"months": 247, "month": "2047-05"}


async def test_a_run_records_the_score_it_advised_on(monkeypatch):
    from salli.domain.agents import advisor as advisor_llm

    uow = h.uow()
    advisor = _advisor(uow, monkeypatch)
    advice = SimpleNamespace(summary="Keep going.", fire_tier_assessment="", recommendations=[])
    monkeypatch.setattr(advisor_llm, "generate_advice", AsyncMock(return_value=advice))
    monkeypatch.setattr(advisor, "llm_for", AsyncMock(return_value=object()))

    report = await advisor.run_advisor(h.USER)

    assert report["summary"] == "Keep going."
    [score] = uow.fi_scores.rows
    assert (score["overall_score"], score["as_of"]) == ("60.08", "2026-10-11")
