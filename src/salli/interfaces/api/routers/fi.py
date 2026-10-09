"""
Financial Independence router — FI score, goals, AI FIRE strategy, projections, surplus.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from salli.application.ports import PayloadView, Surface
from salli.domain.usage import AIAction
from salli.interfaces.api.deps import AppServices, CurrentEmail, CurrentUser

router = APIRouter(prefix="/fi", tags=["financial-independence"])

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


# ── Score ─────────────────────────────────────────────────────────────────────


async def _gate_strategy_stream(
    upstream: AsyncGenerator[str, None], view: PayloadView
) -> AsyncGenerator[str, None]:
    """Pass status/error SSE events straight through; shape only the final
    `done` event's `strategy` payload for the caller."""
    async for chunk in upstream:
        payload = chunk.removeprefix("data: ").rstrip("\n")
        try:
            event: dict[str, Any] = json.loads(payload)
        except json.JSONDecodeError:
            yield chunk
            continue
        if event.get("type") == "done" and "strategy" in event:
            event["strategy"] = view.shape(Surface.FIRE_STRATEGY, event["strategy"])
        yield f"data: {json.dumps(event, default=str)}\n\n"


@router.get("/score")
async def get_score(user_id: CurrentUser, svc: AppServices):
    """Latest FI score, computing one on first access."""
    return await svc.fi.get_or_compute_score(user_id)


@router.post("/score/recompute")
async def recompute_score(user_id: CurrentUser, svc: AppServices):
    """Recompute the FI score from the current ledger and store a snapshot."""
    return await svc.fi.compute_score(user_id)


@router.get("/score/history")
async def score_history(user_id: CurrentUser, svc: AppServices):
    return {"history": await svc.fi.get_score_history(user_id)}


# ── Goals ─────────────────────────────────────────────────────────────────────


class GoalRequest(BaseModel):
    name: str
    kind: str = "custom"
    # Decimal, not float — this is money, and the project's own invariant says
    # so. `current_amount` is gone: progress is derived from allocations against
    # real accounts, never typed in.
    target_amount: Decimal = Decimal(0)
    target_date: str | None = None
    # 1 high … 3 low. Decides which goal stays funded when one account is
    # claimed by several.
    priority: int = 2


class GoalUpdateRequest(BaseModel):
    name: str | None = None
    kind: str | None = None
    target_amount: Decimal | None = None
    target_date: str | None = None
    priority: int | None = None
    is_active: bool | None = None


@router.get("/goals")
async def list_goals(user_id: CurrentUser, svc: AppServices):
    return {"goals": await svc.fi.list_goals(user_id)}


@router.post("/goals", status_code=status.HTTP_201_CREATED)
async def create_goal(body: GoalRequest, user_id: CurrentUser, svc: AppServices):
    goal_id = await svc.fi.create_goal(user_id, body.model_dump())
    return {"id": goal_id}


