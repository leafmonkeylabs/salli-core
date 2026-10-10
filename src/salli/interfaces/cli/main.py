"""
`salli-server` — stand up, run and look after a Salli server.

This is the operator's command line, run where the server runs, with the
database at hand: setting up an instance, serving the API, migrating, adding
members, checking health, and the scheduled jobs that act on every user.
Enabled extensions add their own command groups (`ExtensionSpec.cli_groups`).

What a person does with their own finances is not here. That is the `salli`
command line (packages/cli, `npm install --global @leafmonkeylabs/salli`), a
client of the API like the web and mobile apps, so every surface goes through
the same routes and the same checks.

`app`, `cli()` and the helpers in `support` are the stable surface an
extension's commands and tests build on.
"""

from __future__ import annotations

import sys
from typing import Any

import typer
from rich.markup import escape

from salli.interfaces.cli.doctor import doctor
from salli.interfaces.cli.jobs import jobs_app
from salli.interfaces.cli.setup import members_app, serve, setup
from salli.interfaces.cli.support import console, emit, json_mode, with_json_option

app = typer.Typer(
    name="salli-server",
    help="Run and look after a Salli server. Your finances are in the salli CLI: "
    "npm install --global @leafmonkeylabs/salli",
    no_args_is_help=True,
)
db_app = typer.Typer(help="Database migrations", no_args_is_help=True)

app.command("setup")(setup)
app.command("serve")(serve)
app.command("doctor")(doctor)
app.add_typer(db_app, name="db")
app.add_typer(members_app, name="members")
app.add_typer(jobs_app, name="jobs")


# ── db ────────────────────────────────────────────────────────────────────────


@db_app.command("upgrade")
def db_upgrade(
    revision: str = typer.Option("head", help="Target revision (Salli's history only)"),
) -> None:
    """Migrate the database: Salli's tables, then each enabled extension's."""
    from salli.config import get_settings
    from salli.migrations.support import script_locations, upgrade

    upgraded: dict[str, str] = {}
    for name, location in script_locations(get_settings()):
        console.print(f"[bold]{name}[/bold]")
        upgraded[name] = revision if name == "salli" else "head"
        upgrade(location, upgraded[name])
    emit({"upgraded": upgraded})


@db_app.command("current")
def db_current() -> None:
    """Show the revision each migration history is at."""
    import io

    from alembic import command

    from salli.config import get_settings
    from salli.migrations.support import alembic_config, script_locations

    current: dict[str, str] = {}
    for name, location in script_locations(get_settings()):
        console.print(f"[bold]{name}[/bold]")
        cfg = alembic_config(location)
        if json_mode():
            cfg.stdout = io.StringIO()
        command.current(cfg)
        if json_mode():
            current[name] = cfg.stdout.getvalue().strip()
    emit(current)


# ── extensions ────────────────────────────────────────────────────────────────


def _add_extension_groups() -> None:
    """Command groups contributed by enabled extensions (salli/extensions.py)."""
    from salli.config import get_settings
    from salli.extensions import enabled_specs

    for spec in enabled_specs(get_settings()):
        for name, group in spec.cli_groups:
            app.add_typer(group, name=name)


_add_extension_groups()


# ── entrypoint ────────────────────────────────────────────────────────────────


def cli() -> Any:
    """The `salli-server` command tree, with --json on every non-interactive command."""
    return with_json_option(typer.main.get_command(app))


def main() -> None:
    from salli.application.ports import ProfileMissing

    try:
        cli()()
    except ProfileMissing as exc:
        # An extension's command acted as a user (SALLI_USER_ID) who has no
        # profile yet: say what to do rather than end in a traceback.
        console.print(
            f"[red]{escape(str(exc))}.[/red] Run [bold]salli-server setup[/bold] for a new "
            "instance, or [bold]salli-server members add[/bold] to add someone."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
