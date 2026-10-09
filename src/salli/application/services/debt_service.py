"""
DebtService — declares structured debts (principal, APR, minimum payment) and
computes avalanche/snowball payoff plans via the pure domain engine.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.domain.debt import engine
from salli.domain.debt.models import Debt, PayoffStrategy
from salli.domain.money import to_minor


def _debt_view(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": d["id"],
        "name": d["name"],
        "principal": str(Decimal(d["principal_minor"]) / 100),
        "apr": d["apr"],
        "minimum_payment": str(Decimal(d["minimum_payment_minor"]) / 100),
        "is_active": d["is_active"],
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }


class DebtService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    async def add_debt(self, user_id: str, data: dict[str, Any]) -> str:
        debt = {
            "name": data["name"],
            "principal_minor": to_minor(Decimal(str(data["principal"]))),
            "apr": str(Decimal(str(data["apr"]))),
            "minimum_payment_minor": to_minor(Decimal(str(data["minimum_payment"]))),
        }
        async with self._uow_factory() as uow:
            return await uow.debts.save(user_id, debt)

    async def list_debts(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            debts = await uow.debts.list(user_id, active_only)
        return [_debt_view(d) for d in debts]

    async def get_debt(self, user_id: str, debt_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            d = await uow.debts.get(user_id, debt_id)
        return _debt_view(d) if d else None

    async def update_debt(self, user_id: str, debt_id: str, data: dict[str, Any]) -> None:
        updates: dict[str, Any] = {}
        if "name" in data:
            updates["name"] = data["name"]
        if "principal" in data:
            updates["principal_minor"] = to_minor(Decimal(str(data["principal"])))
        if "apr" in data:
            updates["apr"] = str(Decimal(str(data["apr"])))
        if "minimum_payment" in data:
            updates["minimum_payment_minor"] = to_minor(Decimal(str(data["minimum_payment"])))
        if "is_active" in data:
            updates["is_active"] = data["is_active"]
        async with self._uow_factory() as uow:
            await uow.debts.update(user_id, debt_id, updates)

    async def delete_debt(self, user_id: str, debt_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.debts.delete(user_id, debt_id)

    async def get_payoff_plan(
        self, user_id: str, extra_monthly_payment: Decimal, strategy: PayoffStrategy
    ) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            debts_data = await uow.debts.list(user_id, active_only=True)

        debts = [
            Debt(
                name=d["name"],
                principal=Decimal(d["principal_minor"]) / 100,
                apr=Decimal(d["apr"]),
                minimum_payment=Decimal(d["minimum_payment_minor"]) / 100,
            )
            for d in debts_data
        ]
        plan = engine.compute_payoff_plan(debts, extra_monthly_payment, strategy)

        return {
            "strategy": plan.strategy,
            "months_to_payoff": plan.months_to_payoff,
            "total_interest_paid": str(plan.total_interest_paid),
            "schedule": [
                {
                    "month": e.month,
                    "debt_name": e.debt_name,
                    "payment": str(e.payment),
                    "principal_paid": str(e.principal_paid),
                    "interest_paid": str(e.interest_paid),
                    "remaining_balance": str(e.remaining_balance),
                }
                for e in plan.schedule
            ],
        }
