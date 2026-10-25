"""
`salli-server setup`, `serve`, `members` and `secrets` — standing up an
instance, deciding who may use it, and the secrets it keeps.

`salli-server setup` turns an empty database into a working Salli. It is
idempotent: every step checks before it acts, so it can be re-run after a
failure, or to add what a later version needs.

1. Make sure the server's own secrets exist (BYOK encryption key, MCP signing
   secret, cron secret). In the container they already do (`salli-server
   secrets init` made them in SALLI_SECRETS_DIR); in a development checkout
   the missing ones are written to `.env`.
2. Migrate the database.
3. Create the owner's account — their email and password, kept in the
   currency they choose — unless the instance has an owner already.
4. Ask the owner to turn on two-step sign-in. Until they do, adding and
   inviting members is refused, and `salli-server doctor` says so; lost
   authenticators are recovered with `members reset-password --clear-totp`.
5. Seed the owner's starter chart of accounts.

There is no sign-up: everyone else is added by the owner (`salli-server
members add`), and the owner resets anyone's password here (`salli-server
members reset-password`). Nothing here prints a secret or a password, except the owner's own
authenticator key and recovery codes while they set up two-step sign-in.
"""

from __future__ import annotations

import asyncio
import base64
import os
import secrets
import sys
from pathlib import Path
from typing import Any

import typer
from rich.markup import escape

from salli.application.acting import act_as, acting_as
from salli.interfaces.cli.support import console, emit, services

members_app = typer.Typer(help="Who may use this instance", no_args_is_help=True)
secrets_app = typer.Typer(help="The server's own secrets", no_args_is_help=True)

ENV_FILE = Path(".env")


# ── .env (a development checkout) ────────────────────────────────────────────


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


# ── Secrets ──────────────────────────────────────────────────────────────────


def generated_secrets() -> dict[str, str]:
    """A fresh value for each of the server's own secrets, by setting name."""
    return {
        # version:base64(32 random bytes) — see Settings.byok_encryption_keys.
        "byok_encryption_keys": "1:" + base64.b64encode(os.urandom(32)).decode(),
        "mcp_signing_secret": secrets.token_urlsafe(48),
        "cron_secret": secrets.token_urlsafe(32),
    }


def write_secret_files(directory: Path) -> list[str]:
    """Write each secret that has no file in `directory` yet; never replace
    one. The database password is readable by the database's container too
    (0644); the rest by this user alone (0600). Returns the names written."""
    directory.mkdir(parents=True, exist_ok=True)
    wanted = {"database_password": secrets.token_urlsafe(32), **generated_secrets()}
    written: list[str] = []
    for name, value in wanted.items():
        path = directory / name
        if path.exists() and path.read_text().strip():
            continue
        mode = 0o644 if name == "database_password" else 0o600
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        with os.fdopen(fd, "w") as f:
            f.write(value)
        path.chmod(mode)
        written.append(name)
    return written


def _reload_settings() -> Any:
    import salli.config

    salli.config._settings = None  # pyright: ignore[reportPrivateUsage]
    return salli.config.get_settings()


# ── Prompts ──────────────────────────────────────────────────────────────────


def read_password(password_stdin: bool, prompt: str) -> str:
    """A new password: from the first line of stdin, or asked for twice."""
    if password_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    return typer.prompt(prompt, hide_input=True, confirmation_prompt=True)


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


def _create_account(
    email: str, password: str, *, currency: str | None, owner: bool
) -> dict[str, Any]:
    """Creates the account, or says why not and exits 1."""
    from salli.application.services.login_service import LoginExists

    try:
        return asyncio.run(
            services().logins.create_account(email, password, base_currency=currency, owner=owner)
        )
    except (LoginExists, ValueError) as exc:  # PasswordRejected is a ValueError
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc


