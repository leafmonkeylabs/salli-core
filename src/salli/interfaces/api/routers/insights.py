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
from pydantic import BaseModel, Field

from salli.domain.reports.insights import Cadence, SpendingAxis
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
    #: False for the current month, which isn't over.
    complete: bool
    #: Counted in `average`: a full month, from the first with income or
    #: expenses, among the twelve most recent.
    observed: bool


class AverageCashFlow(BaseModel):
    """The monthly averages over the months marked observed: the baseline's
    income and expenses, the same figures FI uses."""

    months_observed: list[Month]
    income: Amount
    expenses: Amount
    net: Amount
    #: net / income, a fraction in a decimal string; null without income.
    savings_rate: str | None


class CashFlow(BaseModel):
    currency: CurrencyCode
    #: Oldest first: the full months asked for, then the current month so far.
    months: list[MonthCashFlow]
    average: AverageCashFlow


class ExchangeRate(BaseModel):
    """A published rate the cash total is in the base currency at: the one
    for the as-of date, as every baseline figure uses."""

    currency: CurrencyCode
    #: Units of the base currency per unit; null when no source had one (the
    #: currency's accounts are then left out of the total).
    rate: str | None
    #: Who published it.
    source: str | None
    #: The day the rate is for: a Sunday's rate is Friday's.
    as_of: str | None


class SpendingLine(BaseModel):
    #: The category tag, account name or need, by the axis asked for.
    key: str
    total: Amount
    #: Its share of what was spent in the period ("0.4000"); null for a line
    #: that netted to money back (refunds only).
    share: str | None
    by_month: dict[Month, Amount]


class Spending(BaseModel):
    currency: CurrencyCode
    by: SpendingAxis
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
    #: The one word the charges are grouped by: what a scenario's
    #: stop_recurring change names to stop them.
    key: str
    cadence: Cadence
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


class ForecastDay(BaseModel):
    date: str
    #: All cash accounts together at the day's end, in the base currency.
    balance: Amount


class AccountForecast(BaseModel):
    account_id: str
    name: str
    #: The account's own currency; its amounts are in it.
    currency: CurrencyCode
    today: Amount
    end: Amount
    lowest: Amount
    lowest_date: str


class ExpectedFlow(BaseModel):
    date: str
    #: The cash account it moves; null for a declared subscription the ledger
    #: has not shown, which moves only the total.
    account_id: str | None
    #: Signed: money in is positive. In `currency`.
    amount: Amount
    currency: CurrencyCode
    description: str
    #: "recurring" (seen in the ledger) or "subscription" (declared, not yet
    #: seen); "change" for a flow a scenario added.
    source: Literal["recurring", "subscription", "change"]


class CashForecast(BaseModel):
    """Where the cash accounts are heading, from what keeps happening."""

    #: The base currency, which the totals are in.
    currency: CurrencyCode
    start: str
    end: str
    today: Amount
    end_balance: Amount
    #: The lowest the total gets, and when: the day to watch.
    lowest: Amount
    lowest_date: str
    daily: list[ForecastDay]
    accounts: list[AccountForecast]
    flows: list[ExpectedFlow]
    #: The rates the total is in the base currency at.
    fx: list[ExchangeRate] = Field(default_factory=list[ExchangeRate])
    #: What was left out, and why: a cash account whose balance in its own
    #: currency can't be known, a series or subscription that can't be read.
    notes: list[str] = Field(default_factory=list)


@router.get("/cash-flow")
async def cash_flow(
    user_id: CurrentUser,
    svc: AppServices,
    months: int = Query(
        12, ge=1, le=120, description="How many full months before this one (this month follows)"
    ),
) -> CashFlow:
    return CashFlow.model_validate(await svc.insights.cash_flow(user_id, months))


@router.get("/spending")
async def spending(
    user_id: CurrentUser,
    svc: AppServices,
    months: int = Query(3, ge=1, le=120, description="How many months, ending this one"),
    by: SpendingAxis = "category",
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


@router.get("/forecast")
async def forecast(
    user_id: CurrentUser,
    svc: AppServices,
    days: int = Query(60, ge=1, le=366, description="How many days ahead"),
) -> CashForecast:
    return CashForecast.model_validate(await svc.insights.forecast(user_id, days))


class CommittedFlow(BaseModel):
    date: str
    description: str
    #: Signed: money out is negative. In `currency`.
    amount: Amount
    currency: CurrencyCode


class NextIncome(BaseModel):
    date: str
    description: str
    amount: Amount
    currency: CurrencyCode


class SafeToSpend(BaseModel):
    """What could go out today without the cash forecast going below zero
    before money next comes in."""

    currency: CurrencyCode
    amount: Amount
    cash_today: Amount
    #: The day money next comes in, or 30 days ahead when none is expected.
    until: str
    next_income: NextIncome | None
    #: What is expected to go out before then.
    committed: list[CommittedFlow]
    #: The rates the cash total is in the base currency at.
    fx: list[ExchangeRate] = Field(default_factory=list[ExchangeRate])
    notes: list[str]


class FinanceSignal(BaseModel):
    kind: Literal[
        "low_balance_ahead",
        "price_change",
        "new_recurring",
        "spending_spike",
        "savings_rate_drop",
        "review_waiting",
        "decision_review_due",
    ]
    severity: Literal["high", "medium", "info"]
    title: str
    detail: str
    #: Where to look: see_forecast, see_recurring, see_spending, see_cash_flow,
    #: review (transactions) or review_decision (a decision in the journal).
    action: Literal[
        "see_forecast",
        "see_recurring",
        "see_spending",
        "see_cash_flow",
        "review",
        "review_decision",
    ]
    amount: Amount | None
    currency: CurrencyCode | None
    date: str | None
    #: What it rests on: journal entry, transaction, account or decision ids.
    refs: list[str]


class FinanceSignals(BaseModel):
    #: Most pressing first.
    signals: list[FinanceSignal]


@router.get("/safe-to-spend")
async def safe_to_spend(user_id: CurrentUser, svc: AppServices) -> SafeToSpend:
    return SafeToSpend.model_validate(await svc.insights.safe_to_spend(user_id))


@router.get("/signals")
async def signals(user_id: CurrentUser, svc: AppServices) -> FinanceSignals:
    return FinanceSignals.model_validate(await svc.insights.signals(user_id))
