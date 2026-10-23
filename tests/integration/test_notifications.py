"""
Digests against a real Postgres: once a period however many runs or servers,
a crash mid-send never sending twice, opt-in and opt-out, each person's own,
erasing an account erasing its digest's rows, and a message built from a
ledger full of distinctive names and amounts holding none of them.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from salli.adapters.db.models import NotificationDeliveryORM
from salli.application.ports import Delivery, Notification, Notifier
from salli.application.services.insights_service import InsightsService
from salli.application.services.ledger_service import LedgerService
from salli.application.services.notification_service import NotificationService
from salli.application.services.reminder_service import ReminderService
from salli.domain.accounting.models import Direction
from tests.fakes import RecordingNotifier
from tests.guardrails import assert_never_urges
from tests.integration.pg import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]

#: Monday 2026-10-12, 09:30 in Lisbon.
SLOT = dt.datetime(2026, 10, 12, 8, 30, tzinfo=dt.UTC)
TODAY = dt.date(2026, 10, 12)


def service(uow_factory, notifier: Notifier, now: dt.datetime = SLOT) -> NotificationService:
    return NotificationService(
        uow_factory,
        ReminderService(uow_factory),
        InsightsService(uow_factory, today=lambda: TODAY),
        notifier,
        notifier_name="test-sender",
        public_url="https://money.example.org",
        clock=lambda: now,
    )


async def person(uow_factory, user: str, *, due: str = "2026-10-14", **prefs: object) -> None:
    """A profile, digests on in Lisbon, and one reminder of their own."""
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(user, {"base_currency": "EUR"})
        await uow.reminders.create_reminder(user, f"{user}-r1", f"Call Zqorbit about {user}", due)
    await service(uow_factory, RecordingNotifier()).set_preferences(
        user, {"enabled": True, "time_zone": "Europe/Lisbon", **prefs}
    )


class Crash(BaseException):
    """The process going away mid-send: not an exception anything catches."""


class CrashingNotifier(Notifier):
    def __init__(self) -> None:
        self.calls = 0

    async def send(self, notification: Notification) -> Delivery:
        self.calls += 1
        raise Crash


async def test_a_period_goes_once_however_many_runs_and_servers(uow_factory):
    await person(uow_factory, "ama")
    notifier = RecordingNotifier()
    one, two = service(uow_factory, notifier), service(uow_factory, notifier)

    results = await asyncio.gather(one.send_due(), two.send_due(), one.send_due())
    await two.send_due(SLOT + dt.timedelta(days=1))

    assert sum(r["sent"] for r in results) == 1
    assert sum(r["skipped"] for r in results) == 2
    assert len(notifier.sent) == 1
    (row,) = await one.deliveries("ama")
    assert (row["status"], row["attempts"], row["period"]) == ("sent", 1, "2026-W42")


async def test_a_crash_mid_send_never_sends_twice(uow_factory):
    await person(uow_factory, "ama")
    crashing = CrashingNotifier()
    with pytest.raises(Crash):
        await service(uow_factory, crashing).send_due()
    assert crashing.calls == 1

    after = RecordingNotifier()
    for day in range(4):
        counts = await service(uow_factory, after).send_due(SLOT + dt.timedelta(days=day))
        assert counts["sent"] == 0
    assert after.sent == []
    (row,) = await service(uow_factory, after).deliveries("ama")
    assert (row["status"], row["attempts"]) == ("sending", 1)


async def test_a_failed_send_is_retried_at_most_three_times(uow_factory):
    await person(uow_factory, "ama")
    failing = RecordingNotifier(Delivery.FAILED)
    for day in range(6):
        await service(uow_factory, failing).send_due(SLOT + dt.timedelta(days=day))
    assert len(failing.sent) == 3
    (row,) = await service(uow_factory, failing).deliveries("ama")
    assert (row["status"], row["attempts"]) == ("failed", 3)


async def test_only_who_opted_in_with_a_time_zone_is_due(uow_factory):
    await person(uow_factory, "on")
    await person(uow_factory, "off")
    await service(uow_factory, RecordingNotifier()).set_preferences("off", {"enabled": False})
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("no-zone", {"base_currency": "EUR"})
        # Stored on, but with no time zone: not due (the service refuses this).
        await uow.notifications.save_preferences(
            "no-zone",
            {"enabled": True, "cadence": "weekly", "weekday": "monday", "hour": 9, "items": []},
        )
    notifier = RecordingNotifier()
    counts = await service(uow_factory, notifier).send_due()
    assert counts["due"] == 1
    assert [n.user_id for n in notifier.sent] == ["on"]


async def test_each_person_sees_only_their_own(uow_factory):
    await person(uow_factory, "ama", due="2026-10-13")
    await person(uow_factory, "kofi", due="2026-11-30")  # not before the next digest
    notifier = RecordingNotifier()
    svc = service(uow_factory, notifier)
    await svc.send_due()
    assert [n.user_id for n in notifier.sent] == ["ama"]
    assert len(await svc.deliveries("ama")) == 1
    assert await svc.deliveries("kofi") == []
    assert (await svc.preview("kofi"))["digest"] is None
    assert (await svc.preferences("kofi"))["time_zone"] == "Europe/Lisbon"


async def test_the_log_allows_one_row_a_person_and_period(uow_factory):
    await person(uow_factory, "ama")
    await service(uow_factory, RecordingNotifier()).send_due()
    with pytest.raises(IntegrityError):
        async with uow_factory() as uow:
            session = uow.notifications._s  # type: ignore[attr-defined]
            session.add(
                NotificationDeliveryORM(
                    id="x" * 64,
                    user_id="ama",
                    period="2026-W42",
                    items=[],
                    hash="sha256:" + "0" * 64,
                    status="sent",
                    attempts=1,
                    last_attempt_at=SLOT,
                )
            )
            # Inside the unit of work, so it rolls back and closes.
            await session.flush()


async def test_two_claims_at_once_take_one(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("ama", {"base_currency": "EUR"})

    async def claim() -> int | None:
        async with uow_factory() as uow:
            return await uow.notifications.claim(
                "ama",
                delivery_id="a" * 64,
                period="2026-W42",
                items=[],
                message_hash="sha256:" + "1" * 64,
                now=SLOT,
                first=True,
                max_attempts=3,
            )

    assert sorted(await asyncio.gather(*(claim() for _ in range(5))), key=str) == [
        1,
        None,
        None,
        None,
        None,
    ]


async def test_erasing_the_account_erases_its_digest(uow_factory):
    await person(uow_factory, "ama")
    await person(uow_factory, "kofi")
    await service(uow_factory, RecordingNotifier()).send_due()
    async with uow_factory() as uow:
        counts = await uow.data_portability.delete_all("ama")
    assert counts["notification_preferences"] == 1
    assert counts["notification_deliveries"] == 1
    async with uow_factory() as uow:
        assert await uow.notifications.get_preferences("ama") is None
        assert await uow.notifications.deliveries("ama") == []
        assert await uow.user_profiles.get("ama") is None
        # Someone else's stays.
        assert await uow.notifications.get_preferences("kofi") is not None
        assert len(await uow.notifications.deliveries("kofi")) == 1


async def test_the_job_s_last_run_is_kept_for_doctor(uow_factory):
    svc = service(uow_factory, RecordingNotifier())
    assert await svc.last_run() is None
    await svc.send_due()
    await svc.send_due(SLOT + dt.timedelta(hours=1))
    assert await svc.last_run() == SLOT + dt.timedelta(hours=1)


def _legs(debit: str, credit: str, amount: str) -> list[dict[str, object]]:
    return [
        {"account_id": debit, "direction": Direction.DEBIT, "amount": Decimal(amount)},
        {"account_id": credit, "direction": Direction.CREDIT, "amount": Decimal(amount)},
    ]


async def test_a_digest_from_real_books_names_nothing_and_counts_no_money(uow_factory):
    user = "ama"
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(user, {"base_currency": "EUR"})
    ledger = LedgerService(uow_factory)
    bank = await ledger.add_account(user, "1000", "Zqvelvet Credit Union", "asset")
    equity = await ledger.add_account(user, "3000", "Zqheirloom", "equity")
    food = await ledger.add_account(user, "5000", "Zqmarzipan Deli", "expense")
    # Overdrawn: the forecast is below zero from today.
    await ledger.add_entry(user, "2026-10-01", "Zqopening", "manual", _legs(bank, equity, "100"))
    await ledger.add_entry(
        user, "2026-10-02", "ZQDELI 4321.09", "manual", _legs(food, bank, "4321.09")
    )
    async with uow_factory() as uow:
        await uow.reminders.create_reminder(user, "own", "Pay Zqlandlord 1875.25", "2026-10-15")
        await uow.reminders.upsert_alert(
            user,
            "decision_review",
            "decision",
            "d1",
            "Review your decision: Buy the Zqvespa for 6400.00?",
            "2026-10-05",
            "info",
        )
        await uow.reminders.upsert_alert(
            user,
            "filing",
            "tax_rules",
            "rs:annual",
            "Zqland annual return (XA 2026)",
            "2026-10-20",
            "info",
        )
    notifier = RecordingNotifier()
    svc = service(uow_factory, notifier)
    await svc.set_preferences(
        user,
        {
            "enabled": True,
            "time_zone": "Europe/Lisbon",
            "items": [
                "decision_review_due",
                "reminder_due",
                "filing_deadline",
                "cash_below_zero_ahead",
                "transactions_to_review",
            ],
        },
    )

    await svc.send_due()

    (sent,) = notifier.sent
    assert [i.kind for i in sent.items] == [
        "decision_review_due",
        "reminder_due",
        "filing_deadline",
        "cash_below_zero_ahead",
    ]
    assert sent.items[3].title == "Your cash forecast goes below zero on Oct 12, 2026"
    message = sent.subject + sent.text + str(sent.items)
    assert "Zq" not in message and "ZQ" not in message
    assert not re.search(r"\d[\d,.]*[.,]\d", message.replace("money.example.org", ""))
    assert_never_urges({"subject": sent.subject, "text": sent.text})
    (row,) = await svc.deliveries(user)
    assert "Zq" not in str(row)