def _owner_two_step(owner: dict[str, Any]) -> None:
    """Ask the owner to turn on two-step sign-in, at a terminal; say how otherwise."""
    from salli.application.services.login_service import CodeRefused

    if owner.get("totp_enabled_at") is not None:
        console.print("[green]✓[/green] Two-step sign-in is on")
        return
    logins = services().logins
    if not logins.two_step_available or not sys.stdin.isatty():
        console.print(
            "[yellow]Turn on two-step sign-in[/yellow] (salli totp enable, after salli "
            "login): until then, adding and inviting members is refused."
        )
        return
    enrolment = asyncio.run(logins.begin_totp(str(owner["user_id"])))
    console.print("Two-step sign-in: add this key to your authenticator app.")
    console.print(f"  {enrolment.uri}", soft_wrap=True)
    console.print(f"  (or type the key: {enrolment.secret})")
    for _ in range(3):
        code = typer.prompt("The six-digit code it shows")
        try:
            codes = asyncio.run(logins.confirm_totp(str(owner["user_id"]), code))
        except CodeRefused:
            console.print("[red]That code doesn't match.[/red]")
            continue
        console.print("[green]✓[/green] Two-step sign-in is on. Recovery codes, each good once:")
        console.print("  " + "  ".join(codes))
        return
    raise typer.Exit(1)


def require_owner_two_step() -> None:
    """Exit 1 unless the owner has two-step sign-in on: the owner-only
    commands that let someone in need it."""
    owner = asyncio.run(services().logins.owner())
    if owner is not None and owner.get("totp_enabled_at") is None:
        console.print(
            "[red]Turn on two-step sign-in for the owner first[/red] (salli totp enable). "
            "Lost the authenticator? salli-server members reset-password <email> --clear-totp."
        )
        raise typer.Exit(1)


# ── Commands ─────────────────────────────────────────────────────────────────


def setup(
    email: str = typer.Option(None, help="The owner's email (prompted if omitted)"),
    name: str = typer.Option(None, help="The owner's name (defaults to the email's name part)"),
    income: str = typer.Option(
        "",
        help="Comma-separated income sources for the starter accounts: "
        "employment,freelance,rental,interest,foreign,dividends",
    ),
    currency: str = typer.Option(
        None, help="ISO 4217 code to keep your ledger in (prompted if omitted)"
    ),
    tax_residency: str = typer.Option(
        None,
        "--tax-residency",
        help="The country you are taxed in (ISO 3166-1 alpha-2, e.g. GB): which of your "
        "tax rule sets compute your tax",
    ),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the owner's password from stdin, not a prompt"
    ),
):
    """Set up this instance: secrets, database, and your owner account."""
    from salli.config import get_settings
    from salli.migrations.support import script_locations, upgrade

    # 1. The server's own secrets.
    settings = get_settings()
    missing = {k: v for k, v in generated_secrets().items() if not getattr(settings, k)}
    written: list[str] = []
    if missing and os.environ.get("SALLI_SECRETS_DIR"):
        console.print(
            f"[yellow]Not set: {', '.join(k.upper() for k in sorted(missing))}.[/yellow] "
            "Run [bold]salli-server secrets init[/bold] (the compose file does), or set them."
        )
    elif missing:
        written = add_to_env({k.upper(): v for k, v in missing.items()})
        if written:
            console.print(f"[green]✓[/green] Wrote to .env: {', '.join(sorted(written))}")
        settings = _reload_settings()

    # 2. Database.
    for label, location in script_locations(settings):
        upgrade(location)
        console.print(f"[green]✓[/green] Database migrated ({label})")

    # 3. Owner.
    svc = services()
    owner: dict[str, Any] | None = asyncio.run(svc.logins.owner())
    if owner is None:
        owner_email = email or typer.prompt("Your email (you'll sign in with it)")
        password = read_password(
            password_stdin,
            "Choose a password (at least 12 characters; for the CLI, the MCP connection "
            "page, and any client)",
        )
        owner = _create_account(
            owner_email, password, currency=choose_currency(currency), owner=True
        )
    else:
        console.print("[green]✓[/green] This instance already has an owner")
    user_id = str(owner["user_id"])
    # From here, setup acts for the owner (application/acting.py).
    act_as(user_id)
    base_currency = asyncio.run(svc.profile.get_base_currency(user_id))
    console.print(
        f"[green]✓[/green] Owner account ready ({escape(str(owner['email']))}, in {base_currency})"
    )

    # 4. Two-step sign-in.
    _owner_two_step(owner)

    # 5. Starter ledger.
    result = asyncio.run(
        svc.onboarding.complete(
            user_id,
            {
                "name": name or str(owner["email"]).split("@")[0],
                "income_sources": [s.strip() for s in income.split(",") if s.strip()],
                "tax_residency": tax_residency,
            },
        )
    )
    console.print(
        f"[green]✓[/green] Starter chart of accounts "
        f"({len(result['accounts_created'])} created, {len(result['accounts_skipped'])} kept)"
    )
    emit({"user_id": user_id, "email": owner["email"], "env_written": sorted(written), **result})

    server = settings.salli_public_url.rstrip("/")
    console.print(
        "\n[bold]Done.[/bold] Next, on your own computer:\n"
        "  npm install --global @leafmonkeylabs/salli\n"
        f"  salli login --server {server}   # with the email and password above\n"
    )
    if not settings.anthropic_api_key:
        console.print(
            "AI features need a model: set ANTHROPIC_API_KEY on the server, or have each "
            "person add their own key (salli llm-keys set anthropic)."
        )


