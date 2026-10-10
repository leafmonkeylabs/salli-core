"""`salli-server doctor` against a real Postgres: it reaches the database and
tells a migrated one from one that needs `salli-server db upgrade`."""

from __future__ import annotations

from salli.config import Settings
from salli.interfaces.cli import doctor
from tests.integration.pg import requires_postgres, scratch_database

pytestmark = requires_postgres


def test_a_migrated_database_is_ready(db):
    assert doctor.database_check(db).status == "ok"
    [migrations] = doctor.migration_checks(Settings(_env_file=None, database_url=db))
    assert migrations.status == "ok"
    assert migrations.detail.startswith("at head")


def test_an_empty_database_needs_an_upgrade(monkeypatch):
    with scratch_database() as url:
        monkeypatch.setenv("DATABASE_URL", url)
        assert doctor.database_check(url).status == "ok"
        [migrations] = doctor.migration_checks(Settings(_env_file=None, database_url=url))
        assert migrations.status == "fail"
        assert "nothing applied" in migrations.detail
        assert "salli-server db upgrade" in migrations.detail
