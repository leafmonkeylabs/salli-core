"""
`salli-server support` — the operator's audited, read-only look at one
person's books, and the only one (docs/security.md, "Support access").

`open` gives a token good for `--minutes` (60, at most 240) that reads that
person's books through the API (`SALLI_TOKEN=… salli …`) and nothing else.
Opening it, each read and its end are in the audit log's hash chain, and
the person sees them all and may end it (`salli support-access`).
"""

from __future__ import annotations

import asyncio
from typing import Any

import typer
from rich.markup import escape
from rich.table import Table

from salli.interfaces.cli.support import console, emit, services

support_app = typer.Typer(
    help="Read one person's books for a support case: time-boxed, audited, shown to them",
    no_args_is_help=True,
)


@support_app.command("open")
def support_open(
    email: str = typer.Argument(..., help="The member's email"),
    reason: str = typer.Option(..., "--reason", help="The ticket, or why"),
    minutes: int = typer.Option(60, "--minutes", min=1, max=240, help="How long (at most 240)"),
) -> None:
    """Open a read-only session on a member's books. The token is shown once."""
    from salli.application.services.support_access_service import SupportRefused

    try:
        opened: dict[str, Any] = asyncio.run(services().support.open(email, reason, minutes))
    except SupportRefused as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc
    if emit(opened):
        return
    console.print(
        f"[green]Opened[/green] {opened['id']} until {opened['expires_at']:%Y-%m-%d %H:%M %Z}. "
        "They see it, and every read, and may end it."
    )
    console.print("Read their books with the salli CLI (GET only), the token shown once:")
    console.print(f"  SALLI_TOKEN={opened['token']} salli accounts list", soft_wrap=True)


@support_app.command("list")
def support_list() -> None:
    """Every support session, open and past, with its reason and reads."""
    sessions: list[dict[str, Any]] = asyncio.run(services().support.list_all())
    if emit(sessions):
        return
    table = Table(title="Support sessions")
    for column in ("Id", "Member", "Reason", "Opened", "Until", "Ended", "Reads"):
        table.add_column(column)
    for s in sessions:
        table.add_row(
            s["id"][:8],
            s["user_id"][:8],
            escape(s["reason"]),
            f"{s['opened_at']:%Y-%m-%d %H:%M}",
            f"{s['expires_at']:%H:%M}",
            f"{s['ended_by']}" if s["ended_at"] else "[green]open[/green]",
            str(len(s["reads"])),
        )
    console.print(table)


@support_app.command("close")
def support_close(session_id: str = typer.Argument(..., help="The session's id")) -> None:
    """End an open support session now."""
    ended = asyncio.run(services().support.close(session_id))
    if not emit({"ended": ended}):
        console.print(
            "[green]Ended.[/green]" if ended else "[red]No open session by that id.[/red]"
        )
    if not ended:
        raise typer.Exit(1)
