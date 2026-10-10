"""
`salli-server doctor` — is this server set up to run?

It checks what a server needs before `salli-server serve`: the configuration
loads, the enabled extensions load, the database answers, every migration
history is at its head, and authentication and the server's own secrets are
set. It says whether each secret is set, never what it is, and names the
database by host, port and name only: the output is safe to paste into an
issue.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, Literal

import typer
from rich.markup import escape
from rich.table import Table

from salli.interfaces.cli.support import console, emit

Status = Literal["ok", "warn", "fail"]

#: How long to wait for the database before calling it unreachable.
CONNECT_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class Check:
    name: str
    status: Status
    detail: str


def describe_database(url: str) -> str:
    """`postgresql+asyncpg://db.example.com:5432/salli`: where the database is,
    without the user name or the password."""
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import ArgumentError

    try:
        parsed = make_url(url)
    except ArgumentError:
        return "an unreadable DATABASE_URL"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.drivername}://{parsed.host or 'localhost'}{port}/{parsed.database or ''}"


def _scrub(message: str, url: str) -> str:
    """An error's first line, with the URL and its password taken out: drivers
    sometimes quote what they were given."""
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import ArgumentError

    line = (message.strip().splitlines() or [""])[0]
    try:
        password = make_url(url).password
    except ArgumentError:
        password = None
    for secret in (url, password):
        if secret:
            line = line.replace(str(secret), "***")
    return line[:200]


def config_checks(settings: Any) -> list[Check]:
    """What the settings alone say. Reads no secret's value beyond whether it
    is empty."""
    from salli.config import dev_auth_fallback_live

    checks: list[Check] = []

    if settings.supabase_url or settings.supabase_jwt_secret:
        checks.append(Check("Authentication", "ok", "Supabase Auth"))
    elif dev_auth_fallback_live(settings):
        checks.append(
            Check(
                "Authentication",
                "warn",
                "development fallback: any bearer token is taken as the user id. "
                "Never expose this server.",
            )
        )
    else:
        checks.append(
            Check(
                "Authentication",
                "fail",
                "not configured: the API refuses every request. "
                "Set SUPABASE_URL and SUPABASE_JWT_SECRET (salli-server setup writes them).",
            )
        )

    def secret(name: str, value: str, missing: str) -> None:
        checks.append(Check(name, "ok", "set") if value else Check(name, "warn", missing))

    secret(
        "MCP_SIGNING_SECRET",
        settings.mcp_signing_secret,
        "not set: MCP sign-in falls back to the Supabase JWT secret. Set one in production.",
    )
    secret(
        "CRON_SECRET",
        settings.cron_secret,
        "not set: the scheduler routes refuse every call. Use `salli-server jobs` from cron "
        "instead, or set one.",
    )
    secret(
        "BYOK_ENCRYPTION_KEYS",
        settings.byok_encryption_keys,
        "not set: users cannot store their own LLM keys or bank connections.",
    )
    secret(
        "ANTHROPIC_API_KEY",
        settings.anthropic_api_key,
        "not set: the AI runs only on users' own keys or ChatGPT plans.",
    )
    checks.append(
        Check(
            "Instance",
            "ok",
            f"environment {settings.environment}, registration {settings.salli_registration}, "
            f"storage {settings.salli_storage}",
        )
    )
    return checks


def extensions_check(settings: Any) -> Check:
    from salli.extensions import ExtensionError, enabled_specs

    try:
        names = [spec.name for spec in enabled_specs(settings)]
    except ExtensionError as exc:
        return Check("Extensions", "fail", str(exc))
    return Check("Extensions", "ok", ", ".join(names) if names else "none enabled")


def database_check(url: str) -> Check:
    """Connects and runs `select 1`."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    where = describe_database(url)

    async def ping() -> None:
        engine = create_async_engine(
            url,
            # As the app's own engine: Supabase's transaction pooler breaks
            # asyncpg's prepared statement cache.
            connect_args={"statement_cache_size": 0, "timeout": CONNECT_TIMEOUT_SECONDS},
        )
        try:
            async with engine.connect() as conn:
                await conn.execute(text("select 1"))
        finally:
            await engine.dispose()

    try:
        asyncio.run(asyncio.wait_for(ping(), CONNECT_TIMEOUT_SECONDS + 5))
    except Exception as exc:  # noqa: BLE001 — any failure to connect is the finding
        reason = _scrub(str(exc), url) or type(exc).__name__
        return Check("Database", "fail", f"cannot reach {where}: {reason}")
    return Check("Database", "ok", f"reachable at {where}")


