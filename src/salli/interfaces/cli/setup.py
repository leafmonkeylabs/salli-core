"""
`salli setup`, `salli serve` and `salli members` — standing up a self-hosted
instance and deciding who may use it.

`salli setup` is the one command between `supabase start` and a working
Salli. It is idempotent: every step checks before it acts, so it can be re-run
after a failure, or to add what a later version needs.

1. Write `.env` from `supabase status` (keys already in `.env` are kept).
2. Generate the local secrets Salli needs (BYOK encryption key, MCP signing
   secret, cron secret).
3. Ask for an Anthropic API key, if there is none.
4. Migrate the database.
5. Create the owner's login in Supabase Auth and their Salli profile, kept in
   the currency they choose, and point the CLI at them (SALLI_USER_ID).
6. Seed the starter chart of accounts.

Nothing here prints a secret.
"""

from __future__ import annotations

import asyncio
import base64
import os
import secrets
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx
import typer

from salli.interfaces.cli.support import console, emit

members_app = typer.Typer(help="Who may use this instance")

ENV_FILE = Path(".env")

#: `supabase status -o env` name -> Salli setting.
_FROM_SUPABASE = {
    "API_URL": "SUPABASE_URL",
    "ANON_KEY": "SUPABASE_ANON_KEY",
    "SERVICE_ROLE_KEY": "SUPABASE_SERVICE_ROLE_KEY",
    "JWT_SECRET": "SUPABASE_JWT_SECRET",
    "DB_URL": "DATABASE_URL",
}


# ── .env ─────────────────────────────────────────────────────────────────────


def read_env(path: Path = ENV_FILE) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def add_to_env(new: dict[str, str], path: Path = ENV_FILE) -> list[str]:
    """Append keys that are missing or empty in `path`; never change one that
    has a value. Returns the keys written."""
    current = read_env(path)
    written = [k for k, v in new.items() if v and not current.get(k)]
    if not written:
        return []
    lines = path.read_text().splitlines() if path.exists() else []
    # Blank-valued keys are rewritten in place; the rest are appended.
    for i, line in enumerate(lines):
        key = line.partition("=")[0].strip()
        if key in written and "=" in line and not line.lstrip().startswith("#"):
            lines[i] = f"{key}={new[key]}"
    present = {line.partition("=")[0].strip() for line in lines}
    lines += [f"{k}={new[k]}" for k in written if k not in present]
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)
    for key in written:
        os.environ[key] = new[key]
    return written


