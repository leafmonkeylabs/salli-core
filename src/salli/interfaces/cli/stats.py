"""
`salli-server stats` — this instance's usage counts, for its owner.

Off unless SALLI_USAGE_COUNTERS is true. Counts only, over the last seven
days, read from the database where the server runs: Salli never sends them
anywhere (business/metrics.md; a hosted deployment's extension may report
them, docs/hosting.md).
"""

from __future__ import annotations

import asyncio
import datetime

import typer

from salli.interfaces.cli.support import console, emit


def stats() -> None:
    """Members active, statement entries imported and reconciliations
    completed in the last seven days (SALLI_USAGE_COUNTERS=true)."""
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
    if emit({"week_ending": now.date().isoformat(), **counts}):
        return
    console.print(f"In the seven days to {now:%Y-%m-%d}:")
    console.print(f"  Members active:             {counts['active_members']}")
    console.print(f"  Statement entries imported: {counts['entries_imported']}")
    console.print(f"  Reconciliations completed:  {counts['reconciliations_completed']}")
