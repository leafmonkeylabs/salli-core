"""Unit tests for the monthly briefing workflow (no LLM calls)."""

from __future__ import annotations

import pytest

from salli.domain.agents.briefing import Draft
from salli.domain.agents.briefing_workflow import (
    BriefingState,
    _finalize,
    _should_narrate,
    _should_review,
)

# ── Fakes ──────────────────────────────────────────────────────────────────────


class FakeAdvisorService:
    def __init__(self):
        self.persisted: list[tuple] = []

    async def persist_report(self, user_id, trigger, draft, context):
        report = {"id": "report-1", "trigger": trigger, "summary": draft.summary}
        self.persisted.append((user_id, trigger, draft))
        return report


def _draft() -> Draft:
    return Draft(summary="Test summary")


# ── Conditional edge routing ─────────────────────────────────────────────────────


def test_should_narrate_routes_to_narrate_on_success():
    state = BriefingState(user_id="u1", context={"figures": {}})
    assert _should_narrate(state) == "narrate"


def test_should_narrate_routes_to_error_on_gather_failure():
    state = BriefingState(user_id="u1", error="UsageLimitReached")
    assert _should_narrate(state) == "error"


def test_should_review_routes_to_review_on_success():
    state = BriefingState(user_id="u1", draft=_draft())
    assert _should_review(state) == "review"


def test_should_review_routes_to_error_on_narrate_failure():
    state = BriefingState(user_id="u1", error="LLM call failed")
    assert _should_review(state) == "error"


# ── _finalize ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_finalize_approved_persists_report():
    advisor_svc = FakeAdvisorService()
    state = BriefingState(user_id="u1", draft=_draft(), review_decision="approve")

    result = await _finalize(state, advisor_svc)

    assert result["report"]["id"] == "report-1"
    assert not result.get("error")
    assert len(advisor_svc.persisted) == 1
    user_id, trigger, draft = advisor_svc.persisted[0]
    assert user_id == "u1"
    assert trigger == "scheduled"
    assert draft.summary == "Test summary"


@pytest.mark.asyncio
async def test_finalize_rejected_does_not_persist():
    advisor_svc = FakeAdvisorService()
    state = BriefingState(user_id="u1", draft=_draft(), review_decision="reject")

    result = await _finalize(state, advisor_svc)

    assert result["report"] == {}
    assert "error" in result
    assert advisor_svc.persisted == []


@pytest.mark.asyncio
async def test_finalize_edit_not_approved():
    advisor_svc = FakeAdvisorService()
    state = BriefingState(user_id="u1", draft=_draft(), review_decision="edit")

    result = await _finalize(state, advisor_svc)

    assert result["report"] == {}
    assert "error" in result
    assert advisor_svc.persisted == []
