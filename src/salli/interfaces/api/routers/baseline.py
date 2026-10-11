"""
The baseline — `/v1/baseline`.

One consistent, dated model of the user's money (domain/baseline,
docs/baseline.md): income and expenses under one definition, balances by
role at the published rate for the as-of date, debts counted once, the
assumptions and which of them are placeholders, and two timelines (daily
cash for the next twelve months, and monthly to a horizon of up to 50 years,
in today's money). FI, insights, the forecast and the debt plan are all
computed from it. Reading it stores nothing.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from salli.interfaces.api.contract import Amount, CurrencyCode, DecimalOut
from salli.interfaces.api.deps import AppServices, CurrentUser
from salli.interfaces.api.routers.fi import FiAssumptions

router = APIRouter(prefix="/baseline", tags=["baseline"])

Month = str  # "YYYY-MM"


class BaselineMonthFlow(BaseModel):
    """One full calendar month's money in and out, signed amounts netted."""

    month: Month
    income: Amount
    expenses: Amount
    net: Amount
    #: Spending tagged `need: essential`.
    essential: Amount


class BaselineFlows(BaseModel):
    """Monthly averages over the months observed (`months_observed`)."""

    monthly_income: Amount
    monthly_expenses: Amount
    monthly_surplus: Amount
    #: monthly_surplus / monthly_income ("0.4907"); null without income.
    savings_rate: str | None
    #: Average essential spending; null while no spending carries a need tag.
    essential_monthly: Amount | None
    #: The share of spending that carries a need tag; null without spending.
    need_coverage: str | None
    by_month: list[BaselineMonthFlow]


class BaselineRate(BaseModel):
    """The published rate for the as-of date that balances in a currency are
    valued at."""

    currency: CurrencyCode
    #: Units of the base currency per unit; null when no source had one (that
    #: currency's balances are then left out of the totals).
    rate: DecimalOut | None
    #: Who published it.
    source: str | None
    #: The day the rate is for: a Sunday's rate is Friday's.
    as_of: str | None


class BaselineBalance(BaseModel):
    account_id: str
    code: str
    name: str
    #: cash, investment or other_asset (the account's asset role), or liability.
    role: Literal["cash", "investment", "other_asset", "liability"]
    #: The account's own currency.
    currency: CurrencyCode
    #: Signed (what is owed is negative), in the account's currency; null
    #: when it can't be known.
    amount: Amount | None
    #: The same in the base currency at the as-of rate; null without one.
    value: Amount | None
    #: Counted as cash: in the daily cash timeline and the monthly timeline's cash.
    in_cash: bool
    #: The declared debt this liability account holds, if any.
    debt_id: str | None


class BaselineTotals(BaseModel):
    """In the base currency, at the as-of rates."""

    #: The cash accounts together, signed (a card's balance counts against them).
    cash: Amount
    #: What the cash-role accounts own: the emergency fund's money.
    liquid: Amount
    investments: Amount
    other_assets: Amount
    #: What the debts with terms owe.
    debts: Amount
    #: What liabilities without terms owe.
    other_liabilities: Amount
    total_assets: Amount
    total_liabilities: Amount
    net_worth: Amount


class BaselineDebt(BaseModel):
    debt_id: str
    name: str
    #: "account": the balance is its linked ledger account's; "declared": the
    #: ledger doesn't hold it, so its declared principal.
    source: Literal["account", "declared"]
    account_id: str | None
    balance: Amount
    apr: DecimalOut
    minimum_payment: Amount
    #: The part of each month's payment the average surplus already pays.
    already_paid: Amount
    #: The calendar month of its last payment ("YYYY-MM"); null when not
    #: within the horizon.
    paid_off: Month | None
    #: Interest paid to then (or to the horizon).
    total_interest: Amount


class BaselineCashMonth(BaseModel):
    month: Month
    #: The cash at the month's end, in that month's own money, after the
    #: share invested has left it.
    cash: Amount
    #: The rest of the month's plan beyond what is scheduled.
    unscheduled: Amount
    #: The share of the month's regular surplus moved into investments on
    #: its last day (`monthly.surplus_invested`).
    invested: Amount


class BaselineDay(BaseModel):
    date: str
    balance: Amount


class BaselineCash(BaseModel):
    """The daily cash timeline: the as-of month and the twelve after it, in
    each day's own money."""

    start: str
    end: str
    today: Amount
    lowest: Amount
    lowest_date: str
    month_ends: list[BaselineCashMonth]
    #: Every day; null when not asked for.
    daily: list[BaselineDay] | None = None


class BaselineMonthPoint(BaseModel):
    """Where things stand at a month's end (the first point: the as-of date),
    in today's money."""

    month: Month
    date: str
    cash: Amount
    investments: Amount
    other_assets: Amount
    debts: Amount
    other_liabilities: Amount
    net_worth: Amount


class BaselineMonthly(BaseModel):
    horizon_years: int
    #: The base scenario's real return the investments grow at.
    real_return: DecimalOut
    #: The share (0 to 1) of each month's regular surplus moved into the
    #: investments; the rest stays in cash, which earns nothing.
    surplus_invested: DecimalOut
    #: The user's inflation; null when none is set (nominal amounts then keep
    #: their real value, a placeholder).
    inflation: DecimalOut | None
    points: list[BaselineMonthPoint]


class BaselineRuleSet(BaseModel):
    """An active tax rule set version that applies on the as-of date."""

    country: str
    region: str | None
    year: str
    rule_set_id: str
    version: int
    content_hash: str


class Baseline(BaseModel):
    """The user's money as of a day, and the definitions behind every figure."""

    as_of: str
    #: The base currency, which every total is in.
    currency: CurrencyCode
    #: The full calendar months income and expenses are averaged over.
    months_observed: list[Month]
    flows: BaselineFlows
    rates: list[BaselineRate]
    balances: list[BaselineBalance]
    totals: BaselineTotals
    debts: list[BaselineDebt]
    #: The month the last debt is paid off; null when one isn't within the
    #: horizon (or there are none).
    debt_free: Month | None
    cash: BaselineCash
    monthly: BaselineMonthly
    #: The FI assumptions planning rests on, and where each came from.
    assumptions: FiAssumptions
    #: Which assumptions are placeholders: real_return, safe_withdrawal_rate,
    #: surplus_invested, and inflation when none is set.
    placeholders: list[
        Literal["real_return", "safe_withdrawal_rate", "surplus_invested", "inflation"]
    ]
    #: The active tax rule sets in your tax residency whose year covers the
    #: as-of date.
    rule_sets: list[BaselineRuleSet]
    #: A content hash of everything the baseline was built from: the same
    #: inputs, the same baseline (a scenario's result records it).
    fingerprint: str
    #: What was left out, and why.
    notes: list[str]


@router.get("")
async def get_baseline(
    user_id: CurrentUser,
    svc: AppServices,
    as_of: dt.date | None = Query(None, description="YYYY-MM-DD; today when omitted"),
    horizon_years: int = Query(30, ge=1, le=50, description="The monthly timeline's horizon"),
    daily: bool = Query(True, description="Include every day of the cash timeline"),
) -> Baseline:
    """The baseline as of a day: what FI, insights, the forecast and the debt
    plan compute from, with the months, rates and assumptions they use."""
    if as_of is not None and as_of > svc.baseline.today():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"The as-of date can't be after today ({svc.baseline.today().isoformat()})",
        )
    view = await svc.baseline.get_baseline(user_id, as_of, horizon_years, daily=daily)
    return Baseline.model_validate(view)
