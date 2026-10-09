"""
Portfolio router — manually-declared investment holdings, allocation, and
rebalancing/ROI summaries. No live market-data feed; values are only as fresh
as the user's last update.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class HoldingRequest(BaseModel):
    symbol: str
    name: str
    asset_class: str
    cost_basis: float
    current_value: float


class HoldingUpdateRequest(BaseModel):
    symbol: str | None = None
    name: str | None = None
    asset_class: str | None = None
    cost_basis: float | None = None
    current_value: float | None = None
    is_active: bool | None = None


def _parse_target(target: list[str]) -> dict[str, Decimal] | None:
    if not target:
        return None
    parsed: dict[str, Decimal] = {}
    for pair in target:
        asset_class, _, pct = pair.partition(":")
        if not asset_class or not pct:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid target entry '{pair}'. Use asset_class:pct.",
            )
        parsed[asset_class] = Decimal(pct)
    return parsed


@router.get("/")
async def list_holdings(user_id: CurrentUser, svc: AppServices, active_only: bool = True):
    return {"holdings": await svc.portfolio.list_holdings(user_id, active_only)}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_holding(body: HoldingRequest, user_id: CurrentUser, svc: AppServices):
    holding_id = await svc.portfolio.add_holding(user_id, body.model_dump())
    return {"id": holding_id}


@router.get("/summary")
async def get_summary(
    user_id: CurrentUser,
    svc: AppServices,
    target: list[str] = Query([], description="Repeatable asset_class:pct, e.g. equity:0.6"),
):
    """Allocation by asset class, total gain/ROI, and (if target given) rebalancing alerts."""
    return await svc.portfolio.get_summary(user_id, _parse_target(target))


@router.get("/{holding_id}")
async def get_holding(holding_id: str, user_id: CurrentUser, svc: AppServices):
    holding = await svc.portfolio.get_holding(user_id, holding_id)
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")
    return holding


@router.patch("/{holding_id}")
async def update_holding(
    holding_id: str, body: HoldingUpdateRequest, user_id: CurrentUser, svc: AppServices
):
    await svc.portfolio.update_holding(user_id, holding_id, body.model_dump(exclude_none=True))
    return {"updated": True}


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(holding_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.portfolio.delete_holding(user_id, holding_id)
