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
from salli.domain.currency import quantize
from salli.domain.money import from_minor, to_minor

# Budget limits are kept in the user's base currency, like the ledger amounts
# they are compared with.


def _lines_to_minor(lines: list[dict[str, Any]], currency: str) -> list[dict[str, Any]]:
    return [
        {
            "account_id": line["account_id"],
            "limit_minor": to_minor(Decimal(str(line["limit_amount"])), currency),
        }
        for line in lines
    ]


def _lines_view(lines: list[dict[str, Any]], currency: str) -> list[dict[str, Any]]:
    return [
        {
            "account_id": line["account_id"],
            "limit_amount": str(from_minor(line["limit_minor"], currency)),
        }
        for line in lines
    ]


def _budget_view(budget: dict[str, Any], currency: str) -> dict[str, Any]:
    return {
        "id": budget["id"],
        "period_start": budget["period_start"],
        "period_end": budget["period_end"],
        "currency": currency,
        "lines": _lines_view(budget["lines"], currency),
        "created_at": budget.get("created_at"),
        "updated_at": budget.get("updated_at"),
    }


class BudgetService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    async def create_budget(
        self, user_id: str, period_start: str, period_end: str, lines: list[dict[str, Any]]
    ) -> str:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            budget = {
                "period_start": period_start,
                "period_end": period_end,
                "lines": _lines_to_minor(lines, currency),
            }
            return await uow.budgets.save(user_id, budget)

    async def list_budgets(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            budgets = await uow.budgets.list(user_id)
        return [_budget_view(b, currency) for b in budgets]

    async def get_budget(self, user_id: str, budget_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            budget = await uow.budgets.get(user_id, budget_id)
        return _budget_view(budget, currency) if budget else None

    async def update_budget(self, user_id: str, budget_id: str, data: dict[str, Any]) -> None:
        updates: dict[str, Any] = {}
        if "period_start" in data:
            updates["period_start"] = data["period_start"]
        if "period_end" in data:
            updates["period_end"] = data["period_end"]
        async with self._uow_factory() as uow:
            if "lines" in data:
                currency = await uow.user_profiles.base_currency(user_id)
                updates["lines"] = _lines_to_minor(data["lines"], currency)
            await uow.budgets.update(user_id, budget_id, updates)

    async def delete_budget(self, user_id: str, budget_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.budgets.delete(user_id, budget_id)

    async def get_summary(self, user_id: str, budget_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            budget = await uow.budgets.get(user_id, budget_id)
            if budget is None:
                return None
            currency = await uow.user_profiles.base_currency(user_id)
            accounts = await uow.ledger.get_accounts(user_id)
            entries = await uow.ledger.get_entries(
                user_id, budget["period_start"], budget["period_end"]
            )

        budget_lines = [
            BudgetLineDef(
                account_id=line["account_id"],
                limit_amount=from_minor(line["limit_minor"], currency),
            )
            for line in budget["lines"]
        ]
        summary = engine.compute(entries, accounts, budget_lines)

        def money(amount: Decimal) -> str:
            return str(quantize(amount, currency))

        return {
            "id": budget["id"],
            "period_start": budget["period_start"],
            "period_end": budget["period_end"],
            "currency": currency,
            "total_limit": money(summary.total_limit),
            "total_actual": money(summary.total_actual),
            "total_variance": money(summary.total_variance),
            "lines": [
                {
                    "account_id": line.account_id,
                    "category": line.category,
                    "limit_amount": money(line.limit_amount),
                    "actual_amount": money(line.actual_amount),
                    "variance": money(line.variance),
                }
                for line in summary.lines
            ],
        }
