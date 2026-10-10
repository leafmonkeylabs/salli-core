"""
Wealth Advisor router — run the advisor, browse reports, and act on
recommendations, plus the daily cron endpoint.
"""

from __future__ import annotations

import hmac
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict

from salli.application.ports import Surface
from salli.config import Settings, get_settings
from salli.domain.usage import UsageLimitReached
from salli.interfaces.api.deps import AppServices, CurrentEmail, CurrentUser

router = APIRouter(prefix="/advisor", tags=["advisor"])


class DailyBriefingRequest(BaseModel):
    enabled: bool


class DailyBriefingSetting(BaseModel):
    enabled: bool


@router.get("/daily-briefing")
async def get_daily_briefing(user_id: CurrentUser, svc: AppServices) -> DailyBriefingSetting:
    """Whether the scheduled daily advisor run is on for this user."""
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


class AdvisoryActionParams(BaseModel):
    """What applying a recommendation sets up: a reminder's label and due date."""

    model_config = ConfigDict(extra="allow")

    label: str | None = None
    #: Days from when it is applied.
    due_in_days: int | None = None


class AdvisoryRecommendation(BaseModel):
    """A recommendation in an advisory report, and what became of it."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    title: str | None = None
    rationale: str | None = None
    #: emergency_fund | debt | savings | investing | spending | tax | goal |
    #: bucket_allocation, as the model chose.
    category: str | None = None
    #: 1 high … 3 low.
    priority: int | None = None
    #: The FIRE strategy bucket it is about, if any.
    bucket_key: str | None = None
    #: What applying it does: "reminder" creates one; "none" only marks it applied.
    action_type: str | None = None
    action_params: AdvisoryActionParams | None = None
    status: Literal["pending", "applied", "dismissed"] | None = None


class AdvisoryReport(BaseModel):
    """A Wealth Advisor run: a summary, and recommendations to act on.

    A report just run carries `fire_tier_assessment`; a stored one carries
    `user_id` and `created_at`. A deployment's entitlement policy may withhold
    parts of it and add fields of its own, so every field is optional.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    user_id: str | None = None
    #: What started the run: "manual", "scheduled", or whatever the CLI was given.
    trigger: str | None = None
    fi_score_id: str | None = None
    summary: str | None = None
    fire_tier_assessment: str | None = None
    recommendations: list[AdvisoryRecommendation] | None = None
    created_at: str | None = None


class AdvisoryReportList(BaseModel):
    #: Newest first.
    reports: list[AdvisoryReport]


class RecommendationStatus(BaseModel):
    id: str
    status: Literal["applied", "dismissed"]


# Shaped surfaces: what the entitlement policy withholds stays out of the
# response rather than coming back as null.
@router.post("/run", response_model_exclude_unset=True)
async def run_advisor(
    user_id: CurrentUser, email: CurrentEmail, svc: AppServices
) -> AdvisoryReport:
    """Run the Wealth Advisor now (passes the deployment's usage meter first)."""
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


@router.post("/reports/{report_id}/recommendations/{rec_id}/apply")
async def apply_recommendation(
    report_id: str, rec_id: str, user_id: CurrentUser, svc: AppServices
) -> RecommendationStatus:
    try:
        result = await svc.advisor.apply_recommendation(user_id, report_id, rec_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return RecommendationStatus.model_validate(result)


@router.post("/reports/{report_id}/recommendations/{rec_id}/dismiss")
async def dismiss_recommendation(
    report_id: str, rec_id: str, user_id: CurrentUser, svc: AppServices
) -> RecommendationStatus:
    try:
        result = await svc.advisor.dismiss_recommendation(user_id, report_id, rec_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return RecommendationStatus.model_validate(result)


# ── Monthly briefing workflow (human-review gate before persisting) ────────────


class BriefingPrepareRequest(BaseModel):
    thread_id: str | None = None


class BriefingResumeRequest(BaseModel):
    thread_id: str
    decision: str  # "approve" | "edit" | "reject"


class BriefingAction(BaseModel):
    """What applying the recommendation would set up."""

    type: Literal["none", "reminder"]
    label: str
    #: For a reminder, days from when it is applied.
    due_in_days: int | None


class BriefingRecommendation(BaseModel):
    """A recommendation in a draft briefing, before it is stored with an id and a status."""

    title: str
    rationale: str
    category: str
    #: 1 high … 3 low.
    priority: int
    bucket_key: str | None
    action: BriefingAction


class BriefingDraft(BaseModel):
    summary: str
    fire_tier_assessment: str
    recommendations: list[BriefingRecommendation]


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
async def resume_briefing(body: BriefingResumeRequest, svc: AppServices) -> BriefingResumed:
    """Resume the briefing workflow after human review and persist if approved."""
    return BriefingResumed.model_validate(
        await svc.agent.resume_briefing(thread_id=body.thread_id, decision=body.decision)
    )


# ── Daily scheduling (called by Supabase pg_cron, not end users) ──────────────


class ScheduledAdvisorRuns(BaseModel):
    """The daily run, accepted: the advisor runs for each due user after this response."""

    #: Opted-in users who have not had a report today.
    due: int
    scheduled: bool


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
    background: BackgroundTasks,
    x_cron_secret: Annotated[str | None, Header()] = None,
) -> ScheduledAdvisorRuns:
    """Trigger the daily advisor for every opted-in user who is due. Auth: X-Cron-Secret header."""
    secret = settings.cron_secret
    if not secret or not x_cron_secret or not hmac.compare_digest(x_cron_secret, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cron secret")
    due = await svc.advisor.due_users()
    # Runs after the response is sent, as it did when this returned its own
    # JSONResponse with a background task.
    background.add_task(_run_due, svc)
    return ScheduledAdvisorRuns(due=len(due), scheduled=True)
