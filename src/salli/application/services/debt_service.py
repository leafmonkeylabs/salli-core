"""
DebtService — declares structured debts (principal, APR, minimum payment) and
computes avalanche/snowball payoff plans via the pure domain engine.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.domain.currency import quantize, quantum
from salli.domain.debt import engine
from salli.domain.debt.models import Debt, PayoffStrategy
from salli.domain.money import from_minor, to_minor

# Debts are kept in the user's base currency.


def _debt_view(d: dict[str, Any], currency: str) -> dict[str, Any]:
    return {
        "id": d["id"],
        "name": d["name"],
        "currency": currency,
        "principal": str(from_minor(d["principal_minor"], currency)),
        "apr": d["apr"],
        "minimum_payment": str(from_minor(d["minimum_payment_minor"], currency)),
        "is_active": d["is_active"],
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }


class DebtService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    async def add_debt(self, user_id: str, data: dict[str, Any]) -> str:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            debt = {
                "name": data["name"],
                "principal_minor": to_minor(Decimal(str(data["principal"])), currency),
                "apr": str(Decimal(str(data["apr"]))),
                "minimum_payment_minor": to_minor(Decimal(str(data["minimum_payment"])), currency),
            }
            return await uow.debts.save(user_id, debt)

    async def list_debts(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            debts = await uow.debts.list(user_id, active_only)
        return [_debt_view(d, currency) for d in debts]

    async def get_debt(self, user_id: str, debt_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            d = await uow.debts.get(user_id, debt_id)
        return _debt_view(d, currency) if d else None

    async def update_debt(self, user_id: str, debt_id: str, data: dict[str, Any]) -> None:
        updates: dict[str, Any] = {}
        if "name" in data:
            updates["name"] = data["name"]
        if "apr" in data:
            updates["apr"] = str(Decimal(str(data["apr"])))
        if "is_active" in data:
            updates["is_active"] = data["is_active"]
        async with self._uow_factory() as uow:
            if "principal" in data or "minimum_payment" in data:
                currency = await uow.user_profiles.base_currency(user_id)
                if "principal" in data:
                    updates["principal_minor"] = to_minor(Decimal(str(data["principal"])), currency)
                if "minimum_payment" in data:
                    updates["minimum_payment_minor"] = to_minor(
                        Decimal(str(data["minimum_payment"])), currency
                    )
            await uow.debts.update(user_id, debt_id, updates)

    async def delete_debt(self, user_id: str, debt_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.debts.delete(user_id, debt_id)

    async def get_payoff_plan(
        self, user_id: str, extra_monthly_payment: Decimal, strategy: PayoffStrategy
    ) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            debts_data = await uow.debts.list(user_id, active_only=True)

        debts = [
            Debt(
                name=d["name"],
                principal=from_minor(d["principal_minor"], currency),
                apr=Decimal(d["apr"]),
                minimum_payment=from_minor(d["minimum_payment_minor"], currency),
            )
            for d in debts_data
        ]
        plan = engine.compute_payoff_plan(
            debts, extra_monthly_payment, strategy, money_quantum=quantum(currency)
        )

        return {
            "strategy": plan.strategy,
            "currency": currency,
            "months_to_payoff": plan.months_to_payoff,
            # Quantized here because with no debts the engine's total is a bare 0.
            "total_interest_paid": str(quantize(plan.total_interest_paid, currency)),
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
