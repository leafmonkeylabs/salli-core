"""
ReminderService — filing calendar and user-defined reminders.

Automatically seeds tax-deadline reminders from the active tax pack's
FilingCalendar when a user's first account is created. Users can also
create custom reminders (e.g. "gather bank statements").
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any


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

    async def seed_filing_calendar(self, user_id: str, year: str = "2025/26") -> list[str]:
        """
        Seed the standard IRD filing deadlines for the given year of assessment.
        Safe to call multiple times — skips kinds that already exist.
        """
        from salli.domain.tax.packs.registry import get_pack

        pack = get_pack("LK", year)
        cal = pack.filing

        # Extract the year start (April 1 for LK)
        yoa_start = year.split("/")[0]  # "2025"

        deadlines: list[tuple[str, str]] = []
        if cal.return_due:
            deadlines.append((f"return_due_{year}", f"{int(yoa_start) + 1}-{cal.return_due}"))
        for i, mmdd in enumerate(cal.installments, 1):
            yr = yoa_start if int(mmdd[:2]) >= 4 else str(int(yoa_start) + 1)
            deadlines.append((f"installment_{i}_{year}", f"{yr}-{mmdd}"))

        async with self._uow_factory() as uow:
            existing = {r["kind"] for r in await uow.reminders.list_reminders(user_id)}
            created = []
            for kind, due_date in deadlines:
                if kind not in existing and due_date:
                    rid = str(uuid.uuid4())
                    await uow.reminders.create_reminder(user_id, rid, kind, due_date)
                    created.append(rid)

        return created

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
