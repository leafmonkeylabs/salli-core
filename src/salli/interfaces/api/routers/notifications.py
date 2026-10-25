"""
Notifications router — a person's digest: their preferences and time zone, a
preview of the message, and the log of what was delivered; plus the hourly
cron route a scheduler calls (docs/design/decision-lab-phase-3.md, section 4).

A digest says what is waiting, never what it is about: kinds of item,
counts, dates and a link. Core builds it; the deployment's notifier, if it
has one, delivers it.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field

from salli.application.services.notification_service import PreferencesError
from salli.domain.notifications.digest import ItemKind
from salli.domain.notifications.schedule import Cadence, Weekday
from salli.interfaces.api.deps import AppServices, CronSecret, CurrentUser

router = APIRouter(prefix="/notifications", tags=["notifications"])


PushItem = Literal["reminder_due", "cash_below_zero_ahead", "budget_over"]
#: A local time, "22:00".
Clock = Annotated[str, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")]


class QuietHours(BaseModel):
    """When no push alert goes, in the person's time zone; it may run past
    midnight. What waits through them goes after."""

    start: Clock
    end: Clock


class NotificationPreferences(BaseModel):
    """A person's digest: off until they turn it on."""

    enabled: bool
    #: weekly, or monthly (on the month's first chosen weekday).
    cadence: Cadence
    weekday: Weekday
    #: The local hour it goes, 0 to 23. No other hour sends anything.
    hour: int
    #: What it may hold. By default everything but `transactions_to_review`.
    items: list[ItemKind]
    #: The push alerts this person's phones take; all three by default.
    push_items: list[PushItem]
    #: Null: push alerts go at any hour.
    quiet_hours: QuietHours | None
    #: An IANA time zone ("Europe/Lisbon"); turning digests on needs one.
    time_zone: str | None
    #: When the next digest's hour begins, in the person's time zone (ISO
    #: 8601), while digests are on.
    next_at: str | None
    #: Whether this server has a notifier to deliver digests. Without one,
    #: preferences still save and the preview works; nothing is sent.
    sender_enabled: bool


class NotificationPreferencesUpdate(BaseModel):
    """Only the fields given change."""

    enabled: bool | None = None
    cadence: Cadence | None = None
    weekday: Weekday | None = None
    hour: Annotated[int, Field(ge=0, le=23)] | None = None
    #: Replaces the chosen items; at least one.
    items: list[ItemKind] | None = None
    #: Replaces the push alerts chosen; an empty list takes none.
    push_items: list[PushItem] | None = None
    #: An explicit null clears them.
    quiet_hours: QuietHours | None = None
    #: An IANA time zone name; an explicit null clears it (refused while
    #: digests are on).
    time_zone: Annotated[str, Field(min_length=1, max_length=64)] | None = None


class DigestItem(BaseModel):
    """One kind of thing waiting, in Salli's own words."""

    kind: ItemKind
    title: str
    count: int
    #: The earliest date it concerns (YYYY-MM-DD).
    date: str | None


class Digest(BaseModel):
    """A digest, exactly as a notifier would be given it."""

    #: Stable for the person and period: a sender's idempotency key.
    id: str
    kind: Literal["digest"]
    #: "2026-W42" or "2026-10".
    period: str
    subject: str
    #: Plain text, complete as it is.
    text: str
    items: list[DigestItem]
    #: The server's public URL; never a token.
    link: str | None


class DigestPreview(BaseModel):
    """The digest that would go now. Nothing is sent or stored."""

    period: str
    #: The person's local date it is read as of.
    as_of: str
    time_zone: str | None
    #: Null when nothing is waiting: then no digest would go.
    digest: Digest | None
    note: str


class DeliveredItem(BaseModel):
    kind: ItemKind
    count: int
    date: str | None


class DigestDelivery(BaseModel):
    """One period's digest in the delivery log. The log keeps the items and
    the message's hash, never its text."""

    id: str
    period: str
    #: sent, no_destination (the deployment had nowhere to send it), failed
    #: (tried again at the same hour on a later day of the period, three
    #: attempts in all), or sending (an attempt whose outcome was never
    #: recorded: it may have gone, so it is not tried again).
    status: Literal["sending", "sent", "no_destination", "failed"]
    attempts: int
    items: list[DeliveredItem]
    #: "sha256:" over the message's canonical JSON.
    hash: str
    created_at: str
    last_attempt_at: str
    sent_at: str | None


class DigestDeliveries(BaseModel):
    #: Newest first.
    deliveries: list[DigestDelivery]


class ScheduledDigests(BaseModel):
    """Accepted: each digest due this hour is sent after this response."""

    #: People in their digest's hour now.
    due: int
    #: False when this server has no notifier: nothing is sent.
    scheduled: bool


@router.get("/preferences")
async def get_preferences(user_id: CurrentUser, svc: AppServices) -> NotificationPreferences:
    """Your digest preferences and time zone."""
    return NotificationPreferences.model_validate(await svc.notifications.preferences(user_id))


@router.patch("/preferences")
async def update_preferences(
    body: NotificationPreferencesUpdate, user_id: CurrentUser, svc: AppServices
) -> NotificationPreferences:
    """Turn your digest on or off, or change when it goes and what it holds;
    choose the push alerts your phones take and their quiet hours. Turning
    the digest on needs a time zone."""
    changes: dict[str, Any] = body.model_dump(exclude_none=True)
    for field in ("time_zone", "quiet_hours"):
        if field in body.model_fields_set and getattr(body, field) is None:
            changes[field] = None
    try:
        saved = await svc.notifications.set_preferences(user_id, changes)
    except PreferencesError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return NotificationPreferences.model_validate(saved)


@router.get("/preview")
async def preview(user_id: CurrentUser, svc: AppServices) -> DigestPreview:
    """The digest that would go now, built by the same code as a real one.
    Sends nothing and stores nothing."""
    return DigestPreview.model_validate(await svc.notifications.preview(user_id))


@router.get("/deliveries")
async def deliveries(
    user_id: CurrentUser,
    svc: AppServices,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> DigestDeliveries:
    """What was delivered to you: each period's status, items and hash."""
    return DigestDeliveries(
        deliveries=[
            DigestDelivery.model_validate(d)
            for d in await svc.notifications.deliveries(user_id, limit)
        ]
    )


@router.post("/cron/send-due", status_code=status.HTTP_202_ACCEPTED, dependencies=[CronSecret])
async def cron_send_due(svc: AppServices, background: BackgroundTasks) -> ScheduledDigests:
    """Send the digests due this hour, for a scheduler (call it hourly).
    Auth: X-Cron-Secret header. `salli-server jobs send-digests` does the same."""
    notifications = svc.notifications
    if not notifications.sender_enabled:
        return ScheduledDigests(due=0, scheduled=False)
    due = await notifications.due()
    # The same list it counts: found once, then sent.
    background.add_task(notifications.send_due, due=due)
    return ScheduledDigests(due=len(due), scheduled=True)
