"""
Who may do what, beyond being signed in as the user: permissions a caller
holds because of *how* they signed in, not who they are.

There is one so far. **`tax:activate`** lets a caller make a tax rule set
version the one Salli computes with (docs/taxrules.md, "Lifecycle"). An agent
researching tax law reads arbitrary web pages, any of which may carry
instructions planted to trick it, and a confirmation relayed through the agent
("the user said yes") is only as trustworthy as the agent. So activation is
kept to channels an agent cannot fake:

| How the caller signed in                        | `tax:activate` |
|-------------------------------------------------|----------------|
| the web or mobile app (a Supabase session)      | yes            |
| a personal access token the user made           | yes            |
| the local-development sign-in                   | yes            |
| OAuth, for the REST API, as Salli's own CLI     | yes            |
| OAuth, for the REST API, as any other client    | no             |
| OAuth, for MCP (an AI connector), any client    | never          |

"Salli's own CLI" is a client the server knows as first party
(`oauth_clients.first_party`, seeded by core_0011), never one that registered
itself (RFC 7591): anyone can register a client and call it anything. An MCP
token never reaches the REST API at all (`deps.get_principal` refuses it), and
the MCP server builds its callers with no permissions and offers no tool that
activates; the services check the permission again, so no route that forgets
to can activate either.

Permissions are derived, not stored or requested: no token can be issued
with, or talked into, a permission its sign-in doesn't carry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

#: Make a tax rule set version the active one.
TAX_ACTIVATE = "tax:activate"

#: How a caller signed in (`interfaces/api/deps.Principal.method`, plus MCP).
SignIn = Literal["session", "oauth", "pat", "dev", "mcp"]

AuthorKind = Literal["user", "agent"]


def is_first_party(method: SignIn, *, first_party_client: bool = False) -> bool:
    """Whether a sign-in is the user's own, in a Salli client, rather than an
    application or agent acting for them."""
    if method in ("session", "pat", "dev"):
        return True
    if method == "oauth":
        return first_party_client
    return False  # MCP: an AI connector, whatever client it is


def permissions_for(method: SignIn, *, first_party_client: bool = False) -> frozenset[str]:
    """The permissions a sign-in carries: the table in the module docstring."""
    if is_first_party(method, first_party_client=first_party_client):
        return frozenset({TAX_ACTIVATE})
    return frozenset()


@dataclass(frozen=True)
class Actor:
    """Who is acting on a user's data, for the services that care: whose data
    it is, who to record as the author of what they write, and what they may
    do beyond reading and writing it."""

    user_id: str
    #: "user" for the user's own first-party sign-ins; "agent" for an AI
    #: connector or any other application acting for them.
    kind: AuthorKind
    #: The client's name, when it has one ("Claude", "Salli CLI").
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
    ) -> Actor:
        first_party = is_first_party(method, first_party_client=first_party_client)
        return cls(
            user_id=user_id,
            kind="user" if first_party else "agent",
            name=name,
            permissions=permissions_for(method, first_party_client=first_party_client),
        )
