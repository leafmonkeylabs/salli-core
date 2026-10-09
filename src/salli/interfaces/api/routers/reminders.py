"""
Reminders router — filing calendar, custom reminders, and system-detected
alerts (Reminder rows with alert_type/source_domain/source_id/severity set).

GET  /reminders             — list reminders (optional ?status, ?alerts_only)
POST /reminders             — create a custom reminder
POST /reminders/seed        — seed IRD filing deadlines for the current year
POST /reminders/sync-alerts — detect and upsert Budget/Subscription/Insurance alerts
PATCH /reminders/{id}/done  — mark a reminder complete
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("/")
async def list_reminders(
    user_id: CurrentUser,
    svc: AppServices,
    status: str | None = None,
    alerts_only: bool = False,
):
    reminders = await svc.reminders.list_reminders(user_id, status)
    if alerts_only:
        reminders = [r for r in reminders if r.get("alert_type")]
    return {"reminders": reminders}


class CreateReminderRequest(BaseModel):
    kind: str
    due_date: str  # YYYY-MM-DD


@router.post("/", status_code=201)
async def create_reminder(body: CreateReminderRequest, user_id: CurrentUser, svc: AppServices):
    reminder_id = await svc.reminders.create_reminder(user_id, body.kind, body.due_date)
    return {"id": reminder_id}


@router.post("/seed", status_code=201)
async def seed_filing_calendar(
    user_id: CurrentUser,
    svc: AppServices,
    year: str = "2025/26",
):
    """Seed the IRD filing deadlines for the given year of assessment."""
    created = await svc.reminders.seed_filing_calendar(user_id, year)
    return {"created": len(created), "ids": created}


@router.post("/sync-alerts", status_code=201)
async def sync_alerts(user_id: CurrentUser, svc: AppServices):
    """Detect current Budget/Subscription/Insurance alert conditions and
    upsert them as reminders. Idempotent — safe to call repeatedly."""
    today = datetime.date.today().isoformat()
    counts = await svc.reminders.sync_alerts(user_id, today)
    return {"counts": counts, "total": sum(counts.values())}


@router.patch("/{reminder_id}/done", status_code=204)
async def mark_done(reminder_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.reminders.mark_done(user_id, reminder_id)


@router.delete("/{reminder_id}", status_code=204)
async def delete_reminder(reminder_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.reminders.delete_reminder(user_id, reminder_id)
