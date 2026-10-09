from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from salli.domain.accounting import ledger as ledger_ops
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("/trial-balance")
async def trial_balance(
    user_id: CurrentUser,
    svc: AppServices,
    from_date: str | None = None,
    to_date: str | None = None,
):
    balances = await svc.ledger.get_trial_balance(user_id, from_date, to_date)
    return {
        "balances": {k: str(v) for k, v in balances.items()},
        "net": str(sum(balances.values())),
    }


@router.get("/income-statement")
async def income_statement(
    user_id: CurrentUser,
    svc: AppServices,
    from_date: str,
    to_date: str,
):
    # Auto-discover income and expense accounts by type
    accounts = await svc.ledger.list_accounts(user_id)
    income_ids = {a.id for a in accounts if a.type == "income"}
    expense_ids = {a.id for a in accounts if a.type == "expense"}
    account_names = {a.id: a.name for a in accounts}

    entries = await svc.ledger.get_entries(user_id, from_date, to_date)
    balances = ledger_ops.trial_balance(entries)

    income_breakdown: dict[str, str] = {}
    expense_breakdown: dict[str, str] = {}

    for acct_id, balance in balances.items():
        if balance == Decimal(0):
            continue
        name = account_names.get(acct_id, acct_id)
        if acct_id in income_ids:
            income_breakdown[name] = str(-balance)  # income is credit-normal → negate
        elif acct_id in expense_ids:
            expense_breakdown[name] = str(balance)  # expenses are debit-normal → positive

    net = sum(Decimal(v) for v in income_breakdown.values()) - sum(
        Decimal(v) for v in expense_breakdown.values()
    )

    return {
        "from_date": from_date,
        "to_date": to_date,
        "income": income_breakdown,
        "expenses": expense_breakdown,
        "net_income": str(net),
    }
