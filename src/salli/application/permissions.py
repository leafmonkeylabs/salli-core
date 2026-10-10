"""
Who may do what, beyond being signed in as the user: permissions a caller
holds because of *how* they signed in, not who they are.

There is one so far. **`tax:activate`** lets a caller make a tax rule set
version the one Salli computes with (docs/taxrules.md, "Lifecycle"). An agent
researching tax law reads arbitrary web pages, any of which may carry
instructions planted to trick it, and a confirmation relayed through the agent
("the user said yes") is only as trustworthy as the agent. So activation is
kept to channels an agent cannot fake:

| How the caller signed in                        | `tax:activate`               |
|-------------------------------------------------|------------------------------|
| the web or mobile app (a Supabase session)      | yes                          |
| the local-development sign-in                   | yes                          |
| OAuth, for the REST API, as Salli's own CLI     | yes                          |
| a personal access token                         | only if made with it         |
| OAuth, for the REST API, as any other client    | no                           |
| OAuth, for MCP (an AI connector), any client    | never                        |

"Salli's own CLI" is a client the server knows as first party
(`oauth_clients.first_party`, seeded by core_0011), never one that registered
itself (RFC 7591): anyone can register a client and call it anything. An MCP
token never reaches the REST API at all (`deps.get_principal` refuses it), and
the MCP server builds its callers with no permissions and offers no tool that
activates; the services check the permission again, so no route that forgets
to can activate either.

A personal access token is the one sign-in whose permissions are stored: it
holds exactly those it was made with (`personal_access_tokens.permissions`,
none unless the user asked for them). Tokens are what people hand to scripts
and agents, so a token that can activate is a choice the user makes, never a
default. Only a first-party sign-in other than a token may make one, and it
may give the token only permissions it holds itself (`may_grant`), so no
sign-in can mint a token more capable than it is. Every other sign-in's
permissions are derived here, never stored or requested: no token can be
issued with, or talked into, a permission its sign-in doesn't carry.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

#: Make a tax rule set version the active one.
TAX_ACTIVATE = "tax:activate"

#: Every permission there is: what a personal access token may hold.
KNOWN_PERMISSIONS: frozenset[str] = frozenset({TAX_ACTIVATE})

#: The same names, for typed request and response bodies. A test keeps the
#: two in step.
Permission = Literal["tax:activate"]

#: How a caller signed in (`interfaces/api/deps.Principal.method`, plus MCP).
SignIn = Literal["session", "oauth", "pat", "dev", "mcp"]

AuthorKind = Literal["user", "agent"]


def is_first_party(method: SignIn, *, first_party_client: bool = False) -> bool:
    """Whether a sign-in is the user's own, in a Salli client or a token they
    made, rather than an application or agent acting for them."""
    if method in ("session", "pat", "dev"):
        return True
    if method == "oauth":
        return first_party_client
    return False  # MCP: an AI connector, whatever client it is


def permissions_for(
    method: SignIn,
    *,
    first_party_client: bool = False,
    granted: Iterable[str] = (),
) -> frozenset[str]:
    """The permissions a sign-in carries: the table in the module docstring.

    `granted` is what a personal access token stores. It counts for a token
    alone (and only the permissions that exist); any other sign-in's are
    derived from how it signed in."""
    if method == "pat":
        return frozenset(granted) & KNOWN_PERMISSIONS
    if is_first_party(method, first_party_client=first_party_client):
        return frozenset({TAX_ACTIVATE})
    return frozenset()


def unknown_permissions(requested: Iterable[str]) -> list[str]:
    """The names in `requested` that aren't permissions, sorted."""
    return sorted(set(requested) - KNOWN_PERMISSIONS)


def may_grant(
    method: SignIn,
    *,
    first_party_client: bool,
    held: frozenset[str],
    requested: Iterable[str],
) -> tuple[bool, list[str]]:
    """Whether a sign-in may make a personal access token carrying
    `requested`, and, when it may not, which of them it can't give.

    Only a first-party sign-in may make a token, never a token itself (so a
    leaked one can't be used to make more), and only with permissions it
    holds."""
    wanted = set(requested)
    if method == "pat" or not is_first_party(method, first_party_client=first_party_client):
        return False, sorted(wanted)
    missing = sorted(wanted - held)
    return not missing, missing


@dataclass(frozen=True)
class Actor:
    """Who is acting on a user's data, for the services that care: whose data
    it is, who to record as the author of what they write, and what they may
    do beyond reading and writing it."""

    user_id: str
    #: "user" for the user's own first-party sign-ins; "agent" for an AI
    #: connector or any other application acting for them.
    kind: AuthorKind
    #: The client's name when it has one ("Claude", "Salli CLI"), or the
    #: personal access token's.
    name: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset[str])

    def may(self, permission: str) -> bool:
        return permission in self.permissions

    @classmethod
    def signed_in(
        cls,
        user_id: str,
        method: SignIn,
        *,
        first_party_client: bool = False,
        name: str | None = None,
        granted: Iterable[str] = (),
    ) -> Actor:
        first_party = is_first_party(method, first_party_client=first_party_client)
        return cls(
            user_id=user_id,
            kind="user" if first_party else "agent",
            name=name,
            permissions=permissions_for(
                method, first_party_client=first_party_client, granted=granted
            ),
        )
