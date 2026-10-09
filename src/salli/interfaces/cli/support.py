"""
What a CLI command needs: the console, the current user, the services, and id
resolution. Public so an extension's command groups (salli/extensions.py) can
use the same plumbing as Salli's own commands without importing cli/main.
"""

from __future__ import annotations

import dataclasses
import datetime
import enum
import json
import os
import sys
from collections.abc import Iterator
from decimal import Decimal
from typing import Any, cast

import typer
from rich.console import Console
from typer.core import TyperOption

console = Console()

# ── --json ───────────────────────────────────────────────────────────────────
#
# Every non-interactive command takes --json (injected by `with_json_option`,
# so no command declares it). In JSON mode the command's data goes to stdout as
# one JSON document and everything the Rich console would have printed —
# progress, confirmations, errors — goes to stderr, so stdout is always
# parseable and exit codes still say whether it worked.

#: Commands that hold a conversation or a review prompt open. They have no
#: single result to print, so --json is not offered.
INTERACTIVE_COMMANDS = frozenset(
    {
        ("agent", "chat"),
        ("agent", "resume"),
        ("tax", "explain"),
        ("tax", "prepare-return"),
        ("advisor", "briefing"),
    }
)

_json_mode = False


def json_mode() -> bool:
    return _json_mode


def _enable_json(ctx: Any, param: Any, value: bool) -> None:
    global _json_mode
    if value and not ctx.resilient_parsing:
        _json_mode = True
        console.file = sys.stderr


def to_jsonable(value: object) -> Any:
    """Plain JSON types for anything a service returns. Money stays a string:
    a Decimal must never pass through a float on its way out."""
    obj: Any = value  # duck-typed below: services return many shapes
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime.date, datetime.datetime, datetime.time)):
        return obj.isoformat()
    if isinstance(obj, enum.Enum):
        return to_jsonable(obj.value)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return to_jsonable(model_dump())
    if isinstance(obj, dict):
        mapping = cast(dict[Any, Any], obj)
        return {str(k): to_jsonable(v) for k, v in mapping.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        items = cast(list[Any], list(obj))  # pyright: ignore[reportUnknownArgumentType]
        return [to_jsonable(v) for v in items]
    if hasattr(obj, "__dict__"):
        fields = cast(dict[str, Any], vars(obj))
        return {k: to_jsonable(v) for k, v in fields.items() if not k.startswith("_")}
    return str(obj)


def emit(data: Any) -> bool:
    """In JSON mode, print `data` as JSON to stdout and return True (the
    command should stop there). Otherwise return False and do nothing."""
    if not _json_mode:
        return False
    sys.stdout.write(json.dumps(to_jsonable(data), indent=2, ensure_ascii=False) + "\n")
    return True


def leaf_commands(group: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    """(path, command) for every runnable command under `group`. Duck-typed:
    Typer builds on its own vendored copy of Click."""
    commands: dict[str, Any] | None = getattr(group, "commands", None)
    if commands is not None:
        for name, sub in commands.items():
            yield from leaf_commands(sub, (*path, name))
    else:
        yield path, group


def with_json_option(root: Any) -> Any:
    """Give every non-interactive command a --json flag."""
    for path, command in leaf_commands(root):
        if path in INTERACTIVE_COMMANDS or any(p.name == "json" for p in command.params):
            continue
        command.params.append(
            TyperOption(
                param_decls=["--json"],
                is_flag=True,
                expose_value=False,
                is_eager=True,
                callback=_enable_json,
                help="Print the result as JSON on stdout (messages go to stderr).",
            )
        )
    return root


def require_user() -> str:
    """The user the CLI acts as: SALLI_USER_ID, from the environment or .env
    (`salli setup` writes it). Refuses rather than guessing: acting as a
    made-up user would quietly put someone's records in an account no one
    can sign in to."""
    from salli.config import get_settings

    user_id = os.environ.get("SALLI_USER_ID") or get_settings().salli_user_id
    if not user_id:
        console.print("[red]No user set.[/red] Run [bold]salli setup[/bold], or set SALLI_USER_ID.")
        raise typer.Exit(1)
    return user_id


def services() -> Any:
    """The services for a command. Unpooled: a command may call asyncio.run
    more than once with them, and a pooled asyncpg connection from an earlier
    (closed) loop fails in the next one ("attached to a different loop")."""
    from salli.composition import build_services
    from salli.config import get_settings

    return build_services(get_settings(), pooled=False)


def resolve_id(items: list[dict[str, Any]], prefix: str, label: str = "item") -> str:
    """
    Resolve a full or truncated (list-display) id to the full id it refers to.
    List commands truncate ids to 8 chars for table display; this lets delete/
    update/show commands accept either the full id or that truncated form,
    instead of silently no-op'ing on a copy-pasted truncated id.
    """
    ids = [str(i.get("id", "")) for i in items]
    if prefix in ids:
        return prefix
    matches = [i for i in ids if i.startswith(prefix)]
    if not matches:
        console.print(f"[red]No {label} found matching id '{prefix}'.[/red]")
        raise typer.Exit(1)
    if len(matches) > 1:
        console.print(
            f"[red]Ambiguous id '{prefix}' matches {len(matches)} {label}s. "
            "Use more characters.[/red]"
        )
        raise typer.Exit(1)
    return matches[0]


def money(amount: Decimal | str | None, currency: str, width: int = 16) -> str:
    """`EUR         1,234.50`: the ISO code, then the amount right-aligned in
    `width` with exactly the currency's decimals (none for JPY, three for KWD).
    For display only — the amount is never parsed back."""
    from salli.domain.currency import exponent, quantize

    if amount is None or amount == "":
        return f"{currency} {'—':>{width}}"
    value = quantize(Decimal(str(amount)), currency, strict=False)
    return f"{currency} {value:>{width},.{exponent(currency, strict=False)}f}"


def amount(value: Decimal | str | None, currency: str) -> str:
    """A table cell: the amount with the currency's decimals, no code."""
    from salli.domain.currency import exponent, quantize

    if value is None or value == "":
        return ""
    rounded = quantize(Decimal(str(value)), currency, strict=False)
    return f"{rounded:,.{exponent(currency, strict=False)}f}"
