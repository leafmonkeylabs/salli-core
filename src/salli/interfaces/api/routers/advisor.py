"""
The monthly briefing: Salli's own figures and signals, narrated by the AI
with every figure filled in by Salli (domain/agents/briefing.py). Run one,
browse them, or prepare one for review before it is stored; plus the daily
cron endpoint. A briefing describes and never advises.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, status
from pydantic import BaseModel, ConfigDict

from salli.application.ports import Surface
from salli.domain.usage import UsageLimitReached
from salli.interfaces.api.deps import AppServices, CronSecret, CurrentEmail, CurrentUser

router = APIRouter(prefix="/advisor", tags=["advisor"])


class DailyBriefingRequest(BaseModel):
    enabled: bool


class DailyBriefingSetting(BaseModel):
    enabled: bool


@router.get("/daily-briefing")
async def get_daily_briefing(user_id: CurrentUser, svc: AppServices) -> DailyBriefingSetting:
    """Whether the scheduled daily briefing is on for this user."""
    return DailyBriefingSetting(enabled=await svc.advisor.get_daily_briefing_enabled(user_id))


@router.put("/daily-briefing", status_code=status.HTTP_204_NO_CONTENT)
async def set_daily_briefing(
    body: DailyBriefingRequest, user_id: CurrentUser, svc: AppServices
) -> None:
    """Opt in or out of the scheduled daily run.

    Off by default: each run is a model call on the user's behalf, so it has to
    be something they asked for rather than something that happens to them.
    """
    await svc.advisor.set_daily_briefing_enabled(user_id, body.enabled)


# ── Reports ────────────────────────────────────────────────────────────────────


Topic = Literal["cash", "spending", "saving", "debt", "independence", "goals", "assumptions"]


class BriefingNote(BaseModel):
    """One topic, in the AI's words with Salli's figures in them."""

    topic: Topic
    text: str


class BriefingFigure(BaseModel):
    """A figure of Salli's the briefing could name, as a person reads it."""

    label: str
    #: Formatted for reading ("1,234.50 EUR", "49.1%", "May 2042"): never parse it.
    value: str


class BriefingSignal(BaseModel):
    """One of Salli's signals, in its own words (`insights.signals`)."""

    model_config = ConfigDict(extra="allow")

    kind: str | None = None
    severity: str | None = None
    title: str | None = None
    detail: str | None = None


class BriefingAssumptions(BaseModel):
    """Whether the independence figures rest on placeholders."""

    status: Literal["placeholder", "user"] | None = None
    placeholders: list[str] = []


