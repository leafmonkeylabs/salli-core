from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from salli.application.permissions import is_recent
from salli.domain.accounting import ledger as ledger_ops
from salli.domain.currency import quantize
from salli.interfaces.api.contract import Amount, CurrencyCode
from salli.interfaces.api.deps import AppServices, CurrentPrincipal, CurrentUser, StepUpRequired

router = APIRouter(prefix="/ledger", tags=["ledger"])


class TrialBalance(BaseModel):
    #: The base currency; every balance is in it.
    currency: CurrencyCode
    #: Account id → signed balance: debit balances positive, credit negative.
    balances: dict[str, Amount]
    #: The sum of every balance; zero for a ledger that balances.
    net: Amount


class IncomeStatementLine(BaseModel):
    account_id: str
    code: str
    name: str
    type: Literal["income", "expense"]
    #: Earned (income) or spent (expense) in the period; negative when
    #: refunds or reversals outweighed it.
    amount: Amount
    #: False for an account closed since; its activity in the period counts.
    is_active: bool


class IncomeStatement(BaseModel):
    from_date: str
    to_date: str
    #: The base currency; every amount is in it.
    currency: CurrencyCode
    #: Income account name → what it earned in the period. Two accounts that
    #: share a name are told apart by their code: "Rent (5100)".
    income: dict[str, Amount]
    #: Expense account name → what was spent on it in the period, likewise.
    expenses: dict[str, Amount]
    total_income: Amount
    total_expenses: Amount
    #: Income less expenses.
    net_income: Amount
    #: Every account with activity, income first, then by code.
    lines: list[IncomeStatementLine]


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
    # Closed accounts too: what they earned or cost in the period still counts.
    accounts = {
        a.id: a
        for a in await svc.ledger.list_accounts(user_id, include_inactive=True)
        if a.type in ("income", "expense")
    }
    entries = await svc.ledger.get_entries(user_id, from_date, to_date)
    balances = ledger_ops.trial_balance(entries)
    currency = await svc.ledger.base_currency(user_id)

    lines: list[IncomeStatementLine] = []
    for account_id, balance in balances.items():
        account = accounts.get(account_id)
        if account is None or balance == Decimal(0):
            continue
        # Income is credit-normal, so its balance is negated; expenses are debit-normal.
        amount = -balance if account.type == "income" else balance
        lines.append(
            IncomeStatementLine(
                account_id=account.id,
                code=account.code,
                name=account.name,
                type=account.type,  # type: ignore[arg-type]
                amount=str(quantize(amount, currency)),
                is_active=account.is_active,
            )
        )
    lines.sort(key=lambda line: (line.type != "income", line.code))

    names = [line.name for line in lines]

    def key(line: IncomeStatementLine) -> str:
        return line.name if names.count(line.name) == 1 else f"{line.name} ({line.code})"

    def total(kind: str) -> Decimal:
        # From Decimal(0), not the int 0 `sum` starts at: a quiet period reads
        # "0.00" in the currency's precision rather than "0".
        return sum((Decimal(line.amount) for line in lines if line.type == kind), Decimal(0))

    income, expenses = total("income"), total("expense")
    return IncomeStatement(
        from_date=from_date,
        to_date=to_date,
        currency=currency,
        income={key(line): line.amount for line in lines if line.type == "income"},
        expenses={key(line): line.amount for line in lines if line.type == "expense"},
        total_income=str(quantize(income, currency)),
        total_expenses=str(quantize(expenses, currency)),
        net_income=str(quantize(income - expenses, currency)),
        lines=lines,
    )


class LockDate(BaseModel):
    #: The books are closed up to and including this day: nothing is posted,
    #: reversed, changed or retagged on or before it. Null: none are closed.
    lock_date: dt.date | None


@router.put("/lock-date")
async def set_lock_date(
    body: LockDate, principal: CurrentPrincipal, user_id: CurrentUser, svc: AppServices
) -> LockDate:
    """Close the books up to and including a day before today, or open them
    (null). Moving the day earlier opens what was closed, so only the person's
    own sign-in may, with a recent password where their client asks for one,
    and never past a tax year whose latest return is filed (a 409) until an
    amendment of it is recorded. Every change is written to the audit log."""
    current = await svc.ledger.lock_date(user_id)
    wanted = body.lock_date.isoformat() if body.lock_date else None
    if current is not None and (wanted is None or wanted < current):
        if principal.actor().kind != "user":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Only your own sign-in to Salli can open closed books; other "
                "applications cannot.",
            )
        if principal.fresh_within and not is_recent(principal.sign_in_age, principal.fresh_within):
            raise StepUpRequired(
                "Opening closed books", int(principal.fresh_within.total_seconds())
            )
    await svc.ledger.set_lock_date(
        user_id, wanted, client_id=principal.client_id, via=principal.method
    )
    return LockDate(lock_date=body.lock_date)


class YearEndCloseRequest(BaseModel):
    #: The last day of the year being closed; the closing entry is dated it.
    period_end: dt.date


class YearEndClose(BaseModel):
    #: The closing entry (source `year_end_close`).
    entry_id: str
    period_end: str
    currency: CurrencyCode
    #: Income less expenses moved to retained earnings (negative: a loss).
    earnings: Amount
    retained_earnings_account_id: str


@router.post("/year-end-close", status_code=201)
async def close_year(
    body: YearEndCloseRequest, user_id: CurrentUser, svc: AppServices
) -> YearEndClose:
    """Close the income and expense accounts into retained earnings: one
    entry on `period_end` bringing each to zero against the equity account
    whose role is `retained_earnings`. Lock the books afterwards."""
    return YearEndClose.model_validate(
        await svc.ledger.close_year(user_id, body.period_end.isoformat())
    )


class RetainedEarningsRequest(BaseModel):
    #: An equity account of yours.
    account_id: str


@router.put("/retained-earnings", status_code=204)
async def set_retained_earnings(
    body: RetainedEarningsRequest, user_id: CurrentUser, svc: AppServices
) -> None:
    """Make an equity account the one a year-end close moves earnings to
    (its `equity_role` becomes `retained_earnings`; any other loses it)."""
    try:
        await svc.ledger.set_retained_earnings(user_id, body.account_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Account not found") from None


class ChainBreak(BaseModel):
    #: The first entry that doesn't check out.
    seq: int
    entry_id: str
    #: `missing`: an entry before it is gone; `link`: it doesn't name the
    #: one before it; `content`: it changed after it was posted.
    reason: Literal["missing", "link", "content"]


class ChainCheck(BaseModel):
    #: True when every entry is as it was posted.
    ok: bool
    #: How many entries checked out, from the first.
    checked: int
    first_break: ChainBreak | None


@router.get("/verify")
async def verify_ledger(user_id: CurrentUser, svc: AppServices) -> ChainCheck:
    """Check the ledger's hash chain from its first entry: each entry holds
    the hash of the one before and its own over what it says, so a changed,
    removed or reordered entry shows as the first break."""
    return ChainCheck.model_validate(await svc.ledger.verify_chain(user_id))
