"""
InsightsService — the numbers a finance dashboard is built on, from the ledger
(domain/reports/insights.py): cash flow and savings rate by month, spending by
category, net worth over time, and the recurring payments the user may not be
tracking as subscriptions yet.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.domain.currency import quantize
from salli.domain.money import from_minor
from salli.domain.reports import insights
from salli.domain.rules.engine import payee_word
from salli.domain.rules.history import booked_transactions
from salli.domain.subscription.engine import find_matches
from salli.domain.subscription.models import Subscription


def _ratio(value: Decimal | None) -> str | None:
    return None if value is None else str(value.quantize(Decimal("0.0001")))


def _money(value: Decimal, currency: str) -> str:
    return str(quantize(value, currency))


class InsightsService:
    def __init__(
        self, uow_factory: Callable[[], Any], today: Callable[[], dt.date] = dt.date.today
    ):
        self._uow_factory = uow_factory
        self._today = today

    async def _ledger(self, user_id: str) -> tuple[list[Any], list[Any], str]:
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(user_id)
            base = await uow.user_profiles.base_currency(user_id)
        return accounts, entries, base

    async def cash_flow(self, user_id: str, months: int = 12) -> dict[str, Any]:
        accounts, entries, base = await self._ledger(user_id)
        flows = insights.cash_flow(entries, accounts, insights.last_months(self._today(), months))
        return {
            "currency": base,
            "months": [
                {
                    "month": f.month,
                    "income": _money(f.income, base),
                    "expenses": _money(f.expenses, base),
                    "net": _money(f.net, base),
                    "savings_rate": _ratio(f.savings_rate),
                }
                for f in flows
            ],
        }

    async def spending(
        self, user_id: str, months: int = 3, by: insights.SpendingAxis = "category"
    ) -> dict[str, Any]:
        accounts, entries, base = await self._ledger(user_id)
        window = insights.last_months(self._today(), months)
        lines = insights.spending(entries, accounts, window, by)
        return {
            "currency": base,
            "by": by,
            "months": window,
            "lines": [
                {
                    "key": line.key,
                    "total": _money(line.total, base),
                    "share": _ratio(line.share),
                    "by_month": {m: _money(v, base) for m, v in line.by_month.items()},
                }
                for line in lines
            ],
        }

    async def net_worth(self, user_id: str, months: int = 24) -> dict[str, Any]:
        accounts, entries, base = await self._ledger(user_id)
        points = insights.net_worth_series(
            entries, accounts, insights.last_months(self._today(), months)
        )
        return {
            "currency": base,
            "points": [
                {
                    "month": p.month,
                    "assets": _money(p.assets, base),
                    "liabilities": _money(p.liabilities, base),
                    "net_worth": _money(p.net_worth, base),
                }
                for p in points
            ],
        }

    async def recurring(self, user_id: str) -> dict[str, Any]:
        """Recurring payments found in the ledger, each with the declared
        subscription that already covers it, if any: one the subscription
        engine matches to these charges, or else one named after the payee."""
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(user_id)
            base = await uow.user_profiles.base_currency(user_id)
            subscriptions = await uow.recurring_subscriptions.list(user_id, active_only=True)
        found = insights.detect_recurring(booked_transactions(entries, accounts), self._today())

        matched: dict[str, str] = {}  # entry id -> subscription id
        for s in subscriptions:
            declared = Subscription(
                name=s["name"],
                amount=from_minor(s["amount_minor"], base),
                frequency=s["frequency"],
                next_due_date=s["next_due_date"],
                account_id=s["account_id"],
                grace_days=s["grace_days"],
                amount_tolerance_pct=Decimal(s["amount_tolerance_pct"]),
            )
            for match in find_matches(declared, entries, accounts):
                matched.setdefault(match.entry_id, s["id"])
        by_name = {payee_word(s["name"]) or s["name"].casefold(): s["id"] for s in subscriptions}

        def covered_by(r: insights.Recurring) -> str | None:
            hit = next((matched[e] for e in r.entry_ids if e in matched), None)
            return hit or by_name.get(r.key)

        items: list[dict[str, Any]] = []
        for r in found:
            subscription_id = covered_by(r)
            items.append(
                {
                    "payee": r.payee,
                    "cadence": r.cadence,
                    "typical_amount": str(quantize(r.typical_amount, r.currency, strict=False)),
                    "varies": r.varies,
                    "currency": r.currency,
                    "account_id": r.account_id,
                    "occurrences": r.occurrences,
                    "last_date": r.last_date,
                    "next_expected": r.next_expected,
                    "examples": list(r.examples),
                    "tracked": subscription_id is not None,
                    "subscription_id": subscription_id,
                }
            )
        return {"items": items}