@router.patch("/goals/{goal_id}")
async def update_goal(
    goal_id: str, body: GoalUpdateRequest, user_id: CurrentUser, svc: AppServices
):
    await svc.fi.update_goal(user_id, goal_id, body.model_dump(exclude_none=True))
    return {"updated": True}


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(goal_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.fi.delete_goal(user_id, goal_id)


# ── FIRE Strategy ──────────────────────────────────────────────────────────────


@router.get("/strategy")
async def get_strategy(user_id: CurrentUser, email: CurrentEmail, svc: AppServices):
    """Return the user's active FIRE strategy, or 404 if none exists yet."""
    strategy = await svc.fi.get_strategy(user_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No FIRE strategy found")
    view = await svc.entitlements.for_user(user_id, email)
    return view.shape(Surface.FIRE_STRATEGY, strategy)


@router.get("/strategy/history")
async def get_strategy_history(user_id: CurrentUser, email: CurrentEmail, svc: AppServices):
    """List all strategy versions (summary only)."""
    history = await svc.fi.get_strategy_history(user_id)
    view = await svc.entitlements.for_user(user_id, email)
    return {"history": [view.shape(Surface.FIRE_STRATEGY, h) for h in history]}


@router.post("/strategy/generate")
async def generate_strategy(user_id: CurrentUser, email: CurrentEmail, svc: AppServices):
    """
    Trigger AI FIRE strategy generation. Returns an SSE stream.

    Stream events:
      {"type": "status",  "message": "..."} — progress updates
      {"type": "done",    "strategy": {...}} — final result
      {"type": "error",   "message": "..."}  — failure

    Passes the deployment's usage meter like /agent/chat — checked before the
    stream opens, same as chat, rather than mid-stream.
    """
    model_id = await svc.profile.get_preferred_model(user_id)
    await svc.usage.charge(user_id, AIAction.FIRE_STRATEGY, model_id=model_id, email=email)
    view = await svc.entitlements.for_user(user_id, email)
    return StreamingResponse(
        _gate_strategy_stream(svc.fi.generate_strategy(user_id, email, model=model_id), view),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# ── Projections & Surplus ──────────────────────────────────────────────────────


@router.get("/projections")
async def get_projections(user_id: CurrentUser, email: CurrentEmail, svc: AppServices):
    """15-year portfolio projections across conservative/base/growth scenarios."""
    data = await svc.fi.get_projections(user_id)
    view = await svc.entitlements.for_user(user_id, email)
    return view.shape(Surface.FI_PROJECTIONS, data)


@router.get("/surplus")
async def get_surplus_breakdown(user_id: CurrentUser, svc: AppServices):
    """Income-by-source and expense-by-category breakdown from the trailing 12 months."""
    return await svc.fi.get_surplus_breakdown(user_id)


# ── "Can I afford this?" ──────────────────────────────────────────────────────


class PurchaseRequest(BaseModel):
    """
    Money arrives as a STRING and is parsed to Decimal, never float — a float in
    the money path is a bug (CLAUDE.md). `annual_interest_rate` is a fraction
    (0.18 = 18%), bounded so a caller passing 18 is rejected rather than
    silently costing the plan ~100x too dearly.
    """

    amount: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]
    term_months: Annotated[int | None, Field(default=None, ge=1, le=600)] = None
    annual_interest_rate: Annotated[Decimal, Field(default=Decimal(0), ge=0, le=1)] = Decimal(0)


@router.post("/simulate-purchase")
async def simulate_purchase(body: PurchaseRequest, user_id: CurrentUser, svc: AppServices):
    """
    Cost a prospective purchase in months of freedom, comparing cash against
    instalments.

    Deliberately NOT metered: it is pure deterministic engine math with no LLM
    call, and it is the loop the product exists for — throttling it would teach
    users not to ask.
    """
    return await svc.fi.simulate_purchase(
        user_id,
        body.amount,
        term_months=body.term_months,
        annual_interest_rate=body.annual_interest_rate,
    )


# ── goal allocations ──────────────────────────────────────────────────────────
#
# An allocation earmarks part of a real account for a goal. Progress is derived
# from what that account actually holds, so it moves when money moves — unlike
# the old `current_amount`, which was a number the user typed and then had to
# maintain by hand.
#
# One account can back several goals. When their claims exceed the balance the
# shortfall is reported rather than rejected, and the balance is apportioned by
# the goals' `priority`.


class AllocationRequest(BaseModel):
    account_id: str
    allocated_amount: Decimal


@router.get("/goals/{goal_id}/allocations")
async def list_goal_allocations(goal_id: str, user_id: CurrentUser, svc: AppServices):
    return {"allocations": await svc.fi.list_allocations(user_id, goal_id)}


@router.put("/goals/{goal_id}/allocations")
async def set_goal_allocation(
    goal_id: str, body: AllocationRequest, user_id: CurrentUser, svc: AppServices
):
    """Earmark part of an account for this goal. An amount of 0 clears it."""
    try:
        await svc.fi.set_allocation(user_id, goal_id, body.account_id, body.allocated_amount)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return {"updated": True}
