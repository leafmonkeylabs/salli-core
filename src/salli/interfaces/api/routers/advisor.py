"""
Wealth Advisor router — run the advisor, browse reports, and act on
recommendations, plus the daily cron endpoint.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse

from salli.application.ports import Surface
from salli.config import Settings, get_settings
from salli.domain.usage import UsageLimitReached
from salli.interfaces.api.deps import AppServices, CurrentEmail, CurrentUser

router = APIRouter(prefix="/advisor", tags=["advisor"])


class DailyBriefingRequest(BaseModel):
    enabled: bool


@router.get("/daily-briefing")
async def get_daily_briefing(user_id: CurrentUser, svc: AppServices):
    """Whether the scheduled daily advisor run is on for this user."""
    return {"enabled": await svc.advisor.get_daily_briefing_enabled(user_id)}


@router.put("/daily-briefing", status_code=status.HTTP_204_NO_CONTENT)
async def set_daily_briefing(body: DailyBriefingRequest, user_id: CurrentUser, svc: AppServices):
    """Opt in or out of the scheduled daily run.

    Off by default: each run is a model call on the user's behalf, so it has to
    be something they asked for rather than something that happens to them.
    """
    await svc.advisor.set_daily_briefing_enabled(user_id, body.enabled)


@router.post("/run")
async def run_advisor(user_id: CurrentUser, email: CurrentEmail, svc: AppServices):
    """Run the Wealth Advisor now (passes the deployment's usage meter first)."""
    report = await svc.advisor.run_advisor(user_id, email, trigger="manual")
    view = await svc.entitlements.for_user(user_id, email)
    return view.shape(Surface.ADVISOR_REPORT, report)


@router.get("/reports")
async def list_reports(user_id: CurrentUser, email: CurrentEmail, svc: AppServices):
    reports = await svc.advisor.list_reports(user_id)
    view = await svc.entitlements.for_user(user_id, email)
    return {"reports": [view.shape(Surface.ADVISOR_REPORT, r) for r in reports]}


@router.get("/reports/latest")
async def latest_report(user_id: CurrentUser, email: CurrentEmail, svc: AppServices):
    report = await svc.advisor.get_latest_report(user_id)
    if not report:
        return {}
    view = await svc.entitlements.for_user(user_id, email)
    return view.shape(Surface.ADVISOR_REPORT, report)


@router.post("/reports/{report_id}/recommendations/{rec_id}/apply")
async def apply_recommendation(report_id: str, rec_id: str, user_id: CurrentUser, svc: AppServices):
    try:
        return await svc.advisor.apply_recommendation(user_id, report_id, rec_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/reports/{report_id}/recommendations/{rec_id}/dismiss")
async def dismiss_recommendation(
    report_id: str, rec_id: str, user_id: CurrentUser, svc: AppServices
):
    try:
        return await svc.advisor.dismiss_recommendation(user_id, report_id, rec_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Monthly briefing workflow (human-review gate before persisting) ────────────


class BriefingPrepareRequest(BaseModel):
    thread_id: str | None = None


class BriefingResumeRequest(BaseModel):
    thread_id: str
    decision: str  # "approve" | "edit" | "reject"


@router.post("/briefing/prepare")
async def prepare_briefing(
    body: BriefingPrepareRequest, user_id: CurrentUser, email: CurrentEmail, svc: AppServices
):
    """
    Run the monthly briefing workflow up to the human review gate. Returns the
    draft briefing for approval, or a gather-step error (e.g. a usage limit).
    """
    return await svc.agent.prepare_briefing(user_id, email, thread_id=body.thread_id)


@router.post("/briefing/resume")
async def resume_briefing(body: BriefingResumeRequest, svc: AppServices):
    """Resume the briefing workflow after human review and persist if approved."""
    return await svc.agent.resume_briefing(thread_id=body.thread_id, decision=body.decision)


# ── Daily scheduling (called by Supabase pg_cron, not end users) ──────────────


async def _run_due(svc) -> None:
    """Background: run the advisor for each opted-in user who is due; skip anyone
    the usage meter refuses."""
    due = await svc.advisor.due_users()
    for sub in due:
        try:
            await svc.advisor.run_advisor(sub["user_id"], None, trigger="scheduled")
        except UsageLimitReached:
            continue
        except Exception:
            continue


@router.post("/cron/run-due", status_code=status.HTTP_202_ACCEPTED)
async def cron_run_due(
    svc: AppServices,
    settings: Annotated[Settings, Depends(get_settings)],
    x_cron_secret: Annotated[str | None, Header()] = None,
):
    """Trigger the daily advisor for every opted-in user who is due. Auth: X-Cron-Secret header."""
    secret = settings.cron_secret
    if not secret or not x_cron_secret or not hmac.compare_digest(x_cron_secret, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cron secret")
    due = await svc.advisor.due_users()
    return JSONResponse(
        {"due": len(due), "scheduled": True},
        status_code=status.HTTP_202_ACCEPTED,
        background=BackgroundTask(_run_due, svc),
    )