class AdvisoryReport(BaseModel):
    """A monthly briefing: a summary and notes in the AI's words, every figure
    in them Salli's own, and the figures, signals and assumptions it was
    written from. It describes; it never advises.

    A deployment's entitlement policy may withhold parts of it and add fields
    of its own, so every field is optional.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    user_id: str | None = None
    #: What started the run: "manual", "scheduled", or whatever the CLI was given.
    trigger: str | None = None
    summary: str | None = None
    notes: list[BriefingNote] | None = None
    #: By slot name.
    figures: dict[str, BriefingFigure] | None = None
    signals: list[BriefingSignal] | None = None
    assumptions: BriefingAssumptions | None = None
    created_at: str | None = None


class AdvisoryReportList(BaseModel):
    #: Newest first. Briefings only: the advisor's earlier reports are in the export.
    reports: list[AdvisoryReport]


# Shaped surfaces: what the entitlement policy withholds stays out of the
# response rather than coming back as null.
@router.post("/run", response_model_exclude_unset=True)
async def run_advisor(
    user_id: CurrentUser, email: CurrentEmail, svc: AppServices
) -> AdvisoryReport:
    """Write a briefing now (passes the deployment's usage meter first)."""
    report = await svc.advisor.run_advisor(user_id, email, trigger="manual")
    view = await svc.entitlements.for_user(user_id, email)
    return AdvisoryReport.model_validate(view.shape(Surface.ADVISOR_REPORT, report))


@router.get("/reports", response_model_exclude_unset=True)
async def list_reports(
    user_id: CurrentUser, email: CurrentEmail, svc: AppServices
) -> AdvisoryReportList:
    reports = await svc.advisor.list_reports(user_id)
    view = await svc.entitlements.for_user(user_id, email)
    return AdvisoryReportList.model_validate(
        {"reports": [view.shape(Surface.ADVISOR_REPORT, r) for r in reports]}
    )


@router.get("/reports/latest", response_model_exclude_unset=True)
async def latest_report(
    user_id: CurrentUser, email: CurrentEmail, svc: AppServices
) -> AdvisoryReport:
    """The newest report, or an empty object when there is none yet."""
    report = await svc.advisor.get_latest_report(user_id)
    if not report:
        return AdvisoryReport()
    view = await svc.entitlements.for_user(user_id, email)
    return AdvisoryReport.model_validate(view.shape(Surface.ADVISOR_REPORT, report))


# ── Monthly briefing workflow (human-review gate before persisting) ────────────


class BriefingPrepareRequest(BaseModel):
    thread_id: str | None = None


class BriefingResumeRequest(BaseModel):
    thread_id: str
    decision: str  # "approve" | "edit" | "reject"


class BriefingDraft(BaseModel):
    """A briefing before it is stored, as `AdvisoryReport` shows one."""

    summary: str
    notes: list[BriefingNote]
    figures: dict[str, BriefingFigure]
    signals: list[BriefingSignal]
    assumptions: BriefingAssumptions


class BriefingPrepared(BaseModel):
    """A draft briefing, held for review under `thread_id`."""

    thread_id: str
    #: Why the workflow stopped before review (a usage limit, say), leaving the
    #: draft empty; empty when it reached review.
    error: str
    briefing: BriefingDraft


class BriefingResumed(BaseModel):
    """The outcome of a review."""

    #: The stored report when approved; an empty object otherwise.
    report: AdvisoryReport
    #: Why nothing was stored; empty when the report was.
    error: str


@router.post("/briefing/prepare")
async def prepare_briefing(
    body: BriefingPrepareRequest, user_id: CurrentUser, email: CurrentEmail, svc: AppServices
) -> BriefingPrepared:
    """
    Run the monthly briefing workflow up to the human review gate. Returns the
    draft briefing for approval, or a gather-step error (e.g. a usage limit).
    """
    return BriefingPrepared.model_validate(
        await svc.agent.prepare_briefing(user_id, email, thread_id=body.thread_id)
    )


# The report is an empty object unless the briefing was approved: its absent
# fields stay absent rather than coming back as null.
@router.post("/briefing/resume", response_model_exclude_unset=True)
async def resume_briefing(
    body: BriefingResumeRequest, user_id: CurrentUser, svc: AppServices
) -> BriefingResumed:
    """Resume the caller's briefing workflow after human review and persist if approved."""
    return BriefingResumed.model_validate(
        await svc.agent.resume_briefing(
            user_id=user_id, thread_id=body.thread_id, decision=body.decision
        )
    )


# ── Daily scheduling (called by a scheduler, not end users) ───────────────────


class ScheduledAdvisorRuns(BaseModel):
    """The daily run, accepted: the advisor runs for each due user after this response."""

    #: Opted-in users who have not had a report today.
    due: int
    scheduled: bool


async def _run_due(svc, due: list[dict[str, Any]]) -> None:
    """Background: write a briefing for each due user; skip anyone the usage
    meter refuses."""
    for sub in due:
        try:
            await svc.advisor.run_advisor(sub["user_id"], None, trigger="scheduled")
        except UsageLimitReached:
            continue
        except Exception:
            continue


@router.post("/cron/run-due", status_code=status.HTTP_202_ACCEPTED, dependencies=[CronSecret])
async def cron_run_due(svc: AppServices, background: BackgroundTasks) -> ScheduledAdvisorRuns:
    """Write the daily briefing for every opted-in user who is due. Auth: X-Cron-Secret header."""
    due = await svc.advisor.due_users()
    # Runs after the response is sent, for the users counted in it.
    background.add_task(_run_due, svc, due)
    return ScheduledAdvisorRuns(due=len(due), scheduled=True)
