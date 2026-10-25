"""
The briefing's gather step reads and never writes: it used to store an FI
score every time it computed one. Its run, which writes a report, records the
score it described.
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
    return AdvisorService(uow.factory(), fi, SimpleNamespace(charge=AsyncMock()))


async def test_gathering_the_context_stores_no_score(monkeypatch):
    uow = h.uow()
    context = await _advisor(uow, monkeypatch).gather_context(h.USER)

    assert uow.fi_scores.rows == []
    # 1b: was 2043-03 (197 months), then 2047-05 (247): FI's month is the
    # baseline timeline's now, with the surplus invested at the placeholder
    # 100% (tests/golden/test_household_fi.py says why).
    # Then May 2042 (187), before the plan-consistency pass.
    assert context["figures"]["fi_month"]["value"] == "August 2044"
    # Salli's figures only: nothing researched, nothing about the person's
    # goals in their own words, and no score.
    assert set(context) == {"figures", "signals", "assumptions"}


async def test_a_run_records_the_score_it_described(monkeypatch):
    import json

    from tests.fakes import FakeLLM

    uow = h.uow()
    advisor = _advisor(uow, monkeypatch)
    answer = json.dumps({"summary": "FI comes in {fi_month} at this pace.", "notes": []})
    monkeypatch.setattr(advisor, "llm_for", AsyncMock(return_value=FakeLLM(answer)))

    report = await advisor.run_advisor(h.USER)

    assert report["summary"] == "FI comes in August 2044 at this pace."
    [score] = uow.fi_scores.rows
    # Was 60.08: debt is scored by its rates (FI pack 3.0.0).
    # Then 57.42, before the emergency fund was held out of the asset base.
    assert (score["overall_score"], score["as_of"]) == ("56.42", "2026-10-11")


async def test_every_briefing_says_an_ai_wrote_it(monkeypatch):
    import json

    from salli.domain.agents.briefing import NOTICE
    from tests.fakes import FakeLLM

    uow = h.uow()
    advisor = _advisor(uow, monkeypatch)
    answer = json.dumps({"summary": "FI comes in {fi_month} at this pace.", "notes": []})
    monkeypatch.setattr(advisor, "llm_for", AsyncMock(return_value=FakeLLM(answer)))

    ran = await advisor.run_advisor(h.USER)
    [listed] = await advisor.list_reports(h.USER)

    for report in (ran, listed):
        assert (report["written_by"], report["notice"]) == ("ai", NOTICE)
