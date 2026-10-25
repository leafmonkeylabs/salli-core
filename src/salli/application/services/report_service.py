"""
ReportService — read-only composition over the baseline, LedgerService and
FiService into exportable statements: a balance sheet (the baseline's
balances and debts today), a net-worth statement (current value + historical
trend, reusing the fi_scores snapshot history rather than a new table), and a
goal progress report. export_csv() flattens any of the three
into downloadable CSV bytes via the pure domain/reports/csv_export helper.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from salli.application.services.baseline_service import BaselineService
from salli.domain.baseline import Balance
from salli.domain.currency import quantize


class ReportService:
    def __init__(self, ledger_svc: Any, fi_svc: Any, baselines: BaselineService) -> None:
        self._ledger = ledger_svc
        self._fi = fi_svc
        self._baselines = baselines

    async def get_balance_sheet(self, user_id: str, as_of: str | None = None) -> dict[str, Any]:
        """What is owned and owed on a day (today unless `as_of`) as the baseline counts it
        (`BaselineService.worth`), so its net worth is every other read's:
        each asset and liability account at today's published rate (one
        without a rate is left out, and said in `notes`), a debt the ledger
        doesn't hold at its declared principal, and the totals with each
        account judged on its own sign. Equity as the trial balance keeps it, with
        the income and expenses not yet closed as current-year earnings."""
        day = dt.date.fromisoformat(as_of) if as_of else self._baselines.today()
        [now] = await self._baselines.worth(user_id, [day])
        currency = now.currency

        def money(amount: Decimal) -> str:
            return str(quantize(amount, currency))

        def line(b: Balance, owed: bool) -> dict[str, Any]:
            value = b.value or Decimal(0)
            return {
                "account_id": b.account_id,
                "code": b.code,
                "name": b.name,
                # What a liability owes is shown as a positive amount.
                "balance": money(-value if owed else value),
            }

        known = [b for b in now.balances if b.value is not None]
        liabilities = [line(b, True) for b in known if b.role == "liability"]
        liabilities += [
            {"account_id": None, "code": "", "name": d.name, "balance": money(d.balance)}
            for d in now.debts
            if d.source == "declared"
        ]

        accounts = await self._ledger.list_accounts(user_id)
        balances = await self._ledger.get_trial_balance(user_id, to_date=day.isoformat())
        unrealised = await self._ledger.unrealised_fx(user_id, day.isoformat())
        equity: list[dict[str, Any]] = []
        total_equity = Decimal(0)
        for acc in accounts:
            if acc.type == "equity":
                magnitude = -balances.get(acc.id, Decimal(0))
                equity.append(
                    {
                        "account_id": acc.id,
                        "code": acc.code,
                        "name": acc.name,
                        "balance": money(magnitude),
                    }
                )
                total_equity += magnitude
        # Income less expenses not yet closed into retained earnings
        # (LedgerService.close_year): the books balance without a close.
        earnings = -sum(
            (balances.get(a.id, Decimal(0)) for a in accounts if a.type in ("income", "expense")),
            Decimal(0),
        )
        equity.append(
            {
                "account_id": None,
                "code": "",
                "name": "Current-year earnings",
                "balance": money(earnings),
            }
        )
        total_equity += earnings

        return {
            "currency": currency,
            "assets": [line(b, False) for b in known if b.role != "liability"],
            "liabilities": liabilities,
            "equity": equity,
            "total_assets": money(now.total_assets),
            "total_liabilities": money(now.total_liabilities),
            "total_equity": money(total_equity),
            "net_worth": money(now.net_worth),
            "as_of": day.isoformat(),
            "unrealised_fx": unrealised,
            "notes": [
                *now.notes,
                *unrealised["notes"],
                *await self._ledger.books_note(user_id, day.isoformat()),
            ],
        }

    async def get_net_worth_statement(self, user_id: str) -> dict[str, Any]:
        latest = await self._fi.compute_score(user_id)
        history = await self._fi.get_score_history(user_id)
        # history is ordered most-recent-first; a trend line reads naturally chronologically.
        # `latest` is the bare result_json (no created_at — that lives on the ORM row, not
        # inside the stored payload), so as_of comes from history's most recent row instead.
        trend = [
            {"date": h.get("created_at"), "net_worth": h.get("net_worth")}
            for h in reversed(history)
            if h.get("net_worth") is not None
        ]
        return {
            "currency": latest.get("currency"),
            "current_net_worth": latest.get("net_worth"),
            "as_of": trend[-1]["date"] if trend else None,
            "trend": trend,
        }

    async def get_goal_progress_report(self, user_id: str) -> dict[str, Any]:
        goals = await self._fi.list_goals(user_id)
        completed = [g for g in goals if g["progress"] >= 1.0]
        in_progress = [g for g in goals if g["progress"] < 1.0]
        return {
            "goals": goals,
            "completed_count": len(completed),
            "in_progress_count": len(in_progress),
        }

    async def export_csv(self, report_type: str, user_id: str) -> bytes:
        from salli.domain.reports.csv_export import rows_to_csv

        if report_type == "balance-sheet":
            report = await self.get_balance_sheet(user_id)
            rows = [["asset", a["code"], a["name"], a["balance"]] for a in report["assets"]]
            rows += [
                ["liability", entry["code"], entry["name"], entry["balance"]]
                for entry in report["liabilities"]
            ]
            rows += [["equity", e["code"], e["name"], e["balance"]] for e in report["equity"]]
            rows.append(["", "", "Net Worth", report["net_worth"]])
            return rows_to_csv(["Type", "Code", "Account", "Balance"], rows)

        if report_type == "net-worth":
            report = await self.get_net_worth_statement(user_id)
            rows = [[t["date"], t["net_worth"]] for t in report["trend"]]
            return rows_to_csv(["Date", "Net Worth"], rows)

        if report_type == "goal-progress":
            report = await self.get_goal_progress_report(user_id)
            rows = [
                [
                    g["name"],
                    g["kind"],
                    g["target_amount"],
                    g["current_amount"],
                    f"{g['progress'] * 100:.1f}%",
                    g.get("target_date", ""),
                ]
                for g in report["goals"]
            ]
            return rows_to_csv(
                ["Name", "Kind", "Target", "Current", "Progress", "Target Date"], rows
            )

        raise ValueError(f"Unknown report type: {report_type}")
