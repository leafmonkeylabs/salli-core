"""
The digest routes over a real NotificationService (an in-memory unit of
work, an injected clock, a RecordingNotifier): preferences read and set, the
time zone and its refusals, the preview, the delivery log, and the cron
route behind X-Cron-Secret.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from salli.application.services.notification_service import NotificationService
from salli.config import get_settings
from tests.fakes import FakeUoW, RecordingNotifier
from tests.guardrails import assert_never_urges
from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio

USER = "test-user-1"
SLOT = dt.datetime(2026, 10, 12, 8, 30, tzinfo=dt.UTC)  # Monday 09:30 in Lisbon


class _Insights:
    async def cash_below_zero_on(self, user_id: str, today: dt.date) -> dt.date | None:
        return dt.date(2026, 11, 2)

    async def transactions_waiting(self, user_id: str) -> tuple[int, dt.date | None]:
        return 0, None


class _Reminders:
    async def sync_alerts(self, user_id: str, today: str) -> dict[str, int]:
        return {}


@pytest.fixture
def notifier() -> RecordingNotifier:
    return RecordingNotifier()


@pytest.fixture
def uow() -> FakeUoW:
    return FakeUoW("EUR")


@pytest.fixture(autouse=True)
def notifications(mock_services, uow, notifier):
    mock_services.notifications = NotificationService(
        uow.factory(),
        _Reminders(),  # type: ignore[arg-type]
        _Insights(),  # type: ignore[arg-type]
        notifier,
        notifier_name="test-sender",
        public_url="https://money.example.org",
        clock=lambda: SLOT,
    )
    return mock_services.notifications


async def test_preferences_start_off(client):
    r = await client.get("/v1/notifications/preferences", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {
        "enabled": False,
        "cadence": "weekly",
        "weekday": "monday",
        "hour": 9,
        "items": [
            "decision_review_due",
            "reminder_due",
            "filing_deadline",
            "cash_below_zero_ahead",
        ],
        "time_zone": None,
        "next_at": None,
        "sender_enabled": True,
    }


async def test_turning_digests_on_with_a_time_zone(client, uow):
    r = await client.patch(
        "/v1/notifications/preferences",
        headers=AUTH,
        json={"enabled": True, "time_zone": "Europe/Lisbon", "cadence": "monthly", "hour": 18},
    )
    assert r.status_code == 200
    body = r.json()
    assert (body["enabled"], body["cadence"], body["hour"]) == (True, "monthly", 18)
    assert body["next_at"] == "2026-11-02T18:00:00+00:00"
    assert uow.user_profiles.rows[USER]["time_zone"] == "Europe/Lisbon"
    again = await client.get("/v1/notifications/preferences", headers=AUTH)
    assert again.json() == body


async def test_on_without_a_time_zone_is_refused(client, uow):
    r = await client.patch("/v1/notifications/preferences", headers=AUTH, json={"enabled": True})
    assert r.status_code == 422
    assert "time zone" in r.json()["detail"]
    assert await uow.notifications.get_preferences(USER) is None


@pytest.mark.parametrize(
    "body",
    [
        {"time_zone": "Mars/Olympus"},
        {"hour": 24},
        {"cadence": "daily"},
        {"weekday": "funday"},
        {"items": ["spending_spike"]},
        {"items": []},
    ],
)
async def test_what_cannot_be_saved_is_a_422(client, body):
    r = await client.patch("/v1/notifications/preferences", headers=AUTH, json=body)
    assert r.status_code == 422


async def test_an_explicit_null_clears_the_time_zone(client, uow):
    await client.patch(
        "/v1/notifications/preferences", headers=AUTH, json={"time_zone": "Pacific/Auckland"}
    )
    r = await client.patch("/v1/notifications/preferences", headers=AUTH, json={"time_zone": None})
    assert r.json()["time_zone"] is None
    assert uow.user_profiles.rows[USER]["time_zone"] is None


async def test_the_preview_is_the_message_and_sends_nothing(client, notifier):
    await client.patch(
        "/v1/notifications/preferences",
        headers=AUTH,
        json={"enabled": True, "time_zone": "Europe/Lisbon"},
    )
    r = await client.get("/v1/notifications/preview", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["period"] == "2026-W42"
    assert body["as_of"] == "2026-10-12"
    digest = body["digest"]
    assert digest["kind"] == "digest"
    assert digest["items"] == [
        {
            "kind": "cash_below_zero_ahead",
            "title": "Your cash forecast goes below zero on Nov 2, 2026",
            "count": 1,
            "date": "2026-11-02",
        }
    ]
    assert digest["link"] == "https://money.example.org"
    assert notifier.sent == []
    assert_never_urges(body)


async def test_the_log_lists_what_went(client, notifications, notifier):
    await client.patch(
        "/v1/notifications/preferences",
        headers=AUTH,
        json={"enabled": True, "time_zone": "Europe/Lisbon"},
    )
    await notifications.send_due()
    r = await client.get("/v1/notifications/deliveries", headers=AUTH)
    assert r.status_code == 200
    (row,) = r.json()["deliveries"]
    assert row["status"] == "sent"
    assert row["period"] == "2026-W42"
    assert row["items"] == [{"kind": "cash_below_zero_ahead", "count": 1, "date": "2026-11-02"}]
    assert row["id"] == notifier.sent[0].id
    assert row["sent_at"] is not None
    assert "text" not in row
    assert (await client.get("/v1/notifications/deliveries?limit=0", headers=AUTH)).status_code == (
        422
    )


async def test_the_routes_need_a_signed_in_person(client):
    assert (await client.get("/v1/notifications/preferences")).status_code == 401
    assert (await client.get("/v1/notifications/preview")).status_code == 401


async def test_the_cron_route_sends_what_is_due_after_answering(app, client, notifier):
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(cron_secret="s3cret")
    await client.patch(
        "/v1/notifications/preferences",
        headers=AUTH,
        json={"enabled": True, "time_zone": "Europe/Lisbon"},
    )
    r = await client.post("/v1/notifications/cron/send-due", headers={"X-Cron-Secret": "s3cret"})
    assert r.status_code == 202
    assert r.json() == {"due": 1, "scheduled": True}
    # The transport waits for the background work.
    assert [n.user_id for n in notifier.sent] == [USER]


async def test_the_cron_route_needs_its_secret(app, client, notifier):
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(cron_secret="s3cret")
    r = await client.post("/v1/notifications/cron/send-due", headers={"X-Cron-Secret": "guess"})
    assert r.status_code == 401
    assert notifier.sent == []


async def test_without_a_notifier_the_cron_route_schedules_nothing(
    app, client, mock_services, uow, notifier
):
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(cron_secret="s3cret")
    mock_services.notifications = NotificationService(
        uow.factory(),
        _Reminders(),  # type: ignore[arg-type]
        _Insights(),  # type: ignore[arg-type]
        notifier,
        clock=lambda: SLOT,
    )
    r = await client.post("/v1/notifications/cron/send-due", headers={"X-Cron-Secret": "s3cret"})
    assert r.json() == {"due": 0, "scheduled": False}
