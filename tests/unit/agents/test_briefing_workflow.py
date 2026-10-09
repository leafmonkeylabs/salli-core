"""Unit tests for the monthly briefing workflow (no LLM calls)."""

from __future__ import annotations

import pytest

from salli.domain.agents.advisor import Advice, Recommendation, SuggestedAction
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

    async def persist_report(self, user_id, trigger, advice):
        report = {
            "id": "report-1",
            "trigger": trigger,
            "summary": advice.summary,
            "fire_tier_assessment": advice.fire_tier_assessment,
            "recommendations": [r.title for r in advice.recommendations],
        }
        self.persisted.append((user_id, trigger, advice))
        return report


def _advice() -> Advice:
    return Advice(
        summary="Test summary",
        fire_tier_assessment="Test tier",
        recommendations=[
            Recommendation(
                title="Do X",
                rationale="Because Y",
                category="savings",
                priority=1,
                action=SuggestedAction(type="reminder", label="Do X", due_in_days=7),
            )
        ],
    )


# ── Conditional edge routing ─────────────────────────────────────────────────────


def test_should_narrate_routes_to_narrate_on_success():
    state = BriefingState(user_id="u1", context={"currency": "LKR"})
    assert _should_narrate(state) == "narrate"


def test_should_narrate_routes_to_error_on_gather_failure():
    state = BriefingState(user_id="u1", error="UsageLimitReached")
    assert _should_narrate(state) == "error"


def test_should_review_routes_to_review_on_success():
    state = BriefingState(user_id="u1", advice=_advice())
    assert _should_review(state) == "review"


def test_should_review_routes_to_error_on_narrate_failure():
    state = BriefingState(user_id="u1", error="LLM call failed")
    assert _should_review(state) == "error"


# ── _finalize ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_finalize_approved_persists_report():
    advisor_svc = FakeAdvisorService()
    state = BriefingState(user_id="u1", advice=_advice(), review_decision="approve")

    result = await _finalize(state, advisor_svc)

    assert result["report"]["id"] == "report-1"
    assert not result.get("error")
    assert len(advisor_svc.persisted) == 1
    user_id, trigger, advice = advisor_svc.persisted[0]
    assert user_id == "u1"
    assert trigger == "scheduled"
    assert advice.summary == "Test summary"


@pytest.mark.asyncio
async def test_finalize_rejected_does_not_persist():
    advisor_svc = FakeAdvisorService()
    state = BriefingState(user_id="u1", advice=_advice(), review_decision="reject")

    result = await _finalize(state, advisor_svc)

    assert result["report"] == {}
    assert "error" in result
    assert advisor_svc.persisted == []


@pytest.mark.asyncio
async def test_finalize_edit_not_approved():
    advisor_svc = FakeAdvisorService()
    state = BriefingState(user_id="u1", advice=_advice(), review_decision="edit")

    result = await _finalize(state, advisor_svc)

    assert result["report"] == {}
    assert "error" in result
    assert advisor_svc.persisted == []
