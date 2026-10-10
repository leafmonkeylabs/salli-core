"""
`salli-server jobs` — work an operator schedules for every user at once.

Each job does in-process what a cron route does over HTTP (the API's
/advisor/cron/run-due and /bank-connections/cron/sync-due, behind
X-Cron-Secret), so a self-hoster can use a system crontab instead of exposing
those routes. They act on every user, which is why they belong to the server's
command line and not to anyone's client.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any

import typer
from rich.markup import escape
from rich.table import Table

from salli.interfaces.cli.support import console, emit, services

jobs_app = typer.Typer(help="Scheduled work across every user (for cron)", no_args_is_help=True)


@jobs_app.command("run-advisor")
def run_advisor() -> None:
    """Run the advisor for every opted-in user who has not had today's report."""
    from salli.domain.usage import UsageLimitReached

    ran: list[str] = []
    refused: list[str] = []
    failed: list[str] = []

    async def run() -> list[dict[str, Any]]:
        svc = services()
        due: list[dict[str, Any]] = await svc.advisor.due_users()
        for user in due:
            try:
                await svc.advisor.run_advisor(user["user_id"], None, trigger="scheduled")
                ran.append(user["user_id"])
            except UsageLimitReached:
                refused.append(user["user_id"])
            except Exception as exc:  # noqa: BLE001 — one user's failure must not stop the rest
                # The type only: an exception's text may quote the user's data.
                console.print(f"[red]{escape(user['user_id'])}: {type(exc).__name__}[/red]")
                failed.append(user["user_id"])
        return due

    due = asyncio.run(run())
    emit({"due": len(due), "ran": ran, "refused": refused, "failed": failed})
    console.print(
        f"Due: {len(due)} · ran {len(ran)} · refused {len(refused)} · failed {len(failed)}"
    )
    if failed:
        raise typer.Exit(1)


@jobs_app.command("sync-banks")
def sync_banks(
    max_age_hours: int = typer.Option(12, "--max-age-hours", min=1, help="Sync what is older"),
) -> None:
    """Sync every user's bank connections that have not synced lately."""
    from salli.application.services.bank_connection_service import BankConnectionsUnavailable

    try:
        counts: dict[str, int] = asyncio.run(
            services().bank_connections.sync_due(datetime.timedelta(hours=max_age_hours))
        )
    except BankConnectionsUnavailable as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc
    if not emit(counts):
        console.print(
            f"{counts['synced']} of {counts['due']} synced, {counts['failed']} failed, "
            f"{counts['skipped']} already syncing."
        )
    if counts["failed"]:
        raise typer.Exit(1)


@jobs_app.command("recompute-tax")
def recompute_tax(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write the corrected results. Without it, only report what would change.",
    ),
) -> None:
    """
    Re-run every stored tax computation against the current engine.

    The API's latest-computation route serves the most recently *saved*
    result, so after an engine fix a user keeps seeing the old figure until
    they recompute it themselves, and a wrong tax figure is exactly what they
    would act on. Dry run by default: read the report, then run with --apply.
    """
    report: list[dict[str, Any]] = asyncio.run(services().tax.recompute_stored(apply=apply))
    if emit(report):
        return
    if not report:
        console.print("[yellow]No stored tax computations found.[/yellow]")
        return

    table = Table(title="Recomputed stored tax" if apply else "Dry run: nothing written")
    for column in (
        "User",
        "Year",
        "Credits was",
        "Credits now",
        "Payable was",
        "Payable now",
        "Refund",
        "Status",
    ):
        table.add_column(column)

    changed = errored = 0
    for row in report:
        if "error" in row:
            errored += 1
            dashes = ["—"] * 5
            table.add_row(
                row["user_id"][:8], row["year"], *dashes, f"[red]{escape(row['error'])}[/red]"
            )
            continue
        if row["changed"]:
            changed += 1
            status = "[green]applied[/green]" if row["applied"] else "[yellow]would change[/yellow]"
        else:
            status = "[dim]unchanged[/dim]"
        table.add_row(
            row["user_id"][:8],
            row["year"],
            row["old_credits"],
            row["new_credits"],
            row["old_tax_payable"],
            row["new_tax_payable"],
            row["new_refund_due"],
            status,
        )

    console.print(table)
    console.print(
        f"{len(report)} stored · [bold]{changed} changed[/bold]"
        + (f" · [red]{errored} errored[/red]" if errored else "")
        + ("" if apply else "  —  run again with [bold]--apply[/bold] to write")
    )
