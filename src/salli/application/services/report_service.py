"""
ReportService — read-only composition over LedgerService/FiService data into
exportable statements: a balance sheet, a net-worth statement (current value
+ historical trend, reusing the fi_scores snapshot history rather than a new
table), and a goal progress report. export_csv() flattens any of the three
into downloadable CSV bytes via the pure domain/reports/csv_export helper.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from salli.domain.currency import quantize


class ReportService:
    def __init__(self, ledger_svc: Any, fi_svc: Any) -> None:
        self._ledger = ledger_svc
        self._fi = fi_svc

    async def get_balance_sheet(self, user_id: str) -> dict[str, Any]:
        accounts = await self._ledger.list_accounts(user_id)
        balances = await self._ledger.get_trial_balance(user_id)
        # Every balance is the account's value in the base currency.
        currency = await self._ledger.base_currency(user_id)

        def money(amount: Decimal) -> str:
            return str(quantize(amount, currency))

        assets: list[dict[str, Any]] = []
        liabilities: list[dict[str, Any]] = []
        equity: list[dict[str, Any]] = []
        total_assets = Decimal(0)
        total_liabilities = Decimal(0)
        total_equity = Decimal(0)

        for acc in accounts:
            bal = balances.get(acc.id, Decimal(0))
            line = {"account_id": acc.id, "code": acc.code, "name": acc.name}
            if acc.type == "asset":
                assets.append({**line, "balance": money(bal)})
                total_assets += bal
            elif acc.type == "liability":
                # Liabilities are credit-normal (negative in trial_balance) —
                # display the magnitude owed, matching ledger_ops.net_worth's convention.
                magnitude = -bal
                liabilities.append({**line, "balance": money(magnitude)})
                total_liabilities += magnitude
            elif acc.type == "equity":
                magnitude = -bal
                equity.append({**line, "balance": money(magnitude)})
                total_equity += magnitude

        return {
            "currency": currency,
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "total_assets": money(total_assets),
            "total_liabilities": money(total_liabilities),
            "total_equity": money(total_equity),
            "net_worth": money(total_assets - total_liabilities),
        }

    async def get_net_worth_statement(self, user_id: str) -> dict[str, Any]:
        latest = await self._fi.get_or_compute_score(user_id)
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
