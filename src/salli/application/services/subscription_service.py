"""
SubscriptionService — declares recurring-expense expectations and computes
missed-charge/price-change reports by matching them against posted ledger
entries. The domain engine never touches the DB; this service fetches ledger
data (via its own uow_factory, same pattern as BudgetService.get_summary) and
calls compute_report().
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.domain.money import to_minor
from salli.domain.subscription import engine
from salli.domain.subscription.models import Subscription


def _subscription_view(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": s["id"],
        "name": s["name"],
        "amount": str(Decimal(s["amount_minor"]) / 100),
        "frequency": s["frequency"],
        "next_due_date": s["next_due_date"],
        "account_id": s["account_id"],
        "grace_days": s["grace_days"],
        "amount_tolerance_pct": s["amount_tolerance_pct"],
        "is_active": s["is_active"],
        "created_at": s.get("created_at"),
        "updated_at": s.get("updated_at"),
    }


def _to_domain(s: dict[str, Any]) -> Subscription:
    return Subscription(
        name=s["name"],
        amount=Decimal(s["amount_minor"]) / 100,
        frequency=s["frequency"],
        next_due_date=s["next_due_date"],
        account_id=s["account_id"],
        grace_days=s["grace_days"],
        amount_tolerance_pct=Decimal(s["amount_tolerance_pct"]),
    )


def _report_view(subscription: dict[str, Any], report: Any) -> dict[str, Any]:
    return {
        "subscription_id": subscription["id"],
        "name": subscription["name"],
        "matches": [
            {"entry_id": m.entry_id, "entry_date": m.entry_date, "amount": str(m.amount)}
            for m in report.matches
        ],
        "alerts": [
            {
                "kind": a.kind,
                "message": a.message,
                "expected_amount": str(a.expected_amount)
                if a.expected_amount is not None
                else None,
                "actual_amount": str(a.actual_amount) if a.actual_amount is not None else None,
            }
            for a in report.alerts
        ],
    }


class SubscriptionService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    async def add_subscription(self, user_id: str, data: dict[str, Any]) -> str:
        subscription = {
            "name": data["name"],
            "amount_minor": to_minor(Decimal(str(data["amount"]))),
            "frequency": data["frequency"],
            "next_due_date": data["next_due_date"],
            "account_id": data.get("account_id"),
            "grace_days": data.get("grace_days", 5),
            "amount_tolerance_pct": str(Decimal(str(data.get("amount_tolerance_pct", "0.05")))),
        }
        async with self._uow_factory() as uow:
            return await uow.recurring_subscriptions.save(user_id, subscription)

    async def list_subscriptions(
        self, user_id: str, active_only: bool = True
    ) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            subscriptions = await uow.recurring_subscriptions.list(user_id, active_only)
        return [_subscription_view(s) for s in subscriptions]

    async def get_subscription(self, user_id: str, subscription_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            s = await uow.recurring_subscriptions.get(user_id, subscription_id)
        return _subscription_view(s) if s else None

    async def update_subscription(
        self, user_id: str, subscription_id: str, data: dict[str, Any]
    ) -> None:
        updates: dict[str, Any] = {}
        if "name" in data:
            updates["name"] = data["name"]
        if "amount" in data:
            updates["amount_minor"] = to_minor(Decimal(str(data["amount"])))
        if "frequency" in data:
            updates["frequency"] = data["frequency"]
        if "next_due_date" in data:
            updates["next_due_date"] = data["next_due_date"]
        if "account_id" in data:
            updates["account_id"] = data["account_id"]
        if "grace_days" in data:
            updates["grace_days"] = data["grace_days"]
        if "amount_tolerance_pct" in data:
            updates["amount_tolerance_pct"] = str(Decimal(str(data["amount_tolerance_pct"])))
        if "is_active" in data:
            updates["is_active"] = data["is_active"]
        async with self._uow_factory() as uow:
            await uow.recurring_subscriptions.update(user_id, subscription_id, updates)

    async def delete_subscription(self, user_id: str, subscription_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.recurring_subscriptions.delete(user_id, subscription_id)

    async def get_report(
        self, user_id: str, subscription_id: str, today: str
    ) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            subscription = await uow.recurring_subscriptions.get(user_id, subscription_id)
            if subscription is None:
                return None
            accounts = await uow.ledger.get_accounts(user_id)
            entries = await uow.ledger.get_entries(user_id)

        report = engine.compute_report(_to_domain(subscription), entries, accounts, today)
        return _report_view(subscription, report)

    async def get_all_reports(self, user_id: str, today: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            subscriptions = await uow.recurring_subscriptions.list(user_id, active_only=True)
            accounts = await uow.ledger.get_accounts(user_id)
            entries = await uow.ledger.get_entries(user_id)

        reports: list[dict[str, Any]] = []
        for subscription in subscriptions:
            report = engine.compute_report(_to_domain(subscription), entries, accounts, today)
            reports.append(_report_view(subscription, report))
        return reports
