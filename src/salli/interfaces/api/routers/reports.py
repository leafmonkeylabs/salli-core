"""
Reports router — balance sheet, net-worth statement, goal progress, and CSV
export of any of the three.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/reports", tags=["reports"])

_VALID_REPORT_TYPES = ("balance-sheet", "net-worth", "goal-progress")


@router.get("/balance-sheet")
async def get_balance_sheet(user_id: CurrentUser, svc: AppServices):
    return await svc.reports.get_balance_sheet(user_id)


@router.get("/net-worth")
async def get_net_worth_statement(user_id: CurrentUser, svc: AppServices):
    return await svc.reports.get_net_worth_statement(user_id)


@router.get("/goal-progress")
async def get_goal_progress_report(user_id: CurrentUser, svc: AppServices):
    return await svc.reports.get_goal_progress_report(user_id)


@router.get("/{report_type}/export")
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
