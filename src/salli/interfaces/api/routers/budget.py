"""
Budget router — category budget limits per period and their summary against
actual ledger spend.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from salli.interfaces.api.contract import Amount, AmountIn, CurrencyCode, Ref, Updated
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/budget", tags=["budget"])


class BudgetLineRequest(BaseModel):
    account_id: str
    limit_amount: AmountIn


class BudgetRequest(BaseModel):
    period_start: str  # YYYY-MM-DD
    period_end: str  # YYYY-MM-DD
    lines: list[BudgetLineRequest]


class BudgetUpdateRequest(BaseModel):
    period_start: str | None = None
    period_end: str | None = None
    lines: list[BudgetLineRequest] | None = None


class BudgetLine(BaseModel):
    """A category limit: how much may be spent from one expense account."""

    account_id: str
    limit_amount: Amount


class Budget(BaseModel):
    id: str
    period_start: str  # YYYY-MM-DD
    period_end: str  # YYYY-MM-DD
    #: Limits are kept in the base currency, like the ledger spend they are compared with.
    currency: CurrencyCode
    lines: list[BudgetLine]
    created_at: str
    updated_at: str


class BudgetList(BaseModel):
    budgets: list[Budget]


class BudgetSummaryLine(BaseModel):
    account_id: str
    #: The expense account's name; its id when the account is not in the ledger.
    category: str
    limit_amount: Amount
    actual_amount: Amount
    #: Limit minus actual: negative means over budget.
    variance: Amount


class BudgetSummary(BaseModel):
    id: str
    period_start: str
    period_end: str
    currency: CurrencyCode
    total_limit: Amount
    total_actual: Amount
    total_variance: Amount
    lines: list[BudgetSummaryLine]


@router.get("/")
async def list_budgets(user_id: CurrentUser, svc: AppServices) -> BudgetList:
    return BudgetList.model_validate({"budgets": await svc.budget.list_budgets(user_id)})


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_budget(body: BudgetRequest, user_id: CurrentUser, svc: AppServices) -> Ref:
    budget_id = await svc.budget.create_budget(
        user_id, body.period_start, body.period_end, [line.model_dump() for line in body.lines]
    )
    return Ref(id=budget_id)


@router.get("/{budget_id}")
async def get_budget(budget_id: str, user_id: CurrentUser, svc: AppServices) -> Budget:
    budget = await svc.budget.get_budget(user_id, budget_id)
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return Budget.model_validate(budget)


@router.get("/{budget_id}/summary")
async def get_budget_summary(
    budget_id: str, user_id: CurrentUser, svc: AppServices
) -> BudgetSummary:
    """Category limits vs. actual ledger spend for the budget's period."""
    summary = await svc.budget.get_summary(user_id, budget_id)
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return BudgetSummary.model_validate(summary)


@router.patch("/{budget_id}")
async def update_budget(
    budget_id: str, body: BudgetUpdateRequest, user_id: CurrentUser, svc: AppServices
) -> Updated:
    data = body.model_dump(exclude_none=True)
    if await svc.budget.get_budget(user_id, budget_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such budget")
    await svc.budget.update_budget(user_id, budget_id, data)
    return Updated(updated=True)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(budget_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    await svc.budget.delete_budget(user_id, budget_id)
