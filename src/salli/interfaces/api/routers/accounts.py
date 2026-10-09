from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/accounts", tags=["accounts"])

AccountTypeStr = Literal["asset", "liability", "equity", "income", "expense"]

# The tax engine classifies strictly by `tax_role`, never by account name or
# code (see tax_service). Leaving it off these schemas meant a user-created
# account could never carry one, so only the chart auto-built during
# onboarding was ever visible to the engine.
TaxRoleStr = Literal[
    "apit_credit",
    "ait_credit",
    "foreign_tax_credit",
    "qualifying_payment",
    "fsi_income",
]


class AddAccountRequest(BaseModel):
    code: str
    name: str
    type: AccountTypeStr
    currency: str = "LKR"
    parent_id: str | None = None
    tax_role: TaxRoleStr | None = None


class UpdateAccountRequest(BaseModel):
    code: str
    name: str
    type: AccountTypeStr
    currency: str = "LKR"
    tax_role: TaxRoleStr | None = None


@router.get("/")
async def list_accounts(user_id: CurrentUser, svc: AppServices):
    accounts = await svc.ledger.list_accounts(user_id)
    return [
        {
            "id": a.id,
            "code": a.code,
            "name": a.name,
            "type": a.type,
            "currency": a.currency,
            "parent_id": a.parent_id,
            "is_active": a.is_active,
            "tax_role": a.tax_role,
        }
        for a in accounts
    ]


@router.post("/", status_code=201)
async def add_account(body: AddAccountRequest, user_id: CurrentUser, svc: AppServices):
    account_id = await svc.ledger.add_account(
        user_id=user_id,
        code=body.code,
        name=body.name,
        type=body.type,
        currency=body.currency,
        parent_id=body.parent_id,
        tax_role=body.tax_role,
    )
    return {"id": account_id}


@router.get("/{account_id}")
async def get_account(account_id: str, user_id: CurrentUser, svc: AppServices):
    account = await svc.ledger.get_account(user_id, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return {
        "id": account.id,
        "code": account.code,
        "name": account.name,
        "type": account.type,
        "currency": account.currency,
        "parent_id": account.parent_id,
        "is_active": account.is_active,
        "tax_role": account.tax_role,
    }


@router.get("/{account_id}/overview")
async def get_account_overview(
    account_id: str,
    user_id: CurrentUser,
    svc: AppServices,
    from_date: str | None = None,
    to_date: str | None = None,
):
    """Account detail, current balance, and running-balance transaction history."""
    overview = await svc.ledger.get_account_overview(user_id, account_id, from_date, to_date)
    if overview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return overview


@router.post("/{account_id}/reactivate")
async def reactivate_account(account_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.ledger.reactivate_account(user_id, account_id)
    return {"id": account_id, "is_active": True}


@router.patch("/{account_id}", status_code=200)
async def update_account(
    account_id: str, body: UpdateAccountRequest, user_id: CurrentUser, svc: AppServices
):
    # The repository assigns `row.tax_role = tax_role` unconditionally, and the
    # mobile client does not send the field — so passing body.tax_role straight
    # through would clear the role on every rename and silently inflate that
    # user's tax bill. An omitted field keeps whatever the account already has.
    tax_role = body.tax_role
    if "tax_role" not in body.model_fields_set:
        existing = await svc.ledger.get_account(user_id, account_id)
        tax_role = existing.tax_role if existing else None
    await svc.ledger.update_account(
        user_id=user_id,
        account_id=account_id,
        code=body.code,
        name=body.name,
        type=body.type,
        currency=body.currency,
        tax_role=tax_role,
    )
    return {"id": account_id}


@router.delete("/{account_id}", status_code=204)
async def deactivate_account(account_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.ledger.deactivate_account(user_id=user_id, account_id=account_id)
