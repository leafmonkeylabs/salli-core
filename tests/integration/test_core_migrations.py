"""
Salli's migration history against a real Postgres: it builds the schema the
ORM describes, owns only its own tables, and the ledger's balance trigger is
in place.
"""

from __future__ import annotations

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from salli.migrations.support import CORE_SCRIPT_LOCATION, alembic_config, upgrade
from tests.integration.pg import _sync, requires_postgres, scalar, scratch_database

pytestmark = requires_postgres


@pytest.fixture
def core_db(monkeypatch):
    with scratch_database() as url:
        monkeypatch.setenv("DATABASE_URL", url)
        upgrade(CORE_SCRIPT_LOCATION)
        yield url


def test_the_baseline_matches_the_orm(core_db):
    """Autogenerate finds nothing to do, so the next migration starts clean."""
    command.check(alembic_config(CORE_SCRIPT_LOCATION))


def test_a_foreign_table_is_never_claimed(core_db):
    """Another history's (or a library's) table in the same database must not
    show up as something to drop."""
    engine = create_engine(_sync(core_db))
    with engine.begin() as conn:
        conn.execute(text("create table someone_elses (id int primary key)"))
    engine.dispose()
    command.check(alembic_config(CORE_SCRIPT_LOCATION))


def test_the_version_is_the_head(core_db):
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(alembic_config(CORE_SCRIPT_LOCATION)).get_current_head()
    assert scalar(core_db, "select version_num from alembic_version") == head


def test_an_unbalanced_entry_cannot_commit(core_db):
    engine = create_engine(_sync(core_db))
    with pytest.raises(Exception, match="Unbalanced journal entry"), engine.begin() as conn:
        conn.execute(
            text(
                "insert into accounts (id, user_id, code, name, type, currency, is_active, created_at)"
                " values ('a1', 'u1', '1000', 'Cash', 'asset', 'LKR', true, now())"
            )
        )
        conn.execute(
            text(
                "insert into journal_entries (id, user_id, entry_date, description, source, created_at)"
                " values ('e1', 'u1', current_date, 'x', 'manual', now())"
            )
        )
        conn.execute(
            text(
                "insert into postings (id, entry_id, account_id, direction, amount_minor,"
                " currency, fx_rate, base_amount_minor)"
                " values ('p1', 'e1', 'a1', 1, 100, 'LKR', 1, 100)"
            )
        )
    engine.dispose()
