"""Async SQLAlchemy session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from salli.application import acting
from salli.config import Settings, database_url

_ACTING = text(
    "select set_config('salli.user_id', :person, true), set_config('salli.scope', :scope, true)"
)


class ActingSession(Session):
    """A session whose every transaction says whom it acts for, as the
    row-level security policies read it (application/acting.py): the person,
    or 'system' on one of the system paths, or no one."""


@event.listens_for(ActingSession, "after_begin")
def _set_acting(session: Session, transaction: Any, connection: Any) -> None:
    now = acting.current()
    connection.execute(
        _ACTING,
        {"person": now.person or "", "scope": "system" if now.system else ""},
    )


@asynccontextmanager
async def system_scope(session: AsyncSession, path: str) -> AsyncIterator[None]:
    """Within a transaction already begun for a person, act across people
    for one statement or a few, then for the person again."""
    if path not in acting.SYSTEM_PATHS:
        raise ValueError(f"{path!r} is not a system path (application/acting.py)")
    before = (await session.execute(text("select current_setting('salli.scope', true)"))).scalar()
    await session.execute(text("select set_config('salli.scope', 'system', true)"))
    # Not restored when the block fails: the transaction is rolled back.
    yield
    await session.execute(
        text("select set_config('salli.scope', :scope, true)"), {"scope": before or ""}
    )


def make_engine(settings: Settings, pooled: bool = True):
    """`pooled=False` opens a connection per session and keeps none: what a
    CLI command wants. asyncpg binds a connection to the event loop that opened
    it, so a pooled one kept from one `asyncio.run` fails in the next."""
    pool: dict[str, Any] = (
        {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}
        if pooled
        else {"poolclass": NullPool}
    )
    return create_async_engine(
        database_url(settings),
        **pool,
        # A transaction-mode pooler (PgBouncer, or a hosted Postgres's) hands out
        # connections that may not survive between statements, so asyncpg's
        # server-side prepared statement cache goes stale. Disabling it trades a
        # little query-plan reuse for working behind one.
        connect_args={"statement_cache_size": 0},
    )


def make_session_factory(
    settings: Settings, pooled: bool = True
) -> async_sessionmaker[AsyncSession]:
    engine = make_engine(settings, pooled=pooled)
    return async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession, sync_session_class=ActingSession
    )
