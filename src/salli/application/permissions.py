"""
Who may do what, beyond being signed in as the user: permissions a caller
holds because of *how* they signed in, not who they are.

There is one so far. **`tax:activate`** lets a caller make a tax rule set
version the one Salli computes with (docs/taxrules.md, "Lifecycle"). An agent
researching tax law reads arbitrary web pages, any of which may carry
instructions planted to trick it, and a confirmation relayed through the agent
("the user said yes") is only as trustworthy as the agent. So activation is
kept to channels an agent cannot fake:

| How the caller signed in                        | `tax:activate`                    |
|-------------------------------------------------|-----------------------------------|
| a session (signing in with your password)       | yes                               |
| the local-development sign-in                   | yes                               |
| OAuth, for the REST API, as Salli's own CLI     | yes                               |
| OAuth, for the REST API, as Salli's console     | within 5 minutes of the password  |
| a personal access token                         | only if made with it              |
| OAuth, for the REST API, as any other client    | no                                |
| OAuth, for MCP (an AI connector), any client    | never                             |
| the operator's support session (read-only)      | never                             |

"Salli's own CLI" and "Salli's console" are clients the server knows as
first party (`oauth_clients.first_party`, seeded by core_0011 and core_0021),
never ones that registered themselves (RFC 7591): anyone can register a client
and call it anything.

**A person, just now.** A first-party client may say how recent a sign-in its
powerful permissions need (`oauth_clients.step_up_seconds`): 300 seconds for
the console, none for the CLI. A browser is a place agents now work, and a
page showing rule sets an agent drafted from the open web is where injected
script would aim; the CLI's protection, a terminal an agent can't fake, has no
browser equivalent. So a console sign-in holds `tax:activate` only within five
minutes of the password check (`authenticated_at`, carried through refresh),
and after that is sent through Salli's sign-in page again (`needs_step_up`).

An MCP token never reaches the REST API at all (`deps.get_principal` refuses it), and
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
from datetime import timedelta
from typing import Literal

#: Make a tax rule set version the active one.
TAX_ACTIVATE = "tax:activate"

#: Every permission there is: what a personal access token may hold.
KNOWN_PERMISSIONS: frozenset[str] = frozenset({TAX_ACTIVATE})

#: The same names, for typed request and response bodies. A test keeps the
#: two in step.
Permission = Literal["tax:activate"]

#: How a caller signed in (`interfaces/api/deps.Principal.method`, plus MCP).
SignIn = Literal["session", "oauth", "pat", "dev", "mcp", "support"]

AuthorKind = Literal["user", "agent"]


def is_first_party(method: SignIn, *, first_party_client: bool = False) -> bool:
    """Whether a sign-in is the user's own, in a Salli client or a token they
    made, rather than an application or agent acting for them."""
    if method in ("session", "pat", "dev"):
        return True
    if method == "oauth":
        return first_party_client
    return False  # MCP: an AI connector, whatever client it is


#: Permissions that a client's `step_up_seconds` puts behind a recent
#: password check.
POWERFUL: frozenset[str] = frozenset({TAX_ACTIVATE})


def is_recent(sign_in_age: timedelta | None, fresh_within: timedelta | None) -> bool:
    """Whether a sign-in is recent enough: always, when its client asks for
    no particular recency; otherwise only when its age is known and no more
    than `fresh_within` (4:59 of 5:00 is; 5:01 is not)."""
    if fresh_within is None:
        return True
    return sign_in_age is not None and timedelta(0) <= sign_in_age <= fresh_within


def permissions_for(
    method: SignIn,
    *,
    first_party_client: bool = False,
    granted: Iterable[str] = (),
    sign_in_age: timedelta | None = None,
    fresh_within: timedelta | None = None,
) -> frozenset[str]:
    """The permissions a sign-in carries: the table in the module docstring.

    `granted` is what a personal access token stores. It counts for a token
    alone (and only the permissions that exist); any other sign-in's are
    derived from how it signed in. `fresh_within` is how recent its client
    wants the password check behind a powerful permission to be, and
    `sign_in_age` how long ago it was."""
    if method == "pat":
        return frozenset(granted) & KNOWN_PERMISSIONS
    if is_first_party(method, first_party_client=first_party_client):
        held = frozenset({TAX_ACTIVATE})
        return held if is_recent(sign_in_age, fresh_within) else held - POWERFUL
    return frozenset()


def needs_step_up(
    method: SignIn,
    permission: str,
    *,
    first_party_client: bool = False,
    granted: Iterable[str] = (),
    sign_in_age: timedelta | None = None,
    fresh_within: timedelta | None = None,
) -> bool:
    """Whether this sign-in lacks `permission` only because its password
    check is too long ago: signing in again would give it. Never true for an
    AI connector, another application or a token, which never hold it."""
    now = permissions_for(
        method,
        first_party_client=first_party_client,
        granted=granted,
        sign_in_age=sign_in_age,
        fresh_within=fresh_within,
    )
    fresh = permissions_for(method, first_party_client=first_party_client, granted=granted)
    return permission not in now and permission in fresh


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
        sign_in_age: timedelta | None = None,
        fresh_within: timedelta | None = None,
    ) -> Actor:
        first_party = is_first_party(method, first_party_client=first_party_client)
        return cls(
            user_id=user_id,
            kind="user" if first_party else "agent",
            name=name,
            permissions=permissions_for(
                method,
                first_party_client=first_party_client,
                granted=granted,
                sign_in_age=sign_in_age,
                fresh_within=fresh_within,
            ),
        )
