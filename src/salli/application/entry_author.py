"""
Who is posting to the ledger, for the entries they post.

Each journal entry records the person signed in (their user id) and how they
came in (`via`): "console", "cli", "mobile", "oauth:<client>", "token" (a
personal access token), "session", "mcp:<client>", "import" (a statement or
a message imported: the ledger's store says so by the entry's source), and
"automation" for anything outside a signed-in request (a job). The API sets
it when it checks the caller (`deps.get_principal`), the MCP gate for each
tool call; the ledger's store reads it when it saves an entry.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

#: The first-party clients, by the name an entry records.
_FIRST_PARTY = {"salli-console": "console", "salli-cli": "cli", "salli-mobile": "mobile"}


@dataclass(frozen=True)
class EntryAuthor:
    #: The signed-in person, or None outside a request (the owner is then
    #: recorded).
    user_id: str | None
    via: str


_OUTSIDE = EntryAuthor(None, "automation")
_author: ContextVar[EntryAuthor | None] = ContextVar("salli_entry_author", default=None)


def via_for(method: str, client_id: str | None = None) -> str:
    """How a caller signed in, as an entry records it."""
    if method == "oauth":
        return _FIRST_PARTY.get(client_id or "", f"oauth:{client_id}")
    return {"pat": "token"}.get(method, method)


def set_author(user_id: str | None, via: str) -> None:
    """Record `user_id` and `via` as the author of what this request (task)
    posts from here on."""
    _author.set(EntryAuthor(user_id, via))


def current_author() -> EntryAuthor:
    return _author.get() or _OUTSIDE
