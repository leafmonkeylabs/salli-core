"""
BudgetService — declares category budget limits for a period and computes a
BudgetSummary by aggregating actual ledger spend against them. The domain engine
never touches the DB; this service fetches ledger data (via its own uow_factory,
same pattern as FiService.build_snapshot) and calls compute().
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.domain.budget import engine
from salli.domain.budget.models import BudgetLineDef
from salli.domain.money import to_minor


def _lines_to_minor(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "account_id": line["account_id"],
            "limit_minor": to_minor(Decimal(str(line["limit_amount"]))),
        }
        for line in lines
    ]


def _lines_view(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "account_id": line["account_id"],
            "limit_amount": str(Decimal(line["limit_minor"]) / 100),
        }
        for line in lines
    ]


def _budget_view(budget: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": budget["id"],
        "period_start": budget["period_start"],
        "period_end": budget["period_end"],
        "lines": _lines_view(budget["lines"]),
        "created_at": budget.get("created_at"),
        "updated_at": budget.get("updated_at"),
    }


class BudgetService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    async def create_budget(
        self, user_id: str, period_start: str, period_end: str, lines: list[dict[str, Any]]
    ) -> str:
        budget = {
            "period_start": period_start,
            "period_end": period_end,
            "lines": _lines_to_minor(lines),
        }
        async with self._uow_factory() as uow:
            return await uow.budgets.save(user_id, budget)

    async def list_budgets(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            budgets = await uow.budgets.list(user_id)
        return [_budget_view(b) for b in budgets]

    async def get_budget(self, user_id: str, budget_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            budget = await uow.budgets.get(user_id, budget_id)
        return _budget_view(budget) if budget else None

    async def update_budget(self, user_id: str, budget_id: str, data: dict[str, Any]) -> None:
        updates: dict[str, Any] = {}
        if "period_start" in data:
            updates["period_start"] = data["period_start"]
        if "period_end" in data:
            updates["period_end"] = data["period_end"]
        if "lines" in data:
            updates["lines"] = _lines_to_minor(data["lines"])
        async with self._uow_factory() as uow:
            await uow.budgets.update(user_id, budget_id, updates)

    async def delete_budget(self, user_id: str, budget_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.budgets.delete(user_id, budget_id)

    async def get_summary(self, user_id: str, budget_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            budget = await uow.budgets.get(user_id, budget_id)
            if budget is None:
                return None
            accounts = await uow.ledger.get_accounts(user_id)
            entries = await uow.ledger.get_entries(
                user_id, budget["period_start"], budget["period_end"]
            )

        budget_lines = [
            BudgetLineDef(
                account_id=line["account_id"], limit_amount=Decimal(line["limit_minor"]) / 100
            )
            for line in budget["lines"]
        ]
        summary = engine.compute(entries, accounts, budget_lines)

        return {
            "id": budget["id"],
            "period_start": budget["period_start"],
            "period_end": budget["period_end"],
            "total_limit": str(summary.total_limit),
            "total_actual": str(summary.total_actual),
            "total_variance": str(summary.total_variance),
            "lines": [
                {
                    "account_id": line.account_id,
                    "category": line.category,
                    "limit_amount": str(line.limit_amount),
                    "actual_amount": str(line.actual_amount),
                    "variance": str(line.variance),
                }
                for line in summary.lines
            ],
        }
