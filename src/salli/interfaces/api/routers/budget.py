"""
Budget router — category budget limits per period and their summary against
actual ledger spend.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
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


class MonthlyLineRequest(BaseModel):
    #: One of your expense accounts.
    account_id: str
    limit_amount: AmountIn
    #: What is left at a month's end carries to the next (an overspend
    #: carries nothing).
    rollover: bool = False


class MonthlyBudgetRequest(BaseModel):
    lines: list[MonthlyLineRequest]


class MonthlyLine(BaseModel):
    account_id: str
    limit_amount: Amount
    rollover: bool
    #: The first month it applies to ("YYYY-MM").
    since: str


class MonthlyBudget(BaseModel):
    """A limit per expense account that recurs every calendar month."""

    #: The base currency, like the spending it is compared with.
    currency: CurrencyCode
    lines: list[MonthlyLine]


class CurrentBudgetLine(BaseModel):
    account_id: str
    category: str
    limit_amount: Amount
    #: Rolled over from the months before (rollover lines only).
    carried: Amount
    #: Limit plus carried.
    available: Amount
    #: The account's net spending this month so far.
    spent: Amount
    #: Available less spent: negative means over.
    left: Amount
    #: The share of `available` matching the share of the month gone.
    expected_by_now: Amount
    #: "over" when spent is more than `expected_by_now`.
    pace: Literal["over", "within"]


class CurrentBudget(BaseModel):
    #: "YYYY-MM".
    month: str
    as_of: str
    currency: CurrencyCode
    #: The share of the month gone, today included, as a decimal string.
    month_gone: str
    lines: list[CurrentBudgetLine]


class CategoryTrend(BaseModel):
    account_id: str
    category: str
    #: Net spending in each of `months`, in order.
    spent: list[Amount]


class SpendingTrend(BaseModel):
    currency: CurrencyCode
    #: The calendar months, oldest first; the last is this month so far.
    months: list[str]
    #: Net spending across every category in each of `months`, in order.
    totals: list[Amount]
    categories: list[CategoryTrend]


@router.get("/monthly")
async def get_monthly_budget(user_id: CurrentUser, svc: AppServices) -> MonthlyBudget:
    return MonthlyBudget.model_validate(await svc.budget.monthly_lines(user_id))


@router.put("/monthly")
async def set_monthly_budget(
    body: MonthlyBudgetRequest, user_id: CurrentUser, svc: AppServices
) -> MonthlyBudget:
    """Replace the monthly budget's lines; an empty list clears it."""
    try:
        saved = await svc.budget.set_monthly_lines(
            user_id, [line.model_dump() for line in body.lines]
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return MonthlyBudget.model_validate(saved)


@router.get("/current")
async def get_current_budget(user_id: CurrentUser, svc: AppServices) -> CurrentBudget:
    """This month's lines: limit, carried, spent, left and the pace."""
    return CurrentBudget.model_validate(await svc.budget.current(user_id))


@router.get("/trend")
async def get_spending_trend(
    user_id: CurrentUser, svc: AppServices, months: int = Query(6, ge=1, le=24)
) -> SpendingTrend:
    """Spending per expense account, month by month, this month last."""
    return SpendingTrend.model_validate(await svc.budget.trend(user_id, months))


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