def current_heads(script_location: str) -> tuple[set[str], set[str]]:
    """(the revisions the database is at, the history's heads) for one
    migration history. Runs its env.py, so each history reads its own version
    table, as `alembic current` does."""
    from alembic.runtime.environment import EnvironmentContext
    from alembic.script import ScriptDirectory

    from salli.migrations.support import alembic_config

    cfg = alembic_config(script_location)
    script = ScriptDirectory.from_config(cfg)
    current: set[str] = set()

    def record(rev: Any, context: Any) -> list[Any]:
        current.update(context.get_current_heads())
        return []

    with EnvironmentContext(cfg, script, fn=record):
        script.run_env()
    return current, set(script.get_heads())


def migration_checks(settings: Any) -> list[Check]:
    from salli.migrations.support import script_locations

    checks: list[Check] = []
    for name, location in script_locations(settings):
        label = f"Migrations ({name})"
        try:
            current, heads = current_heads(location)
        except Exception as exc:  # noqa: BLE001 — report it and carry on
            checks.append(Check(label, "fail", f"could not read: {type(exc).__name__}"))
            continue
        if current == heads:
            checks.append(Check(label, "ok", f"at head ({', '.join(sorted(heads))})"))
        else:
            at = ", ".join(sorted(current)) or "nothing applied"
            checks.append(
                Check(
                    label,
                    "fail",
                    f"at {at}, head is {', '.join(sorted(heads))}: run `salli-server db upgrade`",
                )
            )
    return checks


def run_checks() -> list[Check]:
    from pydantic import ValidationError

    from salli.config import get_settings
    from salli.migrations.support import database_url

    try:
        settings = get_settings()
    except ValidationError as exc:
        # The settings' names only: pydantic's own message quotes the values.
        bad = sorted({".".join(str(part) for part in e["loc"]).upper() for e in exc.errors()})
        return [Check("Configuration", "fail", f"invalid: {', '.join(bad)}")]

    checks = [Check("Configuration", "ok", "loaded"), extensions_check(settings)]
    checks += config_checks(settings)
    database = database_check(database_url())
    checks.append(database)
    if database.status == "ok" and checks[1].status == "ok":
        checks += migration_checks(settings)
    else:
        checks.append(Check("Migrations", "warn", "not checked: fix the database first"))
    return checks


_STYLE: dict[Status, str] = {"ok": "green", "warn": "yellow", "fail": "red"}


def doctor() -> None:
    """Check this server's configuration, database and migrations (prints no secrets)."""
    checks = run_checks()
    healthy = all(c.status != "fail" for c in checks)
    if not emit({"ok": healthy, "checks": [asdict(c) for c in checks]}):
        table = Table(show_header=True, box=None)
        table.add_column("CHECK")
        table.add_column("STATUS")
        table.add_column("DETAIL", overflow="fold")
        for c in checks:
            table.add_row(c.name, f"[{_STYLE[c.status]}]{c.status}[/]", escape(c.detail))
        console.print(table)
        console.print(
            "[green]Ready to serve.[/green]"
            if healthy
            else "[red]Not ready:[/red] fix what failed, then run salli-server doctor again."
        )
    if not healthy:
        raise typer.Exit(1)
