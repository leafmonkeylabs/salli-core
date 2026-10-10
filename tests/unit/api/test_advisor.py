"""The advisor routes' responses: reports run and stored, the briefing review, the daily run."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from salli.config import get_settings
from salli.domain.agents.advisor import Recommendation, SuggestedAction
from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio


def _recommendation(status: str = "pending") -> dict:
    """A recommendation as AdvisorService stores it."""
    return {
        "id": "rec-1",
        "title": "Top up the emergency moat",
        "rationale": "It covers two months of the six it should.",
        "category": "emergency_fund",
        "priority": 1,
        "bucket_key": "moat",
        "action_type": "reminder",
        "action_params": {"label": "Move 50,000 to savings", "due_in_days": 7},
        "status": status,
    }


async def test_a_report_just_run_and_a_stored_one_read_as_they_are(client, mock_services):
    """A fresh report has the tier assessment but no owner or date; a stored one
    the reverse. Neither gains the other's fields as nulls."""
    ran = {
        "trigger": "manual",
        "fi_score_id": None,
        "summary": "Thirteen years out.",
        "fire_tier_assessment": "Standard FIRE: balance growth with stability.",
        "recommendations": [_recommendation()],
        "id": "report-1",
    }
    stored = {
        "id": "report-1",
        "user_id": "test-user-1",
        "trigger": "scheduled",
        "fi_score_id": None,
        "summary": "Thirteen years out.",
        "recommendations": [_recommendation("applied")],
        "created_at": "2026-10-09T06:00:00+00:00",
    }
    mock_services.advisor.run_advisor.return_value = ran
    mock_services.advisor.list_reports.return_value = [stored]
    mock_services.advisor.get_latest_report.return_value = stored

    assert (await client.post("/v1/advisor/run", headers=AUTH)).json() == ran
    assert (await client.get("/v1/advisor/reports", headers=AUTH)).json() == {"reports": [stored]}
    assert (await client.get("/v1/advisor/reports/latest", headers=AUTH)).json() == stored


async def test_acting_on_a_recommendation_says_what_became_of_it(client, mock_services):
    mock_services.advisor.apply_recommendation.return_value = {"id": "rec-1", "status": "applied"}
    mock_services.advisor.dismiss_recommendation.return_value = {
        "id": "rec-2",
        "status": "dismissed",
    }

    applied = await client.post(
        "/v1/advisor/reports/report-1/recommendations/rec-1/apply", headers=AUTH
    )
    dismissed = await client.post(
        "/v1/advisor/reports/report-1/recommendations/rec-2/dismiss", headers=AUTH
    )

    assert applied.json() == {"id": "rec-1", "status": "applied"}
    assert dismissed.json() == {"id": "rec-2", "status": "dismissed"}


async def test_acting_on_a_missing_recommendation_is_a_404(client, mock_services):
    mock_services.advisor.apply_recommendation.side_effect = ValueError("Report not found")

    r = await client.post("/v1/advisor/reports/nope/recommendations/rec-1/apply", headers=AUTH)

    assert r.status_code == 404
    assert r.json()["detail"] == "Report not found"


async def test_a_prepared_briefing_is_the_draft_held_for_review(client, mock_services):
    draft = Recommendation(
        title="Open a fixed deposit",
        rationale="Idle cash earns nothing.",
        category="savings",
        priority=2,
        action=SuggestedAction(type="reminder", label="Open an FD", due_in_days=14),
    )
    prepared = {
        "thread_id": "thread-1",
        "error": "",
        "briefing": {
            "summary": "Thirteen years out.",
            "fire_tier_assessment": "Standard FIRE.",
            "recommendations": [draft.model_dump()],
        },
    }
    mock_services.agent.prepare_briefing.return_value = prepared

    r = await client.post("/v1/advisor/briefing/prepare", json={}, headers=AUTH)

    assert r.json() == prepared


async def test_a_briefing_not_approved_stores_nothing(client, mock_services):
    mock_services.agent.resume_briefing.return_value = {
        "report": {},
        "error": "Briefing not approved (decision: reject)",
    }

    r = await client.post(
        "/v1/advisor/briefing/resume",
        json={"thread_id": "thread-1", "decision": "reject"},
        headers=AUTH,
    )

    assert r.json() == {"report": {}, "error": "Briefing not approved (decision: reject)"}


async def test_resuming_a_briefing_needs_a_signed_in_user(client, mock_services):
    r = await client.post(
        "/v1/advisor/briefing/resume", json={"thread_id": "thread-1", "decision": "approve"}
    )

    assert r.status_code == 401
    mock_services.agent.resume_briefing.assert_not_awaited()


async def test_a_briefing_is_resumed_as_the_signed_in_user(client, mock_services):
    mock_services.agent.resume_briefing.return_value = {"report": {}, "error": "x"}

    await client.post(
        "/v1/advisor/briefing/resume",
        json={"thread_id": "thread-1", "decision": "approve"},
        headers=AUTH,
    )

    mock_services.agent.resume_briefing.assert_awaited_once_with(
        user_id="test-user-1", thread_id="thread-1", decision="approve"
    )


async def test_the_daily_briefing_setting(client, mock_services):
    mock_services.advisor.get_daily_briefing_enabled.return_value = True

    r = await client.get("/v1/advisor/daily-briefing", headers=AUTH)

    assert r.json() == {"enabled": True}


async def test_the_daily_run_is_accepted_then_runs_each_due_user(app, client, mock_services):
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(cron_secret="s3cret")
    mock_services.advisor.due_users.return_value = [{"user_id": "a"}, {"user_id": "b"}]

    r = await client.post("/v1/advisor/cron/run-due", headers={"X-Cron-Secret": "s3cret"})

    assert r.status_code == 202
    assert r.json() == {"due": 2, "scheduled": True}
    # After the response: the transport waits for background work to finish.
    runs = mock_services.advisor.run_advisor.await_args_list
    assert [c.args[0] for c in runs] == ["a", "b"]


async def test_the_daily_run_needs_its_secret(app, client, mock_services):
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(cron_secret="s3cret")

    r = await client.post("/v1/advisor/cron/run-due", headers={"X-Cron-Secret": "guess"})

    assert r.status_code == 401
    mock_services.advisor.due_users.assert_not_called()


async def test_a_non_ascii_cron_secret_is_refused_not_a_500(app, client, mock_services):
    # hmac.compare_digest raises TypeError on non-ASCII str.
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(cron_secret="s3cret")

    r = await client.post("/v1/advisor/cron/run-due", headers={"X-Cron-Secret": "sécret".encode()})

    assert r.status_code == 401
    mock_services.advisor.due_users.assert_not_called()


async def test_the_daily_run_lists_the_due_users_once(app, client, mock_services):
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(cron_secret="s3cret")
    mock_services.advisor.due_users.return_value = [{"user_id": "a"}]

    r = await client.post("/v1/advisor/cron/run-due", headers={"X-Cron-Secret": "s3cret"})

    assert r.json() == {"due": 1, "scheduled": True}
    assert mock_services.advisor.due_users.await_count == 1


async def test_the_daily_run_still_answers_at_the_path_pg_cron_was_given(
    app, client, mock_services
):
    """The scheduled job's URL predates /v1 (supabase/migrations)."""
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(cron_secret="s3cret")
    mock_services.advisor.due_users.return_value = []

    r = await client.post("/advisor/cron/run-due", headers={"X-Cron-Secret": "s3cret"})

    assert r.status_code == 202
    assert r.json() == {"due": 0, "scheduled": True}
