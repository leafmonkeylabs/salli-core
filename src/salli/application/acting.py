"""
Whose rows a transaction may touch: the database's own check on every
query, under the application's filtering by user id (docs/security.md,
"Row-level security").

Every table holding a person's data has a row-level security policy
(core_0051) that shows and accepts a row only when its person is the one
the transaction acts for (`salli.user_id`), or when the transaction acts
for the system (`salli.scope = 'system'`). Each transaction sets both from
here (adapters/db/session.py, `ActingSession`): a request acts for its
signed-in person (`deps.get_principal`, the MCP gate, `act_as`), and a
transaction that acts for no one sees no one's rows.

The system scope is for the few paths that must reach across people, and
only these: each is in `SYSTEM_PATHS` with its reason, and `as_system`
refuses any other name.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import ParamSpec, TypeVar

_P = ParamSpec("_P")
_T = TypeVar("_T")

#: Every path that acts across people, and why it must. Nothing else may.
SYSTEM_PATHS: dict[str, str] = {
    "migrations": "a schema or data migration changes every person's rows",
    "sign-in": (
        "a sign-in, a token or an OAuth step is looked up before anyone is known "
        "(sessions, tokens, grants, codes, invitations, throttling)"
    ),
    "members": "the operator's `salli-server members`, `setup` and `doctor` list and add people",
    "member-lookup": (
        "sharing finds a member by email, and shows each side of a grant the other's email"
    ),
    "audit-chain": (
        "the audit log is one hash chain for the instance: a row extends the "
        "last one, whoever's, and `audit verify` reads them all"
    ),
    "erasure": (
        "erasing an account pseudonymises its audit rows, and those of sign-ins "
        "refused under its email's hash, which are no one's"
    ),
    "usage": "the instance's usage counts (`salli-server stats`, `jobs send-usage`) count everyone",
    "jobs": (
        "scheduled work finds who is due across everyone: digests, push alerts, "
        "briefings, bank syncs and tax recomputes (`salli-server jobs`, the cron routes)"
    ),
    "support": (
        "the operator opens, lists and ends support sessions on a person's books "
        "(`salli-server support`); what is read under one acts for that person"
    ),
}


@dataclass(frozen=True)
class Acting:
    #: The person whose rows the transaction may touch.
    person: str | None = None
    #: Or the system path (a SYSTEM_PATHS key) acting across people.
    system: str | None = None


_acting: ContextVar[Acting | None] = ContextVar("salli_acting", default=None)


def current() -> Acting:
    return _acting.get() or Acting()


def act_as(person: str) -> None:
    """Act for `person` from here on, in this request (task)."""
    _acting.set(Acting(person=person))


@contextmanager
def acting_as(person: str) -> Iterator[None]:
    """Act for `person` within the block."""
    token = _acting.set(Acting(person=person))
    try:
        yield
    finally:
        _acting.reset(token)


@contextmanager
def as_system(path: str) -> Iterator[None]:
    """Act across people within the block, for one of SYSTEM_PATHS."""
    if path not in SYSTEM_PATHS:
        raise ValueError(f"{path!r} is not a system path (application/acting.py)")
    token = _acting.set(Acting(system=path))
    try:
        yield
    finally:
        _acting.reset(token)


def system_path(path: str) -> Callable[[Callable[_P, Awaitable[_T]]], Callable[_P, Awaitable[_T]]]:
    """A service method that acts across people, for one of SYSTEM_PATHS."""
    if path not in SYSTEM_PATHS:
        raise ValueError(f"{path!r} is not a system path (application/acting.py)")

    def wrap(method: Callable[_P, Awaitable[_T]]) -> Callable[_P, Awaitable[_T]]:
        @functools.wraps(method)
        async def run(*args: _P.args, **kwargs: _P.kwargs) -> _T:
            with as_system(path):
                return await method(*args, **kwargs)

        return run

    return wrap
