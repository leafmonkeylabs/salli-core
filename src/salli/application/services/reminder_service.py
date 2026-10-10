"""
ReminderService — filing deadlines, user-defined reminders and alerts.

Filing deadlines come from the user's active tax rule sets (their
`deadlines`): activating a version seeds them and replaces the superseded
version's (application/tax_deadlines.py), and `seed_filing_calendar` refreshes
them on demand. Users can also create custom reminders (e.g. "gather bank
statements").
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from salli.application.tax_deadlines import sync_deadlines


class ReminderService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        budget_svc: Any = None,
        subscription_svc: Any = None,
        insurance_svc: Any = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._budget_svc = budget_svc
        self._subscription_svc = subscription_svc
        self._insurance_svc = insurance_svc

    async def list_reminders(
        self,
        user_id: str,
        status: str | None = None,
    ) -> list[dict]:
        async with self._uow_factory() as uow:
            return await uow.reminders.list_reminders(user_id, status)

    async def create_reminder(
        self,
        user_id: str,
        kind: str,
        due_date: str,
    ) -> str:
        reminder_id = str(uuid.uuid4())
        async with self._uow_factory() as uow:
            await uow.reminders.create_reminder(user_id, reminder_id, kind, due_date)
        return reminder_id

    async def mark_done(self, user_id: str, reminder_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.reminders.mark_done(user_id, reminder_id)

    async def delete_reminder(self, user_id: str, reminder_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.reminders.delete_reminder(user_id, reminder_id)

    async def seed_filing_calendar(
        self, user_id: str, year: str | None = None
    ) -> dict[str, list[str]]:
        """Refresh the filing reminders from the deadlines of the user's
        active tax rule sets (for one year, when `year` names one). Activation
        already does this; this catches up a calendar on demand. Idempotent:
        returns the reminder ids `created`, `updated` and `removed`."""
        report: dict[str, list[str]] = {"created": [], "updated": [], "removed": []}
        async with self._uow_factory() as uow:
            for active in await uow.tax_rule_sets.active_versions(user_id):
                if year is not None and active["year_label"] != year:
                    continue
                synced = await sync_deadlines(uow, user_id, active, active["version"]["content"])
                for key, ids in synced.items():
                    report[key] += ids
        return report

    async def sync_alerts(self, user_id: str, today: str) -> dict[str, int]:
        """
        Detect current alert-worthy conditions across Budget/Subscription/
        Insurance and upsert them as reminders (alert_type/source_domain/
        source_id/severity set). Idempotent: re-running against a still-active
        condition updates the existing row rather than duplicating it.

        Portfolio is deliberately excluded — its rebalancing alerts require a
        target allocation the caller supplies on demand, and nothing is
        persisted to check against automatically here.
        """
        from decimal import Decimal

        to_upsert: list[tuple[str, str, str, str, str, str]] = []

        if self._budget_svc:
            budgets = await self._budget_svc.list_budgets(user_id)
            for budget in budgets:
                summary = await self._budget_svc.get_summary(user_id, budget["id"])
                if not summary:
                    continue
                for line in summary["lines"]:
                    variance = Decimal(line["variance"])
                    if variance < 0:
                        to_upsert.append(
                            (
                                "budget_overspend",
                                "budget",
                                f"{budget['id']}:{line['account_id']}",
                                f"Over budget on {line['category']} by {-variance}",
                                today,
                                "warning",
                            )
                        )

        if self._subscription_svc:
            reports = await self._subscription_svc.get_all_reports(user_id, today)
            for report in reports:
                for alert in report["alerts"]:
                    to_upsert.append(
                        (
                            alert["kind"],
                            "subscription",
                            report["subscription_id"],
                            alert["message"],
                            today,
                            "warning",
                        )
                    )

        if self._insurance_svc:
            insurance_report = await self._insurance_svc.get_report(user_id, today)
            for alert in insurance_report["expiring_soon"]:
                # ExpiryAlert has no policy id — (type, name) is the best available key.
                source_id = f"{alert['policy_type']}:{alert['policy_name']}"
                to_upsert.append(
                    (
                        "policy_expiring",
                        "insurance",
                        source_id,
                        f"{alert['policy_name']} expires in {alert['days_until_expiry']} days",
                        alert["expiry_date"],
                        "warning",
                    )
                )
            for policy_type in insurance_report["missing_types"]:
                to_upsert.append(
                    (
                        "coverage_missing",
                        "insurance",
                        policy_type,
                        f"No active {policy_type} insurance coverage",
                        today,
                        "critical",
                    )
                )

        counts: dict[str, int] = {}
        async with self._uow_factory() as uow:
            for alert_type, source_domain, source_id, kind, due_date, severity in to_upsert:
                await uow.reminders.upsert_alert(
                    user_id, alert_type, source_domain, source_id, kind, due_date, severity
                )
                counts[alert_type] = counts.get(alert_type, 0) + 1

        return counts
