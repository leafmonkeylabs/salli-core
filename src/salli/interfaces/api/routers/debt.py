"""
Debt router — structured debts and avalanche/snowball payoff planning.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

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
    #: The liability account that holds this debt in your ledger, if any: one
    #: of your own, in your base currency, holding no other active debt. A
    #: linked debt's balance is the account's, so it is counted once; without
    #: one, the debt counts as declared (its principal).
    account_id: str | None = None


class DebtUpdateRequest(BaseModel):
    name: str | None = None
    principal: AmountIn | None = None
    apr: DecimalIn | None = None
    minimum_payment: AmountIn | None = None
    is_active: bool | None = None
    #: Link the debt to this liability account; null unlinks it. Omitted:
    #: unchanged.
    account_id: str | None = None


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
    #: The liability account that holds it in the ledger; null when it isn't
    #: linked to one (it then counts as declared).
    account_id: str | None = None
    created_at: str
    updated_at: str


class DebtList(BaseModel):
    debts: list[Debt]


class PayoffScheduleEntry(BaseModel):
    """What one debt is paid in one month of the plan."""

    #: 1 for the first payment, 2 for the next, ...
    month: int
    #: The calendar month it falls in ("YYYY-MM").
    period: str
    debt_id: str
    debt_name: str
    payment: Amount
    principal_paid: Amount
    interest_paid: Amount
    #: What is still owed on the debt after this month's payment.
    remaining_balance: Amount


class PlannedDebt(BaseModel):
    """A debt the plan pays off, and what it starts from."""

    debt_id: str
    name: str
    #: What it owes on the as-of date.
    balance: Amount
    #: "account" when that is what its linked ledger account holds;
    #: "declared" when it is the principal declared (no linked account).
    source: Literal["account", "declared"]
    account_id: str | None
    #: Its yearly rate as a fraction ("0.18" is 18%).
    apr: str
    minimum_payment: Amount
    #: The calendar month of its last payment ("YYYY-MM"); null when not
    #: within the plan's horizon.
    payoff_month: str | None = None


class PayoffPlan(BaseModel):
    strategy: PayoffStrategy
    currency: CurrencyCode
    #: The day the plan starts from (ISO 8601).
    as_of: str
    debts: list[PlannedDebt]
    #: Null when the debts are not paid off within the plan's 50-year horizon.
    months_to_payoff: int | None
    #: The calendar month of the first payment, the one after the as-of
    #: date's; null with nothing owed.
    first_month: str | None
    #: The calendar month of the last payment; null when not within the horizon.
    debt_free_month: str | None
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
    """Avalanche/snowball payoff plan on calendar months, from what each debt owes
    today (a linked debt: its ledger account; another: its declared principal):
    each debt's balance, rate, minimum and payoff month, months to payoff, the
    debt-free month, total interest, the schedule."""
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
    # Omitted fields are unchanged; an explicit null is ignored, except for
    # `account_id`, where it unlinks the debt.
    changes = {
        k: v
        for k, v in body.model_dump(exclude_unset=True).items()
        if v is not None or k == "account_id"
    }
    await svc.debt.update_debt(user_id, debt_id, changes)
    return Updated(updated=True)


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_debt(debt_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    await svc.debt.delete_debt(user_id, debt_id)
