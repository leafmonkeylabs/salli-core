"""
NotificationService against an in-memory unit of work, an injected clock and
a RecordingNotifier: preferences, the preview, and `send_due` (who is due
this hour, once a period, retries after FAILED and the stop after three, no
notifier, one person's failure).
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import pytest

from salli.application.ports import Delivery
from salli.application.services.notification_service import (
    MAX_ATTEMPTS,
    NotificationService,
    PreferencesError,
)
from tests.fakes import FakeUoW, RecordingNotifier
from tests.guardrails import assert_never_urges

LINK = "https://money.example.org"
#: Monday 2026-10-12, 09:30 in Lisbon (UTC+1 until the 25th).
SLOT = dt.datetime(2026, 10, 12, 8, 30, tzinfo=dt.UTC)


class StubInsights:
    def __init__(self) -> None:
        self.cash: dict[str, dt.date | None] = {}
        self.review: dict[str, tuple[int, dt.date | None]] = {}
        self.asked: list[tuple[str, dt.date]] = []
        self.fail_for: set[str] = set()

    async def cash_below_zero_on(self, user_id: str, today: dt.date) -> dt.date | None:
        if user_id in self.fail_for:
            raise RuntimeError(f"forecast failed for Zephyrine Quill at 4321.09 {user_id}")
        self.asked.append((user_id, today))
        return self.cash.get(user_id)

    async def transactions_waiting(self, user_id: str) -> tuple[int, dt.date | None]:
        return self.review.get(user_id, (0, None))


class StubReminders:
    def __init__(self) -> None:
        self.synced: list[tuple[str, str]] = []

    async def sync_alerts(self, user_id: str, today: str) -> dict[str, int]:
        self.synced.append((user_id, today))
        return {}


class Clock:
    def __init__(self, now: dt.datetime) -> None:
        self.now = now

    def __call__(self) -> dt.datetime:
        return self.now


@pytest.fixture
def uow() -> FakeUoW:
    return FakeUoW("EUR")


@pytest.fixture
def insights() -> StubInsights:
    return StubInsights()


@pytest.fixture
def reminders() -> StubReminders:
    return StubReminders()


@pytest.fixture
def clock() -> Clock:
    return Clock(SLOT)


def make(
    uow: FakeUoW,
    reminders: StubReminders,
    insights: StubInsights,
    clock: Clock,
    notifier: RecordingNotifier | None = None,
    name: str | None = "test-sender",
) -> tuple[NotificationService, RecordingNotifier]:
    notifier = notifier or RecordingNotifier()
    service = NotificationService(
        uow.factory(),
        reminders,  # type: ignore[arg-type]
        insights,  # type: ignore[arg-type]
        notifier,
        notifier_name=name,
        public_url=LINK + "/",
        clock=clock,
    )
    return service, notifier


def add_reminder(
    uow: FakeUoW, user_id: str, due: str, source: str | None = None, kind: str = "x"
) -> None:
    n = len(uow.reminders.rows)
    uow.reminders.rows[f"r{n}"] = {
        "id": f"r{n}",
        "user_id": user_id,
        "kind": kind,
        "due_date": due,
        "status": "pending",
        "alert_type": None,
        "source_domain": source,
        "source_id": None,
        "severity": None,
    }


async def opt_in(service: NotificationService, user_id: str = "u1", **more: Any) -> None:
    await service.set_preferences(user_id, {"enabled": True, "time_zone": "Europe/Lisbon", **more})


# ── Preferences ─────────────────────────────────────────────────────────────


async def test_off_until_turned_on_with_salli_s_plain_defaults(uow, reminders, insights, clock):
    service, _ = make(uow, reminders, insights, clock)
    assert await service.preferences("u1") == {
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
        "push_items": ["reminder_due", "cash_below_zero_ahead", "budget_over"],
        "quiet_hours": None,
        "time_zone": None,
        "next_at": None,
        "sender_enabled": True,
    }


async def test_turning_it_on_needs_a_time_zone(uow, reminders, insights, clock):
    service, _ = make(uow, reminders, insights, clock)
    with pytest.raises(PreferencesError, match="time zone"):
        await service.set_preferences("u1", {"enabled": True})
    assert await uow.notifications.get_preferences("u1") is None

    saved = await service.set_preferences(
        "u1", {"enabled": True, "time_zone": "Europe/Lisbon", "hour": 18}
    )
    assert saved["enabled"] is True
    assert saved["time_zone"] == "Europe/Lisbon"
    assert saved["next_at"] == "2026-10-12T18:00:00+01:00"
    assert uow.user_profiles.rows["u1"]["time_zone"] == "Europe/Lisbon"

    with pytest.raises(PreferencesError, match="time zone"):
        await service.set_preferences("u1", {"time_zone": None})
    off = await service.set_preferences("u1", {"enabled": False, "time_zone": None})
    assert (off["enabled"], off["time_zone"], off["next_at"]) == (False, None, None)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"time_zone": "Mars/Olympus"}, "IANA"),
        ({"hour": 24}, "hour"),
        ({"hour": True}, "hour"),
        ({"cadence": "daily"}, "cadence"),
        ({"weekday": "funday"}, "weekday"),
        ({"items": ["spending_spike"]}, "unknown item"),
        ({"items": []}, "at least one"),
    ],
)
async def test_what_cannot_be_saved_is_refused_whole(
    uow, reminders, insights, clock, changes, message
):
    service, _ = make(uow, reminders, insights, clock)
    with pytest.raises(PreferencesError, match=message):
        await service.set_preferences("u1", {"cadence": "monthly", **changes})
    assert await uow.notifications.get_preferences("u1") is None


async def test_items_keep_the_tables_order(uow, reminders, insights, clock):
    service, _ = make(uow, reminders, insights, clock)
    saved = await service.set_preferences(
        "u1", {"items": ["transactions_to_review", "reminder_due", "reminder_due"]}
    )
    assert saved["items"] == ["reminder_due", "transactions_to_review"]


async def test_preferences_say_whether_the_server_can_send(uow, reminders, insights, clock):
    service, _ = make(uow, reminders, insights, clock, name=None)
    assert (await service.preferences("u1"))["sender_enabled"] is False


# ── The preview ─────────────────────────────────────────────────────────────


async def test_the_preview_is_the_message_and_sends_and_writes_nothing(
    uow, reminders, insights, clock
):
    service, notifier = make(uow, reminders, insights, clock)
    await opt_in(service)
    add_reminder(uow, "u1", "2026-10-05", "decision", "Review your decision: Buy the Vespa?")
    insights.cash["u1"] = dt.date(2026, 11, 2)

    preview = await service.preview("u1")

    assert preview["period"] == "2026-W42"
    assert preview["as_of"] == "2026-10-12"
    assert preview["time_zone"] == "Europe/Lisbon"
    digest = preview["digest"]
    assert digest["subject"] == "Salli: what is waiting, week of Oct 12, 2026"
    assert [i["kind"] for i in digest["items"]] == [
        "decision_review_due",
        "cash_below_zero_ahead",
    ]
    assert digest["link"] == LINK
    assert "Vespa" not in str(preview)
    assert preview["note"] == "This is the digest that would go if it went now."
    assert notifier.sent == []
    assert uow.notifications.log == {}
    assert reminders.synced == []
    assert_never_urges(preview)


async def test_a_preview_with_nothing_waiting_says_so(uow, reminders, insights, clock):
    service, _ = make(uow, reminders, insights, clock, name=None)
    preview = await service.preview("u1")
    assert preview["digest"] is None
    assert preview["time_zone"] is None
    assert preview["note"] == (
        "Nothing is waiting, so no digest would go. Read in UTC: set your time zone for "
        "your own dates and hour. Digests are off for you."
    )


# ── Sending ─────────────────────────────────────────────────────────────────


async def test_a_digest_goes_in_its_hour_and_is_logged(uow, reminders, insights, clock):
    service, notifier = make(uow, reminders, insights, clock)
    await opt_in(service)
    add_reminder(uow, "u1", "2026-10-14", kind="Pay Zephyrine 950.00")

    counts = await service.send_due()

    assert counts == {
        "notifier": "test-sender",
        "due": 1,
        "sent": 1,
        "nothing_waiting": 0,
        "no_destination": 0,
        "failed": 0,
        "skipped": 0,
    }
    (sent,) = notifier.sent
    assert (sent.user_id, sent.period, sent.kind) == ("u1", "2026-W42", "digest")
    assert [i.title for i in sent.items] == ["1 reminder due on Oct 14, 2026"]
    assert "Zephyrine" not in sent.text and "950" not in sent.text
    assert reminders.synced == [("u1", "2026-10-12")]
    (row,) = await service.deliveries("u1")
    assert row["status"] == "sent"
    assert row["attempts"] == 1
    assert row["items"] == [{"kind": "reminder_due", "count": 1, "date": "2026-10-14"}]
    assert row["hash"].startswith("sha256:")
    assert "text" not in row and "subject" not in row
    assert uow.notifications.runs == [SLOT]


async def test_outside_the_hour_nothing_goes(uow, reminders, insights, clock):
    service, notifier = make(uow, reminders, insights, clock)
    await opt_in(service)
    add_reminder(uow, "u1", "2026-10-14")
    for when in (SLOT - dt.timedelta(hours=1), SLOT + dt.timedelta(hours=1)):
        counts = await service.send_due(when)
        assert counts["due"] == 0
    assert notifier.sent == []


async def test_opted_out_nothing_goes(uow, reminders, insights, clock):
    service, notifier = make(uow, reminders, insights, clock)
    await opt_in(service)
    await service.set_preferences("u1", {"enabled": False})
    add_reminder(uow, "u1", "2026-10-14")
    assert (await service.send_due())["due"] == 0
    assert notifier.sent == []


async def test_nothing_waiting_nothing_sent_and_nothing_logged(uow, reminders, insights, clock):
    service, notifier = make(uow, reminders, insights, clock)
    await opt_in(service)
    counts = await service.send_due()
    assert (counts["due"], counts["nothing_waiting"], counts["sent"]) == (1, 1, 0)
    assert notifier.sent == []
    assert await service.deliveries("u1") == []
    # And a later day of the week does not make up for it.
    add_reminder(uow, "u1", "2026-10-14")
    later = await service.send_due(SLOT + dt.timedelta(days=1))
    assert (later["due"], later["skipped"]) == (1, 1)
    assert notifier.sent == []


async def test_once_a_period_however_often_the_job_runs(uow, reminders, insights, clock):
    service, notifier = make(uow, reminders, insights, clock)
    await opt_in(service)
    add_reminder(uow, "u1", "2026-10-14")
    await service.send_due()
    again = await service.send_due(SLOT + dt.timedelta(minutes=20))
    next_day = await service.send_due(SLOT + dt.timedelta(days=1))
    assert again["skipped"] == next_day["skipped"] == 1
    assert len(notifier.sent) == 1
    # The next week is another period.
    await service.send_due(SLOT + dt.timedelta(days=7))
    assert [n.period for n in notifier.sent] == ["2026-W42", "2026-W43"]


async def test_a_failed_send_is_retried_at_the_hour_then_stops_after_three(
    uow, reminders, insights, clock
):
    notifier = RecordingNotifier(Delivery.FAILED)
    service, _ = make(uow, reminders, insights, clock, notifier)
    await opt_in(service)
    add_reminder(uow, "u1", "2026-10-14")

    outcomes = [
        (await service.send_due(SLOT + dt.timedelta(days=day)))["failed"] for day in range(5)
    ]

    assert outcomes == [1, 1, 1, 0, 0]
    assert len(notifier.sent) == MAX_ATTEMPTS == 3
    assert len({n.id for n in notifier.sent}) == 1  # one idempotency key a period
    (row,) = await service.deliveries("u1")
    assert (row["status"], row["attempts"]) == ("failed", 3)


async def test_a_retry_that_succeeds_is_logged_as_sent(uow, reminders, insights, clock):
    notifier = RecordingNotifier(Delivery.FAILED, Delivery.SENT)
    service, _ = make(uow, reminders, insights, clock, notifier)
    await opt_in(service)
    add_reminder(uow, "u1", "2026-10-14")
    await service.send_due()
    retried = await service.send_due(SLOT + dt.timedelta(days=2))
    assert retried["sent"] == 1
    (row,) = await service.deliveries("u1")
    assert (row["status"], row["attempts"]) == ("sent", 2)
    assert row["sent_at"] is not None


async def test_no_destination_is_recorded_and_not_retried(uow, reminders, insights, clock):
    notifier = RecordingNotifier(Delivery.NO_DESTINATION)
    service, _ = make(uow, reminders, insights, clock, notifier)
    await opt_in(service)
    add_reminder(uow, "u1", "2026-10-14")
    assert (await service.send_due())["no_destination"] == 1
    assert (await service.send_due(SLOT + dt.timedelta(days=1)))["skipped"] == 1
    assert len(notifier.sent) == 1


async def test_a_sender_that_raises_is_a_failure_logged_without_the_message(
    uow, reminders, insights, clock, caplog
):
    notifier = RecordingNotifier(error=ConnectionError("smtp said no to Zephyrine Quill"))
    service, _ = make(uow, reminders, insights, clock, notifier)
    await opt_in(service)
    add_reminder(uow, "u1", "2026-10-14", kind="Pay Zephyrine Quill 950.00")
    with caplog.at_level(logging.WARNING):
        counts = await service.send_due()
    assert counts["failed"] == 1
    (row,) = await service.deliveries("u1")
    assert row["status"] == "failed"
    logged = caplog.text
    assert "ConnectionError" in logged
    assert "Zephyrine" not in logged and "reminder due" not in logged and "950" not in logged


async def test_one_persons_failure_never_stops_the_rest(uow, reminders, insights, clock, caplog):
    service, notifier = make(uow, reminders, insights, clock)
    for user in ("u1", "u2"):
        await opt_in(service, user)
        add_reminder(uow, user, "2026-10-14")
    insights.fail_for.add("u1")
    with caplog.at_level(logging.WARNING):
        counts = await service.send_due()
    assert (counts["failed"], counts["sent"]) == (1, 1)
    assert [n.user_id for n in notifier.sent] == ["u2"]
    assert "RuntimeError" in caplog.text and "Zephyrine" not in caplog.text
    # Nothing was claimed for the one that failed before sending.
    assert await service.deliveries("u1") == []


async def test_each_person_gets_only_their_own(uow, reminders, insights, clock):
    service, notifier = make(uow, reminders, insights, clock)
    await opt_in(service, "u1")
    await opt_in(service, "u2", items=["filing_deadline"])
    add_reminder(uow, "u1", "2026-10-13")
    add_reminder(uow, "u2", "2026-10-20", "tax_rules")
    add_reminder(uow, "u2", "2026-10-13")  # not chosen by u2
    await service.send_due()
    by_user = {n.user_id: [i.kind for i in n.items] for n in notifier.sent}
    assert by_user == {"u1": ["reminder_due"], "u2": ["filing_deadline"]}
    assert len(await service.deliveries("u1")) == len(await service.deliveries("u2")) == 1


async def test_each_person_at_their_own_local_hour(uow, reminders, insights, clock):
    service, notifier = make(uow, reminders, insights, clock)
    await opt_in(service, "lisbon")
    await service.set_preferences("auckland", {"enabled": True, "time_zone": "Pacific/Auckland"})
    for user in ("lisbon", "auckland"):
        add_reminder(uow, user, "2026-10-14")
    # Monday 09:30 in Auckland is Sunday 20:30 UTC.
    await service.send_due(dt.datetime(2026, 10, 11, 20, 30, tzinfo=dt.UTC))
    await service.send_due()
    assert [(n.user_id, n.period) for n in notifier.sent] == [
        ("auckland", "2026-W42"),
        ("lisbon", "2026-W42"),
    ]


async def test_without_a_notifier_the_job_sends_nothing(uow, reminders, insights, clock):
    service, notifier = make(uow, reminders, insights, clock, name=None)
    await opt_in(service)
    add_reminder(uow, "u1", "2026-10-14")
    counts = await service.send_due()
    assert counts["notifier"] is None
    assert counts["due"] == 0
    assert notifier.sent == []
    assert uow.notifications.runs == []
    assert await service.last_run() is None


async def test_the_export_carries_preferences_and_the_log(uow, reminders, insights, clock):
    service, _ = make(uow, reminders, insights, clock)
    await opt_in(service)
    add_reminder(uow, "u1", "2026-10-14")
    await service.send_due()
    exported = await service.export("u1")
    assert exported["notification_preferences"]["enabled"] is True
    assert [d["status"] for d in exported["notification_deliveries"]] == ["sent"]
