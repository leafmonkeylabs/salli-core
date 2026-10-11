"""
DebtService — declares structured debts (principal, APR, minimum payment, and
the ledger account that holds one, if any) and computes avalanche/snowball
payoff plans on calendar months via the pure domain engine, from the balances
the baseline counts.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.application.ownership import require_own_accounts
from salli.application.services.baseline_service import BaselineService
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
        "account_id": d.get("account_id"),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }


async def check_debt_account(
    uow: Any, user_id: str, account_id: str, debt_id: str | None = None
) -> None:
    """Refuse to link a debt to `account_id` unless it is one of the user's
    own liability accounts (AccountNotFound when it isn't theirs, which reads
    the same as one that doesn't exist), held in the base currency, and holds
    no other active debt (ValueError). A linked debt's balance is the
    account's, so an account holding two would count twice."""
    await require_own_accounts(uow, user_id, [account_id])
    account = await uow.ledger.get_account(user_id, account_id)
    base = await uow.user_profiles.base_currency(user_id)
    if account.type != "liability":
        raise ValueError(
            f"A debt links to a liability account, such as a loan or a card; "
            f"{account.name} is an {account.type} account"
        )
    if account.currency != base:
        raise ValueError(
            f"Debts are kept in your base currency ({base}); {account.name} is held in "
            f"{account.currency}"
        )
    for other in await uow.debts.list(user_id, active_only=True):
        if other.get("account_id") == account_id and other["id"] != debt_id:
            raise ValueError(
                f"{account.name} already holds the debt “{other['name']}”: an account "
                "holds one debt"
            )


class DebtService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        baselines: BaselineService | None = None,
        today: Callable[[], dt.date] = dt.date.today,
    ) -> None:
        self._uow_factory = uow_factory
        self._today = today
        self._baselines = baselines or BaselineService(uow_factory, today=today)

    async def add_debt(self, user_id: str, data: dict[str, Any]) -> str:
        """Declare a debt. With `account_id`, it is linked to the liability
        account that holds it in the ledger (`check_debt_account`)."""
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            account_id = data.get("account_id") or None
            if account_id is not None:
                await check_debt_account(uow, user_id, account_id)
            debt = {
                "name": data["name"],
                "principal_minor": to_minor(Decimal(str(data["principal"])), currency),
                "apr": str(Decimal(str(data["apr"]))),
                "minimum_payment_minor": to_minor(Decimal(str(data["minimum_payment"])), currency),
                "account_id": account_id,
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
        """Change a debt: only the fields in `data`. `account_id` None
        unlinks it from its account; another id links it
        (`check_debt_account`)."""
        updates: dict[str, Any] = {}
        if "name" in data:
            updates["name"] = data["name"]
        if "apr" in data:
            updates["apr"] = str(Decimal(str(data["apr"])))
        if "is_active" in data:
            updates["is_active"] = data["is_active"]
        async with self._uow_factory() as uow:
            if "account_id" in data:
                updates["account_id"] = data["account_id"] or None
            current = await uow.debts.get(user_id, debt_id)
            linked = updates.get("account_id", (current or {}).get("account_id"))
            # Checked when it is linked, and when a paid-off debt is made
            # active again: its account may hold another debt by now.
            if (
                current is not None
                and linked is not None
                and ("account_id" in updates or updates.get("is_active") is True)
            ):
                await check_debt_account(uow, user_id, linked, debt_id)
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
        self,
        user_id: str,
        extra_monthly_payment: Decimal,
        strategy: PayoffStrategy,
        as_of: dt.date | None = None,
    ) -> dict[str, Any]:
        """An avalanche or snowball plan for the active debts, as of `as_of`
        (today when None), on calendar months: the first payment falls in the
        month after it. Each debt starts from what the baseline says it owes:
        a linked debt what its ledger account holds, another its declared
        principal. A ValueError for an extra payment below zero or a strategy
        that isn't one, whoever asks."""
        if not extra_monthly_payment.is_finite() or extra_monthly_payment < 0:
            raise ValueError(
                f"An extra monthly payment is an amount from 0, not {extra_monthly_payment}"
            )
        if strategy not in ("avalanche", "snowball"):
            raise ValueError(f"A strategy is avalanche or snowball, not {strategy!r}")
        baseline = await self._baselines.build(user_id, as_of or self._today())
        currency = baseline.currency
        owing = [d for d in baseline.debts if d.balance > 0]
        first_month = engine.month_after(baseline.as_of.isoformat()[:7], 1)
        plan = engine.compute_payoff_plan(
            [Debt(d.name, d.balance, d.apr, d.minimum_payment, id=d.debt_id) for d in owing],
            extra_monthly_payment,
            strategy,
            money_quantum=quantum(currency),
            first_month=first_month,
        )

        return {
            "strategy": plan.strategy,
            "currency": currency,
            "as_of": baseline.as_of.isoformat(),
            # What each debt starts from, and where that figure comes from.
            "debts": [
                {
                    "debt_id": d.debt_id,
                    "name": d.name,
                    "balance": str(quantize(d.balance, currency)),
                    "source": d.source,
                    "account_id": d.account_id,
                }
                for d in owing
            ],
            "months_to_payoff": plan.months_to_payoff,
            "first_month": first_month if owing else None,
            "debt_free_month": plan.debt_free_period,
            # Quantized here because with no debts the engine's total is a bare 0.
            "total_interest_paid": str(quantize(plan.total_interest_paid, currency)),
            "schedule": [
                {
                    "month": e.month,
                    "period": e.period,
                    "debt_id": e.debt_id,
                    "debt_name": e.debt_name,
                    "payment": str(e.payment),
                    "principal_paid": str(e.principal_paid),
                    "interest_paid": str(e.interest_paid),
                    "remaining_balance": str(e.remaining_balance),
                }
                for e in plan.schedule
            ],
        }