def supabase_status() -> dict[str, str]:
    """Connection details of the local Supabase stack, or {} without one."""
    if shutil.which("supabase") is None:
        return {}
    try:
        out = subprocess.run(
            ["supabase", "status", "-o", "env"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return {}
    raw = read_env_text(out)
    found = {_FROM_SUPABASE[k]: v for k, v in raw.items() if k in _FROM_SUPABASE}
    if url := found.get("DATABASE_URL"):
        found["DATABASE_URL"] = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return found


def read_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def generated_secrets() -> dict[str, str]:
    return {
        # version:base64(32 random bytes) — see Settings.byok_encryption_keys.
        "BYOK_ENCRYPTION_KEYS": "1:" + base64.b64encode(os.urandom(32)).decode(),
        "MCP_SIGNING_SECRET": secrets.token_urlsafe(48),
        "CRON_SECRET": secrets.token_urlsafe(32),
    }


def _reload_settings() -> Any:
    import salli.config

    salli.config._settings = None  # pyright: ignore[reportPrivateUsage]
    return salli.config.get_settings()


# ── Supabase Auth admin ──────────────────────────────────────────────────────


class AuthAdminError(RuntimeError):
    pass


def create_login(settings: Any, email: str, password: str | None) -> str:
    """Create (or find) a confirmed Supabase Auth user; return its id.

    Uses the Admin API with the service-role key, so it works with public
    sign-up switched off — which is how a self-hosted instance runs.
    """
    if not (settings.supabase_url and settings.supabase_service_role_key):
        raise AuthAdminError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
    base = settings.supabase_url.rstrip("/") + "/auth/v1/admin/users"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    body: dict[str, Any] = {"email": email, "email_confirm": True}
    if password:
        body["password"] = password
    resp = httpx.post(base, json=body, headers=headers, timeout=15)
    if resp.status_code < 300:
        return str(resp.json()["id"])
    if resp.status_code in (409, 422):
        page = 1
        while True:
            listed = httpx.get(
                base, params={"page": page, "per_page": 200}, headers=headers, timeout=15
            )
            listed.raise_for_status()
            users = listed.json().get("users", [])
            for user in users:
                if str(user.get("email", "")).lower() == email.lower():
                    return str(user["id"])
            if len(users) < 200:
                break
            page += 1
    raise AuthAdminError(f"Supabase Auth refused to create {email}: HTTP {resp.status_code}")


async def _add_member(user_id: str, email: str, base_currency: str | None = None) -> None:
    from salli.composition import build_services
    from salli.config import get_settings

    svc = build_services(get_settings(), pooled=False)
    await svc.profile.ensure_user(user_id, email, may_create=True, base_currency=base_currency)


def detect_currency() -> str:
    """The currency this machine's locale uses (EUR for de_DE, JPY for ja_JP),
    or USD when the locale says nothing. Only ever a default to confirm."""
    import locale

    from salli.domain.currency import is_currency

    try:
        locale.setlocale(locale.LC_MONETARY, "")
        code = str(locale.localeconv().get("int_curr_symbol", "")).strip()
    except locale.Error:
        code = ""
    return code.upper() if is_currency(code) else "USD"


def choose_currency(given: str | None) -> str:
    from salli.domain.currency import UnknownCurrencyError, normalize_currency

    if given:
        return normalize_currency(given)
    while True:
        answer = typer.prompt(
            "Which currency do you keep your money in? (ISO code — your ledger is measured "
            "in it, and it can't change once you have entries)",
            default=detect_currency(),
        )
        try:
            return normalize_currency(answer)
        except UnknownCurrencyError:
            console.print(
                f"[red]{answer!r} is not an ISO 4217 currency code (e.g. USD, EUR).[/red]"
            )


# ── Commands ─────────────────────────────────────────────────────────────────


def setup(
    email: str = typer.Option(None, help="The owner's email (prompted if omitted)"),
    name: str = typer.Option(None, help="The owner's name (defaults to the email's name part)"),
    income: str = typer.Option(
        "",
        help="Comma-separated income sources for the starter accounts: "
        "employment,freelance,rental,interest,foreign,dividends",
    ),
    skip_llm_key: bool = typer.Option(False, help="Do not ask for an Anthropic API key"),
    currency: str = typer.Option(
        None, help="ISO 4217 code to keep your ledger in (prompted if omitted)"
    ),
    tax_residency: str = typer.Option(
        None,
        "--tax-residency",
        help="The country you are taxed in (ISO 3166-1 alpha-2, e.g. LK): your starter "
        "accounts include its tax accounts when Salli has a tax pack for it",
    ),
):
    """Set up this instance: config, database, and your owner account."""
    from salli.migrations.support import script_locations, upgrade

    # 1–3. Configuration.
    found = supabase_status()
    if found:
        console.print("[green]✓[/green] Found the local Supabase stack")
    elif not read_env().get("SUPABASE_URL"):
        console.print(
            "[yellow]No local Supabase found.[/yellow] Run [bold]supabase start[/bold] first, "
            "or put SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET and "
            "DATABASE_URL in .env yourself."
        )
        raise typer.Exit(1)
    written = add_to_env({**found, **generated_secrets(), "SALLI_STORAGE": "local"})
    if not skip_llm_key and not read_env().get("ANTHROPIC_API_KEY"):
        key = typer.prompt(
            "Anthropic API key (Enter to skip; AI features stay off until you add one)",
            default="",
            hide_input=True,
            show_default=False,
        )
        written += add_to_env({"ANTHROPIC_API_KEY": key.strip()})
    if written:
        console.print(f"[green]✓[/green] Wrote to .env: {', '.join(sorted(written))}")
    settings = _reload_settings()

    # 4. Database.
    for label, location in script_locations(settings):
        upgrade(location)
        console.print(f"[green]✓[/green] Database migrated ({label})")

    # 5. Owner.
    owner_email = email or typer.prompt("Your email (you'll sign in with it)")
    user_id = read_env().get("SALLI_USER_ID")
    if not user_id:
        password = typer.prompt(
            "Choose a password (for the API, the MCP connection page, and any client)",
            hide_input=True,
            confirmation_prompt=True,
        )
        try:
            user_id = create_login(settings, owner_email, password)
        except AuthAdminError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        add_to_env({"SALLI_USER_ID": user_id})
    from salli.composition import build_services

    svc = build_services(settings, pooled=False)
    try:
        existing = asyncio.run(svc.profile.get_base_currency(user_id))
    except LookupError:
        existing = None
    # A re-run keeps the currency the ledger already has.
    base_currency = existing or choose_currency(currency)
    asyncio.run(_add_member(user_id, owner_email, base_currency))
    console.print(f"[green]✓[/green] Owner account ready ({owner_email}, in {base_currency})")

    # 6. Starter ledger.
    result = asyncio.run(
        svc.onboarding.complete(
            user_id,
            {
                "name": name or owner_email.split("@")[0],
                "income_sources": [s.strip() for s in income.split(",") if s.strip()],
                "tax_residency": tax_residency,
            },
        )
    )
    console.print(
        f"[green]✓[/green] Starter chart of accounts "
        f"({len(result['accounts_created'])} created, {len(result['accounts_skipped'])} kept)"
    )
    emit({"user_id": user_id, "email": owner_email, "env_written": sorted(written), **result})

    console.print(
        "\n[bold]Done.[/bold] Try:\n"
        "  uv run salli accounts list\n"
        "  uv run salli entry add --date 2026-10-01 --desc 'Lunch' "
        "--debit <expense-id>:1500 --credit <cash-id>:1500\n"
        "  uv run salli serve            # the HTTP API and MCP server on :8000\n"
    )


def serve(
    host: str = typer.Option("127.0.0.1", help="Interface to bind"),
    port: int = typer.Option(8000, help="Port"),
    reload: bool = typer.Option(False, help="Reload on code changes (development)"),
):
    """Run the HTTP API and the MCP server."""
    import uvicorn

    uvicorn.run("salli.interfaces.api.main:app", host=host, port=port, reload=reload)


@members_app.command("add")
def members_add(
    email: str = typer.Argument(..., help="Their email; they sign in with it"),
    currency: str = typer.Option(
        None, help="ISO 4217 code their ledger is kept in (default: the instance's)"
    ),
):
    """Let someone else (a partner, a household member) use this instance."""
    from salli.config import get_settings

    password = typer.prompt("A password for them", hide_input=True, confirmation_prompt=True)
    try:
        user_id = create_login(get_settings(), email, password)
    except AuthAdminError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    asyncio.run(_add_member(user_id, email, currency))
    emit({"user_id": user_id, "email": email})
    console.print(f"[green]Member added:[/green] {email} ({user_id})")
    console.print(f"  They use the CLI with SALLI_USER_ID={user_id}")
