"""
BudgetService — declares category budget limits for a period and computes a
BudgetSummary by aggregating actual ledger spend against them. The domain engine
never touches the DB; this service fetches ledger data (via its own uow_factory,
same pattern as FiService.build_snapshot) and calls compute().
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.application.ownership import require_own_accounts
from salli.domain.budget import engine, monthly
from salli.domain.budget.models import BudgetLineDef
from salli.domain.currency import quantize
from salli.domain.money import from_minor, to_minor
from salli.domain.reports.insights import last_months

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
    def __init__(
        self, uow_factory: Callable[[], Any], today: Callable[[], dt.date] = dt.date.today
    ) -> None:
        self._uow_factory = uow_factory
        self._today = today

    # ── The monthly budget ───────────────────────────────────────────────────

    async def monthly_lines(self, user_id: str) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            profile = await uow.user_profiles.get(user_id) or {}
        return {
            "currency": currency,
            "lines": [
                {
                    "account_id": line["account_id"],
                    "limit_amount": str(from_minor(line["limit_minor"], currency)),
                    "rollover": bool(line["rollover"]),
                    "since": line["since"],
                }
                for line in profile.get("monthly_budget", [])
            ],
        }

    async def set_monthly_lines(self, user_id: str, lines: list[dict[str, Any]]) -> dict[str, Any]:
        """Replace the monthly budget: one line per expense account, a limit
        from 0 and whether what is left rolls over. A line kept keeps the
        month it started (`since`); a new one starts this month. ValueError
        for an account that isn't one of the user's expense accounts, twice."""
        month = monthly.month_of(self._today())
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            profile = await uow.user_profiles.get(user_id) or {}
            started = {
                line["account_id"]: line["since"] for line in profile.get("monthly_budget", [])
            }
            accounts = {a.id: a for a in await uow.ledger.get_accounts(user_id)}
            stored: list[dict[str, Any]] = []
            for line in lines:
                account = accounts.get(line["account_id"])
                if account is None or account.type != "expense":
                    raise ValueError(f"{line['account_id']} is not one of your expense accounts.")
                if any(s["account_id"] == account.id for s in stored):
                    raise ValueError(f"{account.name} has two lines: give it one.")
                limit = Decimal(str(line["limit_amount"]))
                if limit < 0:
                    raise ValueError("A limit is an amount from 0.")
                stored.append(
                    {
                        "account_id": account.id,
                        "limit_minor": to_minor(limit, currency),
                        "rollover": bool(line.get("rollover", False)),
                        "since": started.get(account.id, month),
                    }
                )
            await uow.user_profiles.set_monthly_budget(user_id, stored)
        return await self.monthly_lines(user_id)

    async def _monthly(
        self, user_id: str, months: int
    ) -> tuple[list[monthly.MonthlyLine], dict[tuple[str, str], Decimal], dict[str, str], str]:
        today = self._today()
        first = last_months(today, months)[0]
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            profile = await uow.user_profiles.get(user_id) or {}
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(user_id, from_date=f"{first}-01")
        lines = [
            monthly.MonthlyLine(
                line["account_id"],
                from_minor(line["limit_minor"], currency),
                bool(line["rollover"]),
                line["since"],
            )
            for line in profile.get("monthly_budget", [])
        ]
        names = {a.id: a.name for a in accounts}
        return lines, monthly.spend_by_month(entries, accounts), names, currency

    async def current_lines(self, user_id: str) -> tuple[list[monthly.CurrentLine], str]:
        """This month's lines, as the engine computes them, and the currency."""
        lines, spent, names, currency = await self._monthly(user_id, monthly.CARRY_MONTHS + 1)
        return monthly.current(lines, spent, names, self._today()), currency

    async def current(self, user_id: str) -> dict[str, Any]:
        """This month's budget: per line the limit, what rolled over, what is
        available, spent and left, and the pace (spent against the share of
        the month gone)."""
        today = self._today()
        found, currency = await self.current_lines(user_id)

        def money(amount: Decimal) -> str:
            return str(quantize(amount, currency))

        return {
            "month": monthly.month_of(today),
            "as_of": today.isoformat(),
            "currency": currency,
            "month_gone": str(monthly.month_gone(today).quantize(Decimal("0.0001"))),
            "lines": [
                {
                    "account_id": c.account_id,
                    "category": c.category,
                    "limit_amount": money(c.limit),
                    "carried": money(c.carried),
                    "available": money(c.available),
                    "spent": money(c.spent),
                    "left": money(c.left),
                    "expected_by_now": money(c.expected_by_now),
                    "pace": c.pace,
                }
                for c in found
            ],
        }

    async def trend(self, user_id: str, months: int = 6) -> dict[str, Any]:
        """Spending per expense account in each of the last `months` calendar
        months, this one (so far) last."""
        _, spent, names, currency = await self._monthly(user_id, months)
        window = last_months(self._today(), months)
        return {
            "currency": currency,
            "months": window,
            "categories": [
                {
                    "account_id": account_id,
                    "category": names.get(account_id, account_id),
                    "spent": [str(quantize(v, currency)) for v in values],
                }
                for account_id, values in monthly.trend(spent, window).items()
            ],
        }

    async def create_budget(
        self, user_id: str, period_start: str, period_end: str, lines: list[dict[str, Any]]
    ) -> str:
        """AccountNotFound for a line on an account that is not one of the user's."""
        async with self._uow_factory() as uow:
            await require_own_accounts(uow, user_id, (line["account_id"] for line in lines))
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
                await require_own_accounts(
                    uow, user_id, (line["account_id"] for line in data["lines"])
                )
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
