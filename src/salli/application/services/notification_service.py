"""
NotificationService — a person's digest: their preferences, a preview of the
message, the delivery log, and `send_due`, which a scheduler runs every hour
(docs/design/decision-lab-phase-3.md, section 4).

Core builds every message (domain/notifications/digest.py) and sends none:
the deployment's `Notifier` delivers it, or, with Salli's own `NoNotifier`,
nothing goes and the job says so. What a digest may say is fixed by the
builder: kinds of item, counts, dates and a link, never an amount, a name or
a question.

**Once a period.** `send_due(now)` finds who is in their digest's hour (their
local hour on their digest day, or on a later day of the period for a retry:
domain/notifications/schedule.py), refreshes their alerts, builds the
digest, and claims the period's row in the delivery log before sending. The
claim is an insert under a unique (user, period) key, or an update that only
matches a FAILED row with attempts left, so a rerun or a second server sends
nothing twice. A FAILED send is tried again at the same hour on a later day
of the period, three attempts in all. An attempt that never recorded its
outcome (the process stopped mid-send) stays `sending` and is never tried
again: it may have gone. Nothing waiting, nothing sent, and nothing logged.

**Failures** are logged by the exception's type and the user's id, never a
message's contents, and one person's failure never stops the rest.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from salli.application.ports import Delivery, Notification, Notifier
from salli.application.services.insights_service import InsightsService
from salli.application.services.reminder_service import ReminderService
from salli.domain.notifications import schedule as timing
from salli.domain.notifications.digest import (
    DEFAULT_ITEMS,
    ITEM_KINDS,
    ItemKind,
    ReminderFact,
    Waiting,
    build_digest,
    item_record,
    message_hash,
    waiting_items,
)
from salli.domain.notifications.push import PUSH_ITEMS, build_push
from salli.domain.notifications.schedule import Cadence, Schedule, Weekday

_log = logging.getLogger(__name__)

#: Attempts at one period's digest, the first included.
MAX_ATTEMPTS = 3

#: What a person has before they set anything: off, Monday at 09:00, the
#: default items.
DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "cadence": "weekly",
    "weekday": timing.DEFAULT_WEEKDAY,
    "hour": timing.DEFAULT_HOUR,
    "items": list(DEFAULT_ITEMS),
}


class PreferencesError(ValueError):
    """Preferences that can't be saved, and why."""


class PushUnavailable(RuntimeError):
    """This server sends no push alerts: no relay, or no key to seal tokens."""


def token_hash(token: str) -> str:
    """How a device is found and removed: the SHA-256 of its push token."""
    return hashlib.sha256(token.encode()).hexdigest()


def _token_aad(digest: str) -> str:
    return f"push-device:{digest}"


@dataclass(frozen=True)
class DueDigest:
    """Someone in their digest's hour now."""

    user_id: str
    preferences: dict[str, Any]
    schedule: Schedule
    due: timing.Due


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    return str(value)


def notification_view(notification: Notification) -> dict[str, Any]:
    """A notification as the API and the export show it."""
    return {
        "id": notification.id,
        "kind": notification.kind,
        "period": notification.period,
        "subject": notification.subject,
        "text": notification.text,
        "items": [
            {"kind": i.kind, "title": i.title, "count": i.count, "date": i.date}
            for i in notification.items
        ],
        "link": notification.link,
    }


def delivery_view(row: dict[str, Any]) -> dict[str, Any]:
    """A row of the delivery log: what went, when, and its items."""
    return {
        "id": row["id"],
        "period": row["period"],
        "status": row["status"],
        "attempts": row["attempts"],
        "items": [
            {"kind": i.get("kind"), "count": i.get("count"), "date": i.get("date")}
            for i in row["items"]
        ],
        "hash": row["hash"],
        "created_at": _iso(row["created_at"]),
        "last_attempt_at": _iso(row["last_attempt_at"]),
        "sent_at": _iso(row["sent_at"]),
    }


def _ordered(items: list[str]) -> list[ItemKind]:
    return [k for k in ITEM_KINDS if k in items]


