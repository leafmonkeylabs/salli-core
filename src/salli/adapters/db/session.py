"""Async SQLAlchemy session factory."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from salli.config import Settings, database_url


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
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
