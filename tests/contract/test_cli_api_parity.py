"""
Anything the API can do, the CLI can do.

Every route Salli serves must either name its `salli` command in
salli/interfaces/parity.py or be listed there with a reason it has none. The
table must also stay true: no command it names may have disappeared, and no
entry may outlive its route.
"""

from __future__ import annotations

from salli.interfaces.api.main import create_app
from salli.interfaces.cli.main import cli
from salli.interfaces.cli.support import leaf_commands
from salli.interfaces.parity import CLI_FOR_ROUTE, NO_CLI


def _routes() -> set[tuple[str, str]]:
    paths = create_app().openapi()["paths"]
    return {(method.upper(), path) for path, ops in paths.items() for method in ops}


def _commands() -> set[str]:
    return {" ".join(path) for path, _ in leaf_commands(cli())}


def test_every_route_has_a_command_or_a_reason():
    missing = sorted(_routes() - set(CLI_FOR_ROUTE) - set(NO_CLI))
    assert not missing, (
        "These routes have no `salli` command. Add one, map it in "
        f"salli/interfaces/parity.py, or list it in NO_CLI with a reason: {missing}"
    )


def test_every_mapped_command_exists():
    commands = _commands()
    dangling = sorted({cmd for cmd in CLI_FOR_ROUTE.values() if cmd not in commands})
    assert not dangling, f"parity.py names commands that do not exist: {dangling}"


def test_the_table_has_no_stale_routes():
    stale = sorted((set(CLI_FOR_ROUTE) | set(NO_CLI)) - _routes())
    assert not stale, f"parity.py lists routes Salli no longer serves: {stale}"


def test_a_route_is_mapped_or_exempt_never_both():
    assert not set(CLI_FOR_ROUTE) & set(NO_CLI)


def test_every_exemption_says_why():
    assert all(reason.strip() for reason in NO_CLI.values())
