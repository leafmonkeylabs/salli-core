"""
Reports router — balance sheet, net-worth statement, goal progress, and CSV
export of any of the three.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

from salli.interfaces.api.contract import Amount, CurrencyCode
from salli.interfaces.api.deps import AppServices, CurrentUser
from salli.interfaces.api.routers.fi import Goal, money

router = APIRouter(prefix="/reports", tags=["reports"])

_VALID_REPORT_TYPES = ("balance-sheet", "net-worth", "goal-progress")


class BalanceSheetLine(BaseModel):
    account_id: str
    code: str
    name: str
    #: What the account holds (an asset) or owes (a liability, equity), in the
    #: base currency.
    balance: Amount


class BalanceSheet(BaseModel):
    """Every asset, liability and equity account, valued in the base currency."""

    currency: CurrencyCode
    assets: list[BalanceSheetLine]
    liabilities: list[BalanceSheetLine]
    equity: list[BalanceSheetLine]
    total_assets: Amount
    total_liabilities: Amount
    total_equity: Amount
    #: total_assets − total_liabilities.
    net_worth: Amount


class NetWorthPoint(BaseModel):
    #: When the score it was recorded with was computed.
    date: str
    net_worth: Amount


class NetWorthStatement(BaseModel):
    """Net worth now, and its trend across stored FI scores."""

    currency: CurrencyCode
    #: Null only when the latest score was stored without one.
    current_net_worth: Amount | None
    #: The date of the trend's newest point; null when there is no trend yet.
    as_of: str | None
    #: Oldest first.
    trend: list[NetWorthPoint]


class GoalProgressReport(BaseModel):
    goals: list[Goal]
    #: Goals at 100%.
    completed_count: int
    in_progress_count: int


@router.get("/balance-sheet")
async def get_balance_sheet(user_id: CurrentUser, svc: AppServices) -> BalanceSheet:
    return BalanceSheet.model_validate(await svc.reports.get_balance_sheet(user_id))


@router.get("/net-worth")
async def get_net_worth_statement(user_id: CurrentUser, svc: AppServices) -> NetWorthStatement:
    statement = await svc.reports.get_net_worth_statement(user_id)
    # The figures come from stored FI scores, written as str(Decimal); one
    # stored before scores recorded their currency is in the base currency,
    # which cannot change once anything is stored in it.
    currency = statement["currency"] or await svc.ledger.base_currency(user_id)
    current = statement["current_net_worth"]
    return NetWorthStatement.model_validate(
        {
            **statement,
            "currency": currency,
            "current_net_worth": None if current is None else money(current, currency),
            "trend": [
                {**t, "net_worth": money(t["net_worth"], currency)} for t in statement["trend"]
            ],
        }
    )


@router.get("/goal-progress")
async def get_goal_progress_report(user_id: CurrentUser, svc: AppServices) -> GoalProgressReport:
    return GoalProgressReport.model_validate(await svc.reports.get_goal_progress_report(user_id))


@router.get(
    "/{report_type}/export",
    # The handler builds its own response; naming the plain class keeps FastAPI
    # from also documenting an application/json body it never sends.
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "The report as a CSV file."}},
)
async def export_report_csv(report_type: str, user_id: CurrentUser, svc: AppServices):
    """Download a report as CSV. report_type: balance-sheet | net-worth | goal-progress."""
    if report_type not in _VALID_REPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown report type '{report_type}'. Use one of {_VALID_REPORT_TYPES}.",
        )
    csv_bytes = await svc.reports.export_csv(report_type, user_id)
    filename = f"{report_type}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
