"""
Debt router — structured debts and avalanche/snowball payoff planning.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/debt", tags=["debt"])


class DebtRequest(BaseModel):
    name: str
    principal: float
    apr: float
    minimum_payment: float


class DebtUpdateRequest(BaseModel):
    name: str | None = None
    principal: float | None = None
    apr: float | None = None
    minimum_payment: float | None = None
    is_active: bool | None = None


@router.get("/")
async def list_debts(user_id: CurrentUser, svc: AppServices, active_only: bool = True):
    return {"debts": await svc.debt.list_debts(user_id, active_only)}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_debt(body: DebtRequest, user_id: CurrentUser, svc: AppServices):
    debt_id = await svc.debt.add_debt(user_id, body.model_dump())
    return {"id": debt_id}


@router.get("/payoff-plan")
async def get_payoff_plan(
    user_id: CurrentUser,
    svc: AppServices,
    extra_monthly_payment: float = Query(0, ge=0),
    strategy: str = Query("avalanche", pattern="^(avalanche|snowball)$"),
):
    """Avalanche/snowball payoff plan — months to payoff, total interest, schedule."""
    return await svc.debt.get_payoff_plan(
        user_id,
        Decimal(str(extra_monthly_payment)),
        strategy,  # type: ignore[arg-type]
    )


@router.get("/{debt_id}")
async def get_debt(debt_id: str, user_id: CurrentUser, svc: AppServices):
    debt = await svc.debt.get_debt(user_id, debt_id)
    if debt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
    return debt


@router.patch("/{debt_id}")
async def update_debt(
    debt_id: str, body: DebtUpdateRequest, user_id: CurrentUser, svc: AppServices
):
    await svc.debt.update_debt(user_id, debt_id, body.model_dump(exclude_none=True))
    return {"updated": True}


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_debt(debt_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.debt.delete_debt(user_id, debt_id)
