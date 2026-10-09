"""
Debt router — structured debts and avalanche/snowball payoff planning.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from salli.domain.debt.models import PayoffStrategy
from salli.interfaces.api.contract import Amount, AmountIn, CurrencyCode, DecimalIn, Ref, Updated
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/debt", tags=["debt"])


class DebtRequest(BaseModel):
    name: str
    principal: AmountIn
    #: A yearly rate as a fraction ("0.18" is 18%).
    apr: DecimalIn
    minimum_payment: AmountIn


class DebtUpdateRequest(BaseModel):
    name: str | None = None
    principal: AmountIn | None = None
    apr: DecimalIn | None = None
    minimum_payment: AmountIn | None = None
    is_active: bool | None = None


class Debt(BaseModel):
    id: str
    name: str
    #: Debts are kept in the base currency.
    currency: CurrencyCode
    #: The outstanding balance.
    principal: Amount
    #: Annual rate as a decimal string, a fraction of one: "0.1850" is 18.5%.
    apr: str
    minimum_payment: Amount
    is_active: bool
    created_at: str
    updated_at: str


class DebtList(BaseModel):
    debts: list[Debt]


class PayoffScheduleEntry(BaseModel):
    """What one debt is paid in one month of the plan."""

    month: int
    debt_name: str
    payment: Amount
    principal_paid: Amount
    interest_paid: Amount
    #: What is still owed on the debt after this month's payment.
    remaining_balance: Amount


class PayoffPlan(BaseModel):
    strategy: PayoffStrategy
    currency: CurrencyCode
    #: Null when the debts are not paid off within the plan's 50-year horizon.
    months_to_payoff: int | None
    total_interest_paid: Amount
    schedule: list[PayoffScheduleEntry]


@router.get("/")
async def list_debts(user_id: CurrentUser, svc: AppServices, active_only: bool = True) -> DebtList:
    return DebtList.model_validate({"debts": await svc.debt.list_debts(user_id, active_only)})


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_debt(body: DebtRequest, user_id: CurrentUser, svc: AppServices) -> Ref:
    debt_id = await svc.debt.add_debt(user_id, body.model_dump())
    return Ref(id=debt_id)


@router.get("/payoff-plan")
async def get_payoff_plan(
    user_id: CurrentUser,
    svc: AppServices,
    extra_monthly_payment: AmountIn = Query(Decimal(0), ge=0),
    strategy: str = Query("avalanche", pattern="^(avalanche|snowball)$"),
) -> PayoffPlan:
    """Avalanche/snowball payoff plan — months to payoff, total interest, schedule."""
    plan = await svc.debt.get_payoff_plan(
        user_id,
        extra_monthly_payment,
        strategy,  # type: ignore[arg-type]
    )
    return PayoffPlan.model_validate(plan)


@router.get("/{debt_id}")
async def get_debt(debt_id: str, user_id: CurrentUser, svc: AppServices) -> Debt:
    debt = await svc.debt.get_debt(user_id, debt_id)
    if debt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
    return Debt.model_validate(debt)


@router.patch("/{debt_id}")
async def update_debt(
    debt_id: str, body: DebtUpdateRequest, user_id: CurrentUser, svc: AppServices
) -> Updated:
    if await svc.debt.get_debt(user_id, debt_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such debt")
    await svc.debt.update_debt(user_id, debt_id, body.model_dump(exclude_none=True))
    return Updated(updated=True)


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_debt(debt_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    await svc.debt.delete_debt(user_id, debt_id)