def serve(
    host: str = typer.Option("127.0.0.1", help="Interface to bind"),
    port: int = typer.Option(8000, help="Port"),
    reload: bool = typer.Option(False, help="Reload on code changes (development)"),
    migrate: bool = typer.Option(
        False, "--migrate", help="Migrate the database first (what the container does)"
    ),
):
    """Run the HTTP API and the MCP server."""
    import uvicorn

    if migrate:
        from salli.config import get_settings
        from salli.migrations.support import script_locations, upgrade

        for label, location in script_locations(get_settings()):
            upgrade(location)
            console.print(f"[green]✓[/green] Database migrated ({label})")
    # Behind a reverse proxy, uvicorn takes the client's address from
    # X-Forwarded-For only when the proxy is in FORWARDED_ALLOW_IPS
    # (127.0.0.1 unless set): sign-in throttling counts by that address.
    uvicorn.run(
        "salli.interfaces.api.main:app", host=host, port=port, reload=reload, server_header=False
    )


@members_app.command("add")
def members_add(
    email: str = typer.Argument(..., help="Their email; they sign in with it"),
    currency: str = typer.Option(
        None, help="ISO 4217 code their ledger is kept in (default: the instance's)"
    ),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read their password from stdin, not a prompt"
    ),
):
    """Let someone else (a partner, a household member) use this instance."""
    require_owner_two_step()
    password = read_password(password_stdin, "A password for them (at least 12 characters)")
    login = _create_account(email, password, currency=currency, owner=False)
    if emit({"user_id": login["user_id"], "email": login["email"]}):
        return
    console.print(f"[green]Member added:[/green] {escape(login['email'])} ({login['user_id']})")
    console.print("  They sign in with that email and password: salli login, or any client.")


@members_app.command("invite")
def members_invite(
    email: str = typer.Argument(..., help="Their email; they sign in with it"),
    currency: str = typer.Option(
        None, help="ISO 4217 code their ledger is kept in (default: the instance's)"
    ),
):
    """A link, good once for seven days, where someone sets their own password
    (and two-step sign-in). Salli sends no email: pass the link on yourself."""
    from salli.application.services.login_service import INVITATION_TTL, LoginExists
    from salli.config import get_settings

    require_owner_two_step()
    try:
        token = asyncio.run(services().logins.invite(email, base_currency=currency))
    except (LoginExists, ValueError) as exc:
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc
    link = f"{get_settings().salli_public_url.rstrip('/')}/join?t={token}"
    if emit({"email": email, "link": link, "expires_in_days": INVITATION_TTL.days}):
        return
    console.print(f"[green]Invitation made[/green] for {escape(email)}. Send them this link:")
    console.print(f"  {link}", soft_wrap=True)
    console.print("  It works once, for seven days. Anyone with it can join as them.")


