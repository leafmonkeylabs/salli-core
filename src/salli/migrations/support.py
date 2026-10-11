"""
Shared plumbing for Alembic environments — Salli's and any extension's.

Each environment owns a set of tables (its metadata) and its own version table,
so several histories can share one database without stepping on each other:
autogenerate in one never proposes dropping another's tables.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import create_async_engine

#: The advisory lock every migration run holds (any number: Salli's own).
MIGRATION_LOCK = 0x5A11_0001

#: Salli's own Alembic script directory.
CORE_SCRIPT_LOCATION = str(Path(__file__).resolve().parent)

# Tables owned by libraries rather than any migration history (LangGraph's
# checkpointer creates and migrates these itself).
_EXTERNAL_TABLES = frozenset(
    {"checkpoint_blobs", "checkpoint_migrations", "checkpoint_writes", "checkpoints"}
)


def database_url() -> str:
    """The URL the app uses: DATABASE_URL from the environment (read afresh:
    tests point it at a scratch database), else Settings (which reads .env),
    with DATABASE_PASSWORD in it when the URL has none."""
    from salli.config import database_url as with_password
    from salli.config import get_settings

    settings = get_settings()
    if url := os.environ.get("DATABASE_URL"):
        settings = settings.model_copy(update={"database_url": url})
    return with_password(settings)


def _owns(metadata: MetaData):
    tables = set(metadata.tables)

    def include_object(obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any):
        if type_ == "table":
            # A reflected table this history does not declare belongs to someone
            # else (another history, or a library) — never propose dropping it.
            return name in tables and name not in _EXTERNAL_TABLES
        table = getattr(getattr(obj, "table", None), "name", None)
        if table is not None:
            return table in tables
        return True

    return include_object


def run_env(context: Any, metadata: MetaData, version_table: str) -> None:
    """Run the current Alembic command for one history. Call from env.py."""

    def configure(**kwargs: Any) -> None:
        context.configure(
            target_metadata=metadata,
            version_table=version_table,
            include_object=_owns(metadata),
            **kwargs,
        )

    if context.is_offline_mode():
        configure(url=database_url(), literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    def run(connection: Any) -> None:
        configure(connection=connection)
        with context.begin_transaction():
            # One migrator at a time: the container migrates on every start,
            # and two starting together would otherwise both try to. The
            # second waits here, then finds nothing left to do. Released when
            # the transaction ends.
            connection.execute(text("select pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK})
            context.run_migrations()

    async def run_async() -> None:
        engine = create_async_engine(
            database_url(),
            # Same reason as adapters/db/session.py: a transaction-mode pooler
            # breaks asyncpg's server-side prepared statement cache.
            connect_args={"statement_cache_size": 0},
        )
        async with engine.connect() as conn:
            await conn.run_sync(run)
        await engine.dispose()

    asyncio.run(run_async())


def alembic_config(script_location: str) -> Any:
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", script_location)
    return cfg


def upgrade(script_location: str, revision: str = "head") -> None:
    from alembic import command

    command.upgrade(alembic_config(script_location), revision)


def script_locations(settings: Any) -> list[tuple[str, str]]:
    """(name, script directory) for Salli and each enabled extension that has
    migrations, in the order they must run."""
    from salli.extensions import enabled_specs

    locations = [("salli", CORE_SCRIPT_LOCATION)]
    locations += [(s.name, s.migrations) for s in enabled_specs(settings) if s.migrations]
    return locations
