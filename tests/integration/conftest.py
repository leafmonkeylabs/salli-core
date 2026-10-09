"""Fixtures for tests against a real, freshly migrated Postgres database."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from salli.application.unit_of_work import UnitOfWork
from salli.migrations.support import CORE_SCRIPT_LOCATION, upgrade
from tests.integration.pg import scratch_database


@pytest.fixture
def db(monkeypatch):
    with scratch_database() as url:
        monkeypatch.setenv("DATABASE_URL", url)
        upgrade(CORE_SCRIPT_LOCATION)
        yield url


@pytest.fixture
async def uow_factory(db):
    engine = create_async_engine(db, connect_args={"statement_cache_size": 0})
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield lambda: UnitOfWork(sessions)
    await engine.dispose()
