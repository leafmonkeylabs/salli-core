"""
Reminders router — filing calendar, custom reminders, and system-detected
alerts (Reminder rows with alert_type/source_domain/source_id/severity set).

GET  /reminders             — list reminders (optional ?status, ?alerts_only)
POST /reminders             — create a custom reminder
POST /reminders/seed        — refresh filing deadlines from the active tax rule sets
POST /reminders/sync-alerts — detect and upsert Budget/Subscription/Insurance alerts
PATCH /reminders/{id}/done  — mark a reminder complete
"""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from salli.interfaces.api.contract import Ref
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/reminders", tags=["reminders"])


class Reminder(BaseModel):
    """Something due: a filing deadline, one the user set, or a detected alert."""

    id: str
    #: What is due, in words; for an alert, the condition ("Over budget on …").
    kind: str
    #: YYYY-MM-DD.
    due_date: str
    #: "pending" or "done".
    status: str
    #: Set on a detected alert ("budget_overspend", "policy_expiring", …), as
    #: are the three fields after it; null on a plain reminder.
    alert_type: str | None
    #: What it is about: "budget", "subscription" or "insurance" for an alert;
    #: "tax_rules" for a filing deadline from an active tax rule set.
    source_domain: str | None
    #: Which budget line, subscription or policy it is about; for a filing
    #: deadline, "<rule set id>:<deadline key>".
    source_id: str | None
    #: "warning" or "critical".
    severity: str | None
    created_at: str


class ReminderList(BaseModel):
    reminders: list[Reminder]


class SeededReminders(BaseModel):
    #: How many deadlines were added.
    created: int
    #: The ids of the reminders added.
    ids: list[str]
    #: Reminders whose label or date the rules changed (back to pending when
    #: the date moved).
    updated: list[str]
    #: Reminders for deadlines the active rules no longer list.
    removed: list[str]


class SyncedAlerts(BaseModel):
    #: Alert type → how many alerts of that type this run found.
    counts: dict[str, int]
    total: int


@router.get("/")
async def list_reminders(
    user_id: CurrentUser,
    svc: AppServices,
    status: str | None = None,
    alerts_only: bool = False,
) -> ReminderList:
    reminders = await svc.reminders.list_reminders(user_id, status)
    if alerts_only:
        reminders = [r for r in reminders if r.get("alert_type")]
    return ReminderList.model_validate({"reminders": reminders})


class CreateReminderRequest(BaseModel):
    kind: str
    due_date: str  # YYYY-MM-DD


@router.post("/", status_code=201)
async def create_reminder(
    body: CreateReminderRequest, user_id: CurrentUser, svc: AppServices
) -> Ref:
    reminder_id = await svc.reminders.create_reminder(user_id, body.kind, body.due_date)
    return Ref(id=reminder_id)


@router.post("/seed", status_code=201)
async def seed_filing_calendar(
    user_id: CurrentUser,
    svc: AppServices,
    year: Annotated[str | None, Query(examples=["2031/32"])] = None,
) -> SeededReminders:
    """Refresh the filing reminders from the deadlines of the user's active tax
    rule sets (one year's, when `year` names it). Activating a version does
    this already; this catches a calendar up. Idempotent."""
    synced = await svc.reminders.seed_filing_calendar(user_id, year)
    return SeededReminders(
        created=len(synced["created"]),
        ids=synced["created"],
        updated=synced["updated"],
        removed=synced["removed"],
    )


@router.post("/sync-alerts", status_code=201)
async def sync_alerts(user_id: CurrentUser, svc: AppServices) -> SyncedAlerts:
    """Detect current Budget/Subscription/Insurance alert conditions and
    upsert them as reminders. Idempotent — safe to call repeatedly."""
    today = datetime.date.today().isoformat()
    counts = await svc.reminders.sync_alerts(user_id, today)
    return SyncedAlerts(counts=counts, total=sum(counts.values()))


@router.patch("/{reminder_id}/done", status_code=204)
async def mark_done(reminder_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.reminders.mark_done(user_id, reminder_id)


@router.delete("/{reminder_id}", status_code=204)
async def delete_reminder(reminder_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.reminders.delete_reminder(user_id, reminder_id)
