"""
Insights — `/v1/insights`.

The numbers a finance dashboard is built on, read from the ledger in the base
currency: cash flow and the savings rate by month, where the money goes, net
worth over time, and the recurring payments in the user's history (with the
declared subscription that covers each, if any).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from salli.interfaces.api.contract import Amount, CurrencyCode
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/insights", tags=["insights"])

Month = str  # "YYYY-MM"


class MonthCashFlow(BaseModel):
    month: Month
    income: Amount
    expenses: Amount
    #: Income less expenses.
    net: Amount
    #: Share of income kept, as a decimal string ("0.2500"); null with no income.
    savings_rate: str | None


class CashFlow(BaseModel):
    currency: CurrencyCode
    #: Oldest first, ending with the current month.
    months: list[MonthCashFlow]


class SpendingLine(BaseModel):
    #: The category tag, account name or need, by the axis asked for.
    key: str
    total: Amount
    #: Its share of all spending in the period ("0.4000").
    share: str
    by_month: dict[Month, Amount]


class Spending(BaseModel):
    currency: CurrencyCode
    by: Literal["category", "account", "need"]
    months: list[Month]
    #: Largest first.
    lines: list[SpendingLine]


class MonthEndNetWorth(BaseModel):
    month: Month
    #: Book values at the month's end.
    assets: Amount
    liabilities: Amount
    net_worth: Amount


class NetWorthByMonth(BaseModel):
    currency: CurrencyCode
    points: list[MonthEndNetWorth]


class RecurringPayment(BaseModel):
    payee: str
    cadence: Literal["weekly", "monthly", "quarterly", "yearly"]
    #: The middle charge; `varies` when charges differ by more than 10%.
    typical_amount: Amount
    varies: bool
    currency: CurrencyCode
    #: Where the charges were booked.
    account_id: str
    occurrences: int
    last_date: str
    next_expected: str
    examples: list[str]
    #: Whether a declared subscription already covers these charges, and which.
    tracked: bool
    subscription_id: str | None


class RecurringPayments(BaseModel):
    #: Soonest due first.
    items: list[RecurringPayment]


@router.get("/cash-flow")
async def cash_flow(
    user_id: CurrentUser,
    svc: AppServices,
    months: int = Query(12, ge=1, le=120, description="How many months, ending this one"),
) -> CashFlow:
    return CashFlow.model_validate(await svc.insights.cash_flow(user_id, months))


@router.get("/spending")
async def spending(
    user_id: CurrentUser,
    svc: AppServices,
    months: int = Query(3, ge=1, le=120, description="How many months, ending this one"),
    by: Literal["category", "account", "need"] = "category",
) -> Spending:
    return Spending.model_validate(await svc.insights.spending(user_id, months, by))


@router.get("/net-worth")
async def net_worth(
    user_id: CurrentUser,
    svc: AppServices,
    months: int = Query(24, ge=1, le=600, description="How many month ends, ending this one"),
) -> NetWorthByMonth:
    return NetWorthByMonth.model_validate(await svc.insights.net_worth(user_id, months))


@router.get("/recurring")
async def recurring(user_id: CurrentUser, svc: AppServices) -> RecurringPayments:
    return RecurringPayments.model_validate(await svc.insights.recurring(user_id))
