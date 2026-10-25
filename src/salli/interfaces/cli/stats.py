"""
`salli-server stats` — this instance's usage counts, for its owner.

Off unless SALLI_USAGE_COUNTERS is true. Counts only, over the last seven
days, read from the database where the server runs (business/metrics.md).
Nothing is sent unless the owner also sets SALLI_USAGE_REPORT_URL and
SALLI_USAGE_INSTALL_ID and runs `stats --send` (or `jobs send-usage`): then
exactly `report()`'s fields go there, and `--dry-run` prints them instead.
"""

from __future__ import annotations

import asyncio
import datetime
from importlib.metadata import version
from typing import Any

import typer

from salli.interfaces.cli.support import console, emit

#: What a report is: changing its fields changes this.
REPORT_SCHEMA = "salli.usage/1"


def _counts() -> tuple[Any, datetime.datetime, dict[str, int]]:
    from salli.adapters.db.session import make_session_factory
    from salli.adapters.db.usage_counts import usage_counts
    from salli.config import get_settings

    settings = get_settings()
    if not settings.salli_usage_counters:
        console.print(
            "[yellow]Usage counts are off.[/yellow] Set SALLI_USAGE_COUNTERS=true to see them."
        )
        raise typer.Exit(1)
    now = datetime.datetime.now(datetime.UTC)
    counts = asyncio.run(usage_counts(make_session_factory(settings, pooled=False), now))
    return settings, now, counts


def report(install_id: str, now: datetime.datetime, counts: dict[str, int]) -> dict[str, Any]:
    """Everything a report sends: the week's three totals, its end, the
    owner's install id (any value they choose and may change) and Salli's
    version. No one's id, email, name, description or amount."""
    return {
        "schema": REPORT_SCHEMA,
        "install_id": install_id,
        "salli_version": version("salli-core"),
        "week_ending": now.date().isoformat(),
        **counts,
    }


def send_report(dry_run: bool) -> None:
    """POST the report to SALLI_USAGE_REPORT_URL, or print it (`dry_run`)."""
    import httpx

    settings, now, counts = _counts()
    url, install_id = settings.salli_usage_report_url, settings.salli_usage_install_id
    if not dry_run and not (url and install_id):
        console.print(
            "[red]Set SALLI_USAGE_REPORT_URL and SALLI_USAGE_INSTALL_ID to send.[/red] "
            "--dry-run shows what would go."
        )
        raise typer.Exit(1)
    body = report(install_id or "(SALLI_USAGE_INSTALL_ID)", now, counts)
    if dry_run:
        if not emit({"url": url or None, "body": body}):
            console.print(f"Would POST to {url or '(SALLI_USAGE_REPORT_URL)'}:")
            console.print_json(data=body)
        return
    try:
        httpx.post(url, json=body, timeout=30).raise_for_status()
    except httpx.HTTPError as exc:
        console.print(f"[red]Not sent: {type(exc).__name__}[/red]")
        raise typer.Exit(1) from exc
    if not emit({"sent": True, "body": body}):
        console.print(f"[green]✓[/green] Sent the week to {now:%Y-%m-%d} to {url}")


def stats(
    send: bool = typer.Option(
        False, "--send", help="POST the week's totals to SALLI_USAGE_REPORT_URL"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="With --send: print, don't send"),
) -> None:
    """Members active, statement entries imported and reconciliations
    completed in the last seven days (SALLI_USAGE_COUNTERS=true)."""
    if send or dry_run:
        send_report(dry_run)
        return
    _, now, counts = _counts()
    if emit({"week_ending": now.date().isoformat(), **counts}):
        return
    console.print(f"In the seven days to {now:%Y-%m-%d}:")
    console.print(f"  Members active:             {counts['active_members']}")
    console.print(f"  Statement entries imported: {counts['entries_imported']}")
    console.print(f"  Reconciliations completed:  {counts['reconciliations_completed']}")
