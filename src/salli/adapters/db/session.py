"""Async SQLAlchemy session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from salli.config import Settings


def make_engine(settings: Settings):
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        # Supabase's transaction-mode pooler (pgbouncer) hands out connections that
        # may not survive between statements, so asyncpg's server-side prepared
        # statement cache goes stale. Disabling it trades a little query-plan reuse
        # for correctness under pooling.
        connect_args={"statement_cache_size": 0},
    )


def make_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    engine = make_engine(settings)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