@members_app.command("list")
def members_list():
    """Everyone who can sign in here."""
    from rich.table import Table

    logins: list[dict[str, Any]] = asyncio.run(services().logins.list_logins())
    rows: list[dict[str, Any]] = [
        {
            "user_id": login["user_id"],
            "email": login["email"],
            "role": "owner" if login["is_owner"] else "member",
            "created_at": login["created_at"],
            "password_changed_at": login["password_changed_at"],
        }
        for login in logins
    ]
    if emit(rows):
        return
    table = Table(show_header=True, box=None)
    for column in ("EMAIL", "ROLE", "USER ID", "PASSWORD CHANGED"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            escape(row["email"]),
            row["role"],
            row["user_id"],
            f"{row['password_changed_at']:%Y-%m-%d}",
        )
    console.print(table)


@members_app.command("reset-password")
def members_reset_password(
    email: str = typer.Argument(..., help="The email they sign in with"),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the new password from stdin, not a prompt"
    ),
    sign_out_everywhere: bool = typer.Option(
        False,
        "--sign-out-everywhere",
        help="Also revoke their OAuth sign-ins (the CLI, AI connectors) and personal "
        "access tokens, for an account you think was taken over",
    ),
    clear_totp: bool = typer.Option(
        False,
        "--clear-totp",
        help="Also turn off their two-step sign-in, for someone who has lost their "
        "authenticator app and their recovery codes",
    ),
):
    """Set a new password for someone who has forgotten theirs. Ends their sessions."""
    from salli.application.services.login_service import LoginNotFound

    password = read_password(password_stdin, f"A new password for {email}")
    logins = services().logins
    try:
        login = asyncio.run(logins.reset_password(email, password, clear_totp=clear_totp))
    except (LoginNotFound, ValueError) as exc:  # PasswordRejected is a ValueError
        console.print(f"[red]{escape(str(exc))}[/red]")
        raise typer.Exit(1) from exc
    ended: dict[str, int] = {"sessions": int(login["sessions_ended"])}
    if sign_out_everywhere:
        with acting_as(str(login["user_id"])):
            ended = asyncio.run(logins.sign_out_everywhere(str(login["user_id"])))
        ended["sessions"] += int(login["sessions_ended"])
    if emit(
        {
            "user_id": login["user_id"],
            "email": login["email"],
            "revoked": ended,
            "totp_cleared": login["totp_cleared"],
        }
    ):
        return
    console.print(f"[green]Password reset[/green] for {escape(login['email'])}.")
    if login["totp_cleared"]:
        console.print("  Two-step sign-in is off; they can turn it on again.")
    console.print("  Ended: " + ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in ended.items()))
    if not sign_out_everywhere:
        console.print(
            "  Their CLI sign-ins, AI connectors and personal access tokens still work; "
            "--sign-out-everywhere revokes them too."
        )


@secrets_app.command("init")
def secrets_init(
    directory: Path | None = typer.Option(
        None,
        "--dir",
        help="Where to keep them (default: SALLI_SECRETS_DIR)",
        file_okay=False,
    ),
):
    """Generate the server's secrets that don't exist yet, one file each. Never
    replaces one. The compose file runs it before anything else starts."""
    env_dir = os.environ.get("SALLI_SECRETS_DIR")
    target = directory or (Path(env_dir) if env_dir else None)
    if target is None:
        console.print("[red]Say where: --dir, or SALLI_SECRETS_DIR.[/red]")
        raise typer.Exit(1)
    written = write_secret_files(target)
    if emit({"directory": str(target), "written": written}):
        return
    console.print(
        f"[green]✓[/green] Generated {', '.join(written)} in {target}"
        if written
        else f"[green]✓[/green] Every secret already exists in {target}"
    )
