"""
Budget router — category budget limits per period and their summary against
actual ledger spend.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/budget", tags=["budget"])


class BudgetLineRequest(BaseModel):
    account_id: str
    limit_amount: float


class BudgetRequest(BaseModel):
    period_start: str  # YYYY-MM-DD
    period_end: str  # YYYY-MM-DD
    lines: list[BudgetLineRequest]


class BudgetUpdateRequest(BaseModel):
    period_start: str | None = None
    period_end: str | None = None
    lines: list[BudgetLineRequest] | None = None


@router.get("/")
async def list_budgets(user_id: CurrentUser, svc: AppServices):
    return {"budgets": await svc.budget.list_budgets(user_id)}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_budget(body: BudgetRequest, user_id: CurrentUser, svc: AppServices):
    budget_id = await svc.budget.create_budget(
        user_id, body.period_start, body.period_end, [line.model_dump() for line in body.lines]
    )
    return {"id": budget_id}


@router.get("/{budget_id}")
async def get_budget(budget_id: str, user_id: CurrentUser, svc: AppServices):
    budget = await svc.budget.get_budget(user_id, budget_id)
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


@router.get("/{budget_id}/summary")
async def get_budget_summary(budget_id: str, user_id: CurrentUser, svc: AppServices):
    """Category limits vs. actual ledger spend for the budget's period."""
    summary = await svc.budget.get_summary(user_id, budget_id)
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return summary


@router.patch("/{budget_id}")
async def update_budget(
    budget_id: str, body: BudgetUpdateRequest, user_id: CurrentUser, svc: AppServices
):
    data = body.model_dump(exclude_none=True)
    await svc.budget.update_budget(user_id, budget_id, data)
    return {"updated": True}


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(budget_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.budget.delete_budget(user_id, budget_id)
