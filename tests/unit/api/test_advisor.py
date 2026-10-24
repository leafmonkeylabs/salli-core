"""The briefing routes' responses: briefings run and stored, the review, the daily run."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from salli.config import get_settings
from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio


_BODY = {
    "summary": "You spent 2,650.50 EUR a month on average.",
    "notes": [{"topic": "cash", "text": "Your cash covers 4.3 months of spending."}],
    "figures": {"spending": {"label": "Spending a month, on average", "value": "2,650.50 EUR"}},
    "signals": [
        {"kind": "price_change", "severity": "medium", "title": "A charge went up", "detail": "x"}
    ],
    "assumptions": {"status": "placeholder", "placeholders": ["real_return"]},
}


async def test_a_briefing_just_run_and_a_stored_one_read_as_they_are(client, mock_services):
    """A fresh briefing has no owner or date; a stored one has. Neither gains
    the other's fields as nulls."""
    ran = {"id": "report-1", "trigger": "manual", **_BODY}
    stored = {
        "id": "report-1",
        "user_id": "test-user-1",
        "trigger": "scheduled",
        "created_at": "2026-10-09T06:00:00+00:00",
        **_BODY,
    }
    mock_services.advisor.run_advisor.return_value = ran
    mock_services.advisor.list_reports.return_value = [stored]
    mock_services.advisor.get_latest_report.return_value = stored

    assert (await client.post("/v1/advisor/run", headers=AUTH)).json() == ran
    assert (await client.get("/v1/advisor/reports", headers=AUTH)).json() == {"reports": [stored]}
    assert (await client.get("/v1/advisor/reports/latest", headers=AUTH)).json() == stored


async def test_recommendations_can_no_longer_be_applied_or_dismissed(client):
    for verb in ("apply", "dismiss"):
        r = await client.post(
            f"/v1/advisor/reports/report-1/recommendations/rec-1/{verb}", headers=AUTH
        )
        assert r.status_code == 404


async def test_a_prepared_briefing_is_the_draft_held_for_review(client, mock_services):
    prepared = {"thread_id": "thread-1", "error": "", "briefing": _BODY}
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


async def test_the_daily_run_still_answers_at_its_path_from_before_v1(app, client, mock_services):
    """A scheduler set up before /v1 calls the unversioned path."""
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(cron_secret="s3cret")
    mock_services.advisor.due_users.return_value = []

    r = await client.post("/advisor/cron/run-due", headers={"X-Cron-Secret": "s3cret"})

    assert r.status_code == 202
    assert r.json() == {"due": 0, "scheduled": True}