def _schedule(preferences: dict[str, Any], time_zone: str) -> Schedule:
    return Schedule(
        cadence=cast(Cadence, preferences["cadence"]),
        weekday=cast(Weekday, preferences["weekday"]),
        hour=int(preferences["hour"]),
        zone=timing.zone(time_zone),
    )


class NotificationService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        reminders: ReminderService,
        insights: InsightsService,
        notifier: Notifier,
        *,
        notifier_name: str | None = None,
        public_url: str | None = None,
        clock: Callable[[], dt.datetime] = _utc_now,
        push_enabled: bool = False,
        keyring: Any = None,
        budget: Any = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._reminders = reminders
        self._insights = insights
        self._notifier = notifier
        #: The extension whose notifier is enabled; None when none is.
        self.notifier_name = notifier_name
        self._link = public_url.rstrip("/") if public_url else None
        self._now = clock
        #: Whether the deployment configured a push relay and can seal tokens.
        self.push_enabled = push_enabled and keyring is not None and keyring.available
        self._keyring: Any = keyring
        self._budget: Any = budget

    @property
    def sender_enabled(self) -> bool:
        """Whether this deployment has a notifier to deliver digests."""
        return self.notifier_name is not None

    # ── Preferences ──────────────────────────────────────────────────────────

    async def _read(self, user_id: str) -> tuple[dict[str, Any], str | None]:
        async with self._uow_factory() as uow:
            stored: dict[str, Any] | None = await uow.notifications.get_preferences(user_id)
            profile: dict[str, Any] | None = await uow.user_profiles.get(user_id)
        preferences: dict[str, Any] = {**DEFAULTS, **(stored or {})}
        preferences["items"] = _ordered(list(preferences["items"]))
        time_zone = profile.get("time_zone") if profile else None
        return preferences, (str(time_zone) if time_zone else None)

    def _view(self, preferences: dict[str, Any], time_zone: str | None) -> dict[str, Any]:
        next_at = None
        if preferences["enabled"] and time_zone:
            next_at = timing.next_digest(self._now(), _schedule(preferences, time_zone))
        return {
            "enabled": bool(preferences["enabled"]),
            "cadence": preferences["cadence"],
            "weekday": preferences["weekday"],
            "hour": int(preferences["hour"]),
            "items": list(preferences["items"]),
            "time_zone": time_zone,
            "next_at": _iso(next_at),
            "sender_enabled": self.sender_enabled,
        }

    async def preferences(self, user_id: str) -> dict[str, Any]:
        """The person's digest preferences and time zone, when the next digest
        would go, and whether this server can deliver one at all."""
        preferences, time_zone = await self._read(user_id)
        return self._view(preferences, time_zone)

    async def set_preferences(self, user_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Change the fields given: `enabled`, `cadence`, `weekday`, `hour`,
        `items`, `time_zone` (None clears it). Turning the digest on needs a
        time zone. `PreferencesError` says what can't be saved; nothing is."""
        preferences, time_zone = await self._read(user_id)
        if "cadence" in changes:
            if changes["cadence"] not in timing.CADENCES:
                raise PreferencesError("cadence is weekly or monthly")
            preferences["cadence"] = changes["cadence"]
        if "weekday" in changes:
            if changes["weekday"] not in timing.WEEKDAYS:
                raise PreferencesError(f"weekday is one of {', '.join(timing.WEEKDAYS)}")
            preferences["weekday"] = changes["weekday"]
        if "hour" in changes:
            hour = changes["hour"]
            if not isinstance(hour, int) or isinstance(hour, bool) or not 0 <= hour <= 23:
                raise PreferencesError("hour is a whole number from 0 to 23")
            preferences["hour"] = hour
        if "items" in changes:
            chosen = list(changes["items"])
            unknown = [k for k in chosen if k not in ITEM_KINDS]
            if unknown:
                raise PreferencesError(
                    f"unknown item {unknown[0]!r}: one of {', '.join(ITEM_KINDS)}"
                )
            if not chosen:
                raise PreferencesError("choose at least one item, or turn the digest off")
            preferences["items"] = _ordered(chosen)
        if "enabled" in changes:
            preferences["enabled"] = bool(changes["enabled"])
        zone_changed = "time_zone" in changes
        if zone_changed:
            given = changes["time_zone"]
            if given is not None:
                try:
                    timing.zone(str(given))
                except timing.TimeZoneError as exc:
                    raise PreferencesError(str(exc)) from exc
            time_zone = None if given is None else str(given)
        if preferences["enabled"] and not time_zone:
            raise PreferencesError(
                "a digest goes at your local hour: set your time zone (an IANA name, "
                "such as 'Europe/Lisbon') to turn it on"
            )
        async with self._uow_factory() as uow:
            if zone_changed:
                await uow.user_profiles.set_preference(user_id, "time_zone", time_zone)
            await uow.notifications.save_preferences(user_id, preferences)
        return self._view(preferences, time_zone)

    # ── The message ──────────────────────────────────────────────────────────

    async def _build(
        self,
        user_id: str,
        preferences: dict[str, Any],
        schedule: Schedule,
        today: dt.date,
        period: str,
    ) -> Notification | None:
        chosen: list[ItemKind] = _ordered(list(preferences["items"]))
        async with self._uow_factory() as uow:
            rows = await uow.reminders.list_reminders(user_id, "pending")
        facts: list[ReminderFact] = []
        for row in rows:
            try:
                due = dt.date.fromisoformat(str(row["due_date"]))
            except ValueError:
                continue
            source = row.get("source_domain")
            facts.append(ReminderFact(source, due, row.get("status") == "done"))
        cash = None
        if "cash_below_zero_ahead" in chosen:
            cash = await self._insights.cash_below_zero_on(user_id, today)
        count, since = 0, None
        if "transactions_to_review" in chosen:
            count, since = await self._insights.transactions_waiting(user_id)
        items = waiting_items(
            Waiting(facts, cash, count, since),
            today,
            timing.reminders_until(today, schedule),
            chosen,
        )
        return build_digest(
            user_id,
            items,
            period=period,
            cadence=schedule.cadence,
            today=today,
            link=self._link,
        )

    async def preview(self, user_id: str) -> dict[str, Any]:
        """The digest that would go now, built by the same code as a real
        one, sending nothing and writing nothing. Without a time zone it is
        read in UTC, and says so."""
        preferences, time_zone = await self._read(user_id)
        schedule = _schedule(preferences, time_zone or "UTC")
        today = self._now().astimezone(schedule.zone).date()
        period = timing.period_of(today, schedule.cadence)
        notification = await self._build(user_id, preferences, schedule, today, period)
        if notification is None:
            note = "Nothing is waiting, so no digest would go."
        else:
            note = "This is the digest that would go if it went now."
        if not time_zone:
            note += " Read in UTC: set your time zone for your own dates and hour."
        if not preferences["enabled"]:
            note += " Digests are off for you."
        elif not self.sender_enabled:
            note += " This server has no notifier enabled, so nothing is sent yet."
        return {
            "period": period,
            "as_of": today.isoformat(),
            "time_zone": time_zone,
            "digest": None if notification is None else notification_view(notification),
            "note": note,
        }

    async def deliveries(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """What was delivered to the person, newest first: each period's
        status, attempts, items (kinds, counts, dates) and the message's hash."""
        async with self._uow_factory() as uow:
            rows = await uow.notifications.deliveries(user_id, limit)
        return [delivery_view(r) for r in rows]

    async def export(self, user_id: str) -> dict[str, Any]:
        """The person's preferences and delivery log, for "export my data"."""
        async with self._uow_factory() as uow:
            stored = await uow.notifications.get_preferences(user_id)
            rows = await uow.notifications.deliveries(user_id, 10_000)
        return {
            "notification_preferences": None
            if stored is None
            else {**stored, "updated_at": _iso(stored.get("updated_at"))},
            "notification_deliveries": [delivery_view(r) for r in rows],
        }

    # ── Sending ──────────────────────────────────────────────────────────────

    async def due(self, now: dt.datetime | None = None) -> list[DueDigest]:
        """Everyone opted in whose digest's hour it is now."""
        now = now or self._now()
        async with self._uow_factory() as uow:
            rows = await uow.notifications.opted_in()
        found: list[DueDigest] = []
        for row in rows:
            try:
                schedule = _schedule(row, str(row["time_zone"]))
            except ValueError:
                _log.warning("digest_schedule_unreadable user=%s", row["user_id"])
                continue
            when = timing.due(now, schedule)
            if when is not None:
                found.append(DueDigest(str(row["user_id"]), row, schedule, when))
        return found

    async def send_due(
        self, now: dt.datetime | None = None, due: list[DueDigest] | None = None
    ) -> dict[str, Any]:
        """Send each digest due now (`due`, or whoever `self.due(now)` finds),
        one at a time. Without a notifier, nothing: `notifier` is None."""
        counts: dict[str, Any] = {
            "notifier": self.notifier_name,
            "due": 0,
            "sent": 0,
            "nothing_waiting": 0,
            "no_destination": 0,
            "failed": 0,
            "skipped": 0,
        }
        if not self.sender_enabled:
            return counts
        now = now or self._now()
        async with self._uow_factory() as uow:
            await uow.notifications.record_run(now)
        if due is None:
            due = await self.due(now)
        counts["due"] = len(due)
        for digest in due:
            try:
                outcome = await self._deliver(digest, now)
            except Exception as exc:  # noqa: BLE001 — one person's failure must not stop the rest
                # The type only: an exception's text may quote the person's data.
                _log.warning(
                    "digest_failed user=%s period=%s error=%s",
                    digest.user_id,
                    digest.due.period,
                    type(exc).__name__,
                )
                outcome = "failed"
            counts[outcome] += 1
        return counts

    async def _deliver(self, digest: DueDigest, now: dt.datetime) -> str:
        user_id, when = digest.user_id, digest.due
        async with self._uow_factory() as uow:
            existing = await uow.notifications.delivery(user_id, when.period)
        retry = (
            existing is not None
            and existing["status"] == Delivery.FAILED.value
            and int(existing["attempts"]) < MAX_ATTEMPTS
        )
        if (existing is not None and not retry) or (existing is None and not when.first):
            return "skipped"
        # Alerts current before the digest reads them, as of their own day.
        await self._reminders.sync_alerts(user_id, when.today.isoformat())
        notification = await self._build(
            user_id, digest.preferences, digest.schedule, when.today, when.period
        )
        if notification is None:
            return "nothing_waiting"
        async with self._uow_factory() as uow:
            attempt = await uow.notifications.claim(
                user_id,
                delivery_id=notification.id,
                period=when.period,
                items=[item_record(i) for i in notification.items],
                message_hash=message_hash(notification),
                now=now,
                first=when.first,
                max_attempts=MAX_ATTEMPTS,
            )
        if attempt is None:
            return "skipped"
        try:
            outcome = Delivery(await self._notifier.send(notification))
        except Exception as exc:  # noqa: BLE001 — a sender's failure is a FAILED delivery
            _log.warning(
                "digest_send_failed user=%s period=%s attempt=%s error=%s",
                user_id,
                when.period,
                attempt,
                type(exc).__name__,
            )
            outcome = Delivery.FAILED
        async with self._uow_factory() as uow:
            await uow.notifications.finish(user_id, notification.id, outcome.value, now)
        if outcome is Delivery.FAILED:
            _log.warning(
                "digest_not_delivered user=%s period=%s attempt=%s",
                user_id,
                when.period,
                attempt,
            )
        return outcome.value

    async def last_run(self) -> dt.datetime | None:
        """When `send_due` last ran with a notifier enabled."""
        async with self._uow_factory() as uow:
            return await uow.notifications.last_run()

    # ── Push alerts ──────────────────────────────────────────────────────────

    async def add_device(self, user_id: str, token: str, platform: str) -> dict[str, Any]:
        """Register a phone for push alerts: its Expo token, sealed with the
        key ring, found by its hash (the device's id). PushUnavailable when
        this server sends none."""
        if not self.push_enabled:
            raise PushUnavailable(
                "This server sends no push alerts: its owner sets SALLI_PUSH_RELAY_URL "
                "(and BYOK_ENCRYPTION_KEYS) to turn them on."
            )
        digest = token_hash(token)
        sealed, version = self._keyring.seal(token, aad=_token_aad(digest))
        async with self._uow_factory() as uow:
            await uow.notifications.add_device(user_id, digest, sealed, version, platform)
            rows = await uow.notifications.devices(user_id)
        return next(_device_view(r) for r in rows if r["token_hash"] == digest)

    async def remove_device(self, user_id: str, device_id: str) -> bool:
        async with self._uow_factory() as uow:
            return await uow.notifications.remove_device(user_id, device_id)

    async def devices(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            rows = await uow.notifications.devices(user_id)
        return [_device_view(r) for r in rows]

    def open_token(self, device: dict[str, Any]) -> str:
        """A stored device's push token, for the relay notifier."""
        return self._keyring.open(
            device["token"], aad=_token_aad(device["token_hash"]), key_version=device["key_version"]
        )

    async def _push_items(self, user_id: str, today: dt.date) -> list[Any]:
        async with self._uow_factory() as uow:
            rows = await uow.reminders.list_reminders(user_id, "pending")
        facts: list[ReminderFact] = []
        for row in rows:
            try:
                due = dt.date.fromisoformat(str(row["due_date"]))
            except ValueError:
                continue
            facts.append(ReminderFact(row.get("source_domain"), due, row.get("status") == "done"))
        over = 0
        if self._budget is not None:
            lines, _ = await self._budget.current_lines(user_id)
            over = sum(1 for line in lines if line.left < 0)
        waiting = Waiting(
            facts,
            await self._insights.cash_below_zero_on(user_id, today),
            budgets_over=over,
            budget_month=today.replace(day=1),
        )
        return list(waiting_items(waiting, today, today, PUSH_ITEMS))

    async def send_pushes(self, now: dt.datetime | None = None) -> dict[str, Any]:
        """Send each person with a device the alert for what is waiting now
        (budget lines over, the cash forecast below zero, reminders due), once
        per state: the delivery log's row for the alert's period (a hash of
        its items) is claimed first. Without push, nothing: `enabled` false."""
        counts: dict[str, Any] = {
            "enabled": self.push_enabled,
            "people": 0,
            "sent": 0,
            "nothing_waiting": 0,
            "no_destination": 0,
            "failed": 0,
            "skipped": 0,
        }
        if not self.push_enabled:
            return counts
        now = now or self._now()
        async with self._uow_factory() as uow:
            people = await uow.notifications.device_users()
        counts["people"] = len(people)
        for person in people:
            user_id = str(person["user_id"])
            try:
                zone = timing.zone(str(person["time_zone"] or "UTC"))
            except timing.TimeZoneError:
                zone = timing.zone("UTC")
            today = now.astimezone(zone).date()
            try:
                outcome = await self._push(user_id, today, now)
            except Exception as exc:  # noqa: BLE001 — one person's failure must not stop the rest
                _log.warning("push_failed user=%s error=%s", user_id, type(exc).__name__)
                outcome = "failed"
            counts[outcome] += 1
        return counts

    async def _push(self, user_id: str, today: dt.date, now: dt.datetime) -> str:
        await self._reminders.sync_alerts(user_id, today.isoformat())
        notification = build_push(user_id, await self._push_items(user_id, today), link=self._link)
        if notification is None:
            return "nothing_waiting"
        async with self._uow_factory() as uow:
            attempt = await uow.notifications.claim(
                user_id,
                delivery_id=notification.id,
                period=notification.period,
                items=[item_record(i) for i in notification.items],
                message_hash=message_hash(notification),
                now=now,
                first=True,
                max_attempts=MAX_ATTEMPTS,
            )
        if attempt is None:
            return "skipped"
        try:
            outcome = Delivery(await self._notifier.send(notification))
        except Exception as exc:  # noqa: BLE001 — a sender's failure is a FAILED delivery
            _log.warning("push_send_failed user=%s error=%s", user_id, type(exc).__name__)
            outcome = Delivery.FAILED
        async with self._uow_factory() as uow:
            await uow.notifications.finish(user_id, notification.id, outcome.value, now)
        return outcome.value


def _device_view(row: dict[str, Any]) -> dict[str, Any]:
    """A device as the API shows it: never its token."""
    return {
        "id": row["token_hash"],
        "platform": row["platform"],
        "created_at": _iso(row["created_at"]),
    }
