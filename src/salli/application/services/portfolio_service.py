"""
PortfolioService — declares manually-entered investment holdings (cost basis,
current value) and computes allocation/rebalancing/ROI summaries via the pure
domain engine. No market-data feed — values are only as fresh as the user's
last update.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.domain.money import to_minor
from salli.domain.portfolio import engine
from salli.domain.portfolio.models import Holding


def _holding_view(h: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": h["id"],
        "symbol": h["symbol"],
        "name": h["name"],
        "asset_class": h["asset_class"],
        "cost_basis": str(Decimal(h["cost_basis_minor"]) / 100),
        "current_value": str(Decimal(h["current_value_minor"]) / 100),
        "is_active": h["is_active"],
        "created_at": h.get("created_at"),
        "updated_at": h.get("updated_at"),
    }


class PortfolioService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    async def add_holding(self, user_id: str, data: dict[str, Any]) -> str:
        holding = {
            "symbol": data["symbol"],
            "name": data["name"],
            "asset_class": data["asset_class"],
            "cost_basis_minor": to_minor(Decimal(str(data["cost_basis"]))),
            "current_value_minor": to_minor(Decimal(str(data["current_value"]))),
        }
        async with self._uow_factory() as uow:
            return await uow.holdings.save(user_id, holding)

    async def list_holdings(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            holdings = await uow.holdings.list(user_id, active_only)
        return [_holding_view(h) for h in holdings]

    async def get_holding(self, user_id: str, holding_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            h = await uow.holdings.get(user_id, holding_id)
        return _holding_view(h) if h else None

    async def update_holding(self, user_id: str, holding_id: str, data: dict[str, Any]) -> None:
        updates: dict[str, Any] = {}
        if "symbol" in data:
            updates["symbol"] = data["symbol"]
        if "name" in data:
            updates["name"] = data["name"]
        if "asset_class" in data:
            updates["asset_class"] = data["asset_class"]
        if "cost_basis" in data:
            updates["cost_basis_minor"] = to_minor(Decimal(str(data["cost_basis"])))
        if "current_value" in data:
            updates["current_value_minor"] = to_minor(Decimal(str(data["current_value"])))
        if "is_active" in data:
            updates["is_active"] = data["is_active"]
        async with self._uow_factory() as uow:
            await uow.holdings.update(user_id, holding_id, updates)

    async def delete_holding(self, user_id: str, holding_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.holdings.delete(user_id, holding_id)

    async def get_summary(
        self, user_id: str, target_allocation: dict[str, Decimal] | None = None
    ) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            holdings_data = await uow.holdings.list(user_id, active_only=True)

        holdings = [
            Holding(
                symbol=h["symbol"],
                name=h["name"],
                asset_class=h["asset_class"],
                cost_basis=Decimal(h["cost_basis_minor"]) / 100,
                current_value=Decimal(h["current_value_minor"]) / 100,
            )
            for h in holdings_data
        ]
        summary = engine.compute_summary(holdings, target_allocation)

        return {
            "total_value": str(summary.total_value),
            "total_cost_basis": str(summary.total_cost_basis),
            "total_gain": str(summary.total_gain),
            "total_gain_pct": str(summary.total_gain_pct),
            "allocation": [
                {
                    "asset_class": a.asset_class,
                    "current_value": str(a.current_value),
                    "pct_of_portfolio": str(a.pct_of_portfolio),
                }
                for a in summary.allocation
            ],
            "alerts": [
                {
                    "asset_class": alert.asset_class,
                    "current_pct": str(alert.current_pct),
                    "target_pct": str(alert.target_pct),
                    "drift_pct": str(alert.drift_pct),
                }
                for alert in summary.alerts
            ],
        }
