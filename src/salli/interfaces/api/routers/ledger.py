from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel

from salli.domain.accounting import ledger as ledger_ops
from salli.domain.currency import quantize
from salli.interfaces.api.contract import Amount, CurrencyCode
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/ledger", tags=["ledger"])


class TrialBalance(BaseModel):
    #: The base currency; every balance is in it.
    currency: CurrencyCode
    #: Account id → signed balance: debit balances positive, credit negative.
    balances: dict[str, Amount]
    #: The sum of every balance; zero for a ledger that balances.
    net: Amount


class IncomeStatement(BaseModel):
    from_date: str
    to_date: str
    #: The base currency; every amount is in it.
    currency: CurrencyCode
    #: Income account name → what it earned in the period.
    income: dict[str, Amount]
    #: Expense account name → what was spent on it in the period.
    expenses: dict[str, Amount]
    #: Income less expenses.
    net_income: Amount


@router.get("/trial-balance")
async def trial_balance(
    user_id: CurrentUser,
    svc: AppServices,
    from_date: str | None = None,
    to_date: str | None = None,
) -> TrialBalance:
    balances = await svc.ledger.get_trial_balance(user_id, from_date, to_date)
    currency = await svc.ledger.base_currency(user_id)
    return TrialBalance(
        currency=currency,
        balances={k: str(quantize(v, currency)) for k, v in balances.items()},
        net=str(quantize(sum(balances.values(), Decimal(0)), currency)),
    )


@router.get("/income-statement")
async def income_statement(
    user_id: CurrentUser,
    svc: AppServices,
    from_date: str,
    to_date: str,
) -> IncomeStatement:
    # Auto-discover income and expense accounts by type
    accounts = await svc.ledger.list_accounts(user_id)
    income_ids = {a.id for a in accounts if a.type == "income"}
    expense_ids = {a.id for a in accounts if a.type == "expense"}
    account_names = {a.id: a.name for a in accounts}

    entries = await svc.ledger.get_entries(user_id, from_date, to_date)
    balances = ledger_ops.trial_balance(entries)
    currency = await svc.ledger.base_currency(user_id)

    income_breakdown: dict[str, str] = {}
    expense_breakdown: dict[str, str] = {}

    for acct_id, balance in balances.items():
        if balance == Decimal(0):
            continue
        name = account_names.get(acct_id, acct_id)
        if acct_id in income_ids:
            # income is credit-normal → negate
            income_breakdown[name] = str(quantize(-balance, currency))
        elif acct_id in expense_ids:
            # expenses are debit-normal → positive
            expense_breakdown[name] = str(quantize(balance, currency))

    # Summed from Decimal(0), not the int 0 `sum` starts at: a period with no
    # activity reads "0.00" in the currency's precision rather than "0".
    net = sum((Decimal(v) for v in income_breakdown.values()), Decimal(0)) - sum(
        (Decimal(v) for v in expense_breakdown.values()), Decimal(0)
    )

    return IncomeStatement(
        from_date=from_date,
        to_date=to_date,
        currency=currency,
        income=income_breakdown,
        expenses=expense_breakdown,
        net_income=str(quantize(net, currency)),
    )
