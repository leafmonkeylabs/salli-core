from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from salli.domain.accounting.models import Account as DomainAccount
from salli.interfaces.api.contract import Amount, CurrencyCode, Ref
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/accounts", tags=["accounts"])

AccountTypeStr = Literal["asset", "liability", "equity", "income", "expense"]


# The tax engine classifies strictly by `tax_role`, never by account name or
# code (see tax_service). Leaving it off these schemas meant a user-created
# account could never carry one, so only the chart auto-built during
# onboarding was ever visible to the engine.
#
# Which roles exist isn't fixed: the user's own tax rule sets declare them
# (docs/taxrules.md); Salli has none of its own. So the schema says only what
# a role looks like; whether this user may use it is checked when it is set
# (LedgerService), a 422 if not.
TaxRoleIn = Annotated[
    str,
    Field(
        pattern=r"^[a-z][a-z0-9_]{0,29}$",
        examples=["salary"],
        description="A role one of the user's tax rule sets declares.",
    ),
]
TaxRoleStr = TaxRoleIn


class AddAccountRequest(BaseModel):
    code: str
    name: str
    type: AccountTypeStr
    #: ISO 4217 code the account is held in. Omitted: the user's base currency.
    currency: str | None = None
    parent_id: str | None = None
    tax_role: TaxRoleIn | None = None


class UpdateAccountRequest(BaseModel):
    code: str
    name: str
    type: AccountTypeStr
    #: Omitted: unchanged. Only changes while the account has no entries.
    currency: str | None = None
    tax_role: TaxRoleIn | None = None


class Account(BaseModel):
    id: str
    code: str
    name: str
    type: AccountTypeStr
    #: The currency the account is held in.
    currency: CurrencyCode
    parent_id: str | None
    is_active: bool
    tax_role: TaxRoleStr | None = None


class AccountActivity(BaseModel):
    entry_id: str
    entry_date: str
    description: str
    source: Literal["manual", "statement", "sms", "system"]
    external_ref: str | None
    #: The account's value after this entry, in the base currency.
    running_balance: Amount
    #: The same in the account's own currency; null when it cannot be known.
    running_balance_native: Amount | None


class AccountOverview(BaseModel):
    account: Account
    base_currency: CurrencyCode
    #: The account's value in the base currency, at the rates its entries recorded.
    current_balance: Amount
    #: Its balance in its own currency (what the bank shows); null when unknowable.
    balance: Amount | None
    transactions: list[AccountActivity]


class AccountActive(BaseModel):
    id: str
    is_active: bool


def _account(a: DomainAccount) -> Account:
    return Account(
        id=a.id,
        code=a.code,
        name=a.name,
        type=a.type,
        currency=a.currency,
        parent_id=a.parent_id,
        is_active=a.is_active,
        tax_role=a.tax_role,
    )


@router.get("/")
async def list_accounts(user_id: CurrentUser, svc: AppServices) -> list[Account]:
    return [_account(a) for a in await svc.ledger.list_accounts(user_id)]


@router.post("/", status_code=201)
async def add_account(body: AddAccountRequest, user_id: CurrentUser, svc: AppServices) -> Ref:
    account_id = await svc.ledger.add_account(
        user_id=user_id,
        code=body.code,
        name=body.name,
        type=body.type,
        currency=body.currency,
        parent_id=body.parent_id,
        tax_role=body.tax_role,
    )
    return Ref(id=account_id)


@router.get("/{account_id}")
async def get_account(account_id: str, user_id: CurrentUser, svc: AppServices) -> Account:
    account = await svc.ledger.get_account(user_id, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return _account(account)


@router.get("/{account_id}/overview")
async def get_account_overview(
    account_id: str,
    user_id: CurrentUser,
    svc: AppServices,
    from_date: str | None = None,
    to_date: str | None = None,
) -> AccountOverview:
    """Account detail, current balance, and running-balance transaction history."""
    overview = await svc.ledger.get_account_overview(user_id, account_id, from_date, to_date)
    if overview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return AccountOverview.model_validate(overview)


@router.post("/{account_id}/reactivate")
async def reactivate_account(
    account_id: str, user_id: CurrentUser, svc: AppServices
) -> AccountActive:
    await svc.ledger.reactivate_account(user_id, account_id)
    return AccountActive(id=account_id, is_active=True)


@router.patch("/{account_id}", status_code=200)
async def update_account(
    account_id: str, body: UpdateAccountRequest, user_id: CurrentUser, svc: AppServices
) -> Ref:
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
    return Ref(id=account_id)


@router.delete("/{account_id}", status_code=204)
async def deactivate_account(account_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    await svc.ledger.deactivate_account(user_id=user_id, account_id=account_id)
