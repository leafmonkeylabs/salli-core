"""
Throwaway Postgres databases for migration tests.

Needs SALLI_TEST_DATABASE_URL: a URL to any database on a server where the
user may CREATE DATABASE (e.g. postgresql+asyncpg://postgres:pw@localhost:5432/postgres).
Tests using it are skipped when it is unset.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ADMIN_URL = os.environ.get("SALLI_TEST_DATABASE_URL", "")

requires_postgres = pytest.mark.skipif(
    not ADMIN_URL, reason="SALLI_TEST_DATABASE_URL is not set (needs a Postgres server)"
)


def _sync(url: str) -> str:
    return make_url(url).set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


@contextmanager
def scratch_database() -> Iterator[str]:
    """Create an empty database; yield its asyncpg URL; drop it afterwards."""
    name = f"salli_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(_sync(ADMIN_URL), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'create database "{name}"'))
    try:
        yield (
            make_url(ADMIN_URL)
            .set(drivername="postgresql+asyncpg", database=name)
            .render_as_string(hide_password=False)
        )
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'drop database "{name}" with (force)'))
        admin.dispose()


_SNAPSHOT_QUERIES = {
    "columns": """
        -- Column order, not raw ordinal_position: that is attnum, which keeps
        -- a gap wherever a column was once dropped — a physical artifact of a
        -- database's history, not part of its schema.
        select table_name,
               row_number() over (partition by table_name order by ordinal_position),
               column_name, data_type, udt_name,
               character_maximum_length, numeric_precision, numeric_scale,
               is_nullable, column_default
          from information_schema.columns
         where table_schema = 'public' and table_name not like 'alembic_version%'
         order by 1, 2""",
    "constraints": """
        select conrelid::regclass::text, conname, pg_get_constraintdef(oid)
          from pg_constraint
         where connamespace = 'public'::regnamespace
           and conrelid::regclass::text not like 'alembic_version%'
         order by 1, 2""",
    "indexes": """
        select tablename, indexname, indexdef from pg_indexes
         where schemaname = 'public' and tablename not like 'alembic_version%'
         order by 1, 2""",
    "triggers": """
        select tgrelid::regclass::text, tgname, pg_get_triggerdef(oid)
          from pg_trigger where not tgisinternal order by 1, 2""",
    "functions": """
        select proname, pg_get_functiondef(oid) from pg_proc
         where pronamespace = 'public'::regnamespace order by 1""",
}


def schema_snapshot(url: str) -> dict[str, list[tuple[object, ...]]]:
    """Everything that makes up the public schema, except version tables."""
    engine = create_engine(_sync(url))
    try:
        with engine.connect() as conn:
            return {
                key: [tuple(row) for row in conn.execute(text(sql))]
                for key, sql in _SNAPSHOT_QUERIES.items()
            }
    finally:
        engine.dispose()


def scalar(url: str, sql: str) -> object:
    engine = create_engine(_sync(url))
    try:
        with engine.connect() as conn:
            return conn.execute(text(sql)).scalar()
    finally:
        engine.dispose()
