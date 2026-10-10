"""Tax rule sets in a real database: the key, immutability, one active version,
and that nothing reaches another user's."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from salli.application.ports import RuleSetExists
from salli.migrations.support import CORE_SCRIPT_LOCATION, alembic_config
from tests.integration.pg import _sync, requires_postgres, scalar
from tests.taxrules.documents import minimal

pytestmark = requires_postgres

A, B = "user-a", "user-b"
NOW = datetime(2031, 2, 1, tzinfo=UTC)


def _fields(content=None, status="validated", **extra):
    return {
        "content": content if content is not None else minimal(),
        "content_hash": "a" * 64,
        "status": status,
        "validation": {"ok": status == "validated", "errors": [], "warnings": [], "examples": []},
        "author_kind": "user",
        "author_name": None,
        "change_note": None,
        **extra,
    }


async def _set_with_version(uow_factory, user=A, region=None):
    async with uow_factory() as uow:
        rule_set = await uow.tax_rule_sets.create_set(user, "XZ", region, "2031", "XZ 2031")
        version = await uow.tax_rule_sets.add_version(user, rule_set["id"], _fields())
    return rule_set, version


def _run(db: str, sql: str) -> None:
    engine = create_engine(_sync(db))
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    finally:
        engine.dispose()


async def test_versions_are_numbered_in_order_and_round_trip(uow_factory):
    rule_set, first = await _set_with_version(uow_factory)
    async with uow_factory() as uow:
        await uow.tax_rule_sets.get_set(A, rule_set["id"], lock=True)
        second = await uow.tax_rule_sets.add_version(
            A, rule_set["id"], _fields(status="invalid", change_note="raise the allowance")
        )
    assert (first["version"], second["version"]) == (1, 2)
    async with uow_factory() as uow:
        stored = await uow.tax_rule_sets.get_version(A, second["id"])
        listed = await uow.tax_rule_sets.list_sets(A)
    assert stored is not None
    assert stored["content"] == minimal()
    assert stored["change_note"] == "raise the allowance"
    assert [v["version"] for v in listed[0]["versions"]] == [1, 2]
    assert "content" not in listed[0]["versions"][0]


async def test_one_rule_set_per_jurisdiction_and_year_even_without_a_region(uow_factory):
    rule_set, _ = await _set_with_version(uow_factory)
    async with uow_factory() as uow:
        with pytest.raises(RuleSetExists) as raised:
            await uow.tax_rule_sets.create_set(A, "XZ", None, "2031", "again")
        assert raised.value.rule_set_id == rule_set["id"]
        # The unit of work is still usable after losing the race.
        assert await uow.tax_rule_sets.find_set(A, "XZ", None, "2031") is not None
    async with uow_factory() as uow:
        # A region is a different rule set, and another user has their own.
        await uow.tax_rule_sets.create_set(A, "XZ", "North", "2031", "XZ North 2031")
        await uow.tax_rule_sets.create_set(B, "XZ", None, "2031", "B's")
        with pytest.raises(RuleSetExists):
            await uow.tax_rule_sets.create_set(A, "XZ", "North", "2031", "again")


async def test_a_version_s_content_can_never_be_updated(db, uow_factory):
    _, version = await _set_with_version(uow_factory)
    for column, value in [
        ("content", "'{}'::jsonb"),
        ("content_hash", "'" + "b" * 64 + "'"),
        ("version", "9"),
        ("user_id", f"'{B}'"),
    ]:
        with pytest.raises(Exception, match="immutable"):
            _run(
                db,
                f"update tax_rule_set_versions set {column} = {value} where id = '{version['id']}'",
            )
    # Its lifecycle fields do change.
    _run(db, f"update tax_rule_set_versions set status = 'invalid' where id = '{version['id']}'")
    async with uow_factory() as uow:
        with pytest.raises(ValueError, match="content cannot be changed"):
            await uow.tax_rule_sets.update_version(A, version["id"], {"content": {}})


async def test_a_set_has_at_most_one_active_version(db, uow_factory):
    rule_set, first = await _set_with_version(uow_factory)
    async with uow_factory() as uow:
        second = await uow.tax_rule_sets.add_version(A, rule_set["id"], _fields())
        await uow.tax_rule_sets.update_version(
            A, first["id"], {"status": "active", "activated_at": NOW}
        )
        await uow.tax_rule_sets.set_active(A, rule_set["id"], first["id"])
    with pytest.raises(Exception, match="uq_tax_rule_set_versions_one_active"):
        _run(
            db,
            f"update tax_rule_set_versions set status = 'active', activated_at = now()"
            f" where id = '{second['id']}'",
        )
    with pytest.raises(Exception, match="ck_tax_rule_set_versions_timestamps"):
        _run(
            db, f"update tax_rule_set_versions set status = 'superseded' where id = '{first['id']}'"
        )


async def test_the_database_ties_versions_and_the_active_version_to_their_set(db, uow_factory):
    mine, my_version = await _set_with_version(uow_factory)
    theirs, their_version = await _set_with_version(uow_factory, user=B)
    # A version can't claim another owner than its set's.
    with pytest.raises(Exception, match="fk_tax_rule_set_versions_rule_set"):
        _run(
            db,
            "insert into tax_rule_set_versions (id, rule_set_id, user_id, version, content,"
            " status, validation, author_kind, created_at) values ('x', "
            f"'{mine['id']}', '{B}', 5, '{{}}', 'draft', '{{}}', 'user', now())",
        )
    # A set's active version must be one of its own.
    with pytest.raises(Exception, match="fk_tax_rule_sets_active_version"):
        _run(
            db,
            f"update tax_rule_sets set active_version_id = '{their_version['id']}'"
            f" where id = '{mine['id']}'",
        )
    assert my_version["rule_set_id"] == mine["id"] != theirs["id"]


async def test_nothing_of_one_user_s_is_reachable_by_another(uow_factory):
    rule_set, version = await _set_with_version(uow_factory)
    async with uow_factory() as uow:
        repo = uow.tax_rule_sets
        assert await repo.get_set(B, rule_set["id"]) is None
        assert await repo.get_set(B, rule_set["id"], lock=True) is None
        assert await repo.find_set(B, "XZ", None, "2031") is None
        assert await repo.get_version(B, version["id"]) is None
        assert await repo.list_sets(B) == []
        assert await repo.declared_roles(B) == set()
        assert await repo.export(B) == []
        assert await repo.update_version(B, version["id"], {"status": "invalid"}) is False
        await repo.set_active(B, rule_set["id"], version["id"])
    async with uow_factory() as uow:
        stored = await uow.tax_rule_sets.get_version(A, version["id"])
        unchanged = await uow.tax_rule_sets.get_set(A, rule_set["id"])
    assert stored is not None and stored["status"] == "validated"
    assert unchanged is not None and unchanged["active_version_id"] is None


async def test_declared_roles_come_from_documents_that_match_the_schema(uow_factory):
    rule_set, _ = await _set_with_version(uow_factory)
    junk = {"roles": [{"key": "from_an_invalid_draft"}]}
    async with uow_factory() as uow:
        await uow.tax_rule_sets.add_version(
            A, rule_set["id"], _fields(content=junk, status="invalid", content_hash=None)
        )
    async with uow_factory() as uow:
        assert await uow.tax_rule_sets.declared_roles(A) == {"income", "withheld"}


async def test_deleting_an_account_deletes_its_rule_sets(db, uow_factory):
    rule_set, version = await _set_with_version(uow_factory)
    await _set_with_version(uow_factory, user=B)
    async with uow_factory() as uow:
        await uow.tax_rule_sets.update_version(
            A, version["id"], {"status": "active", "activated_at": NOW}
        )
        await uow.tax_rule_sets.set_active(A, rule_set["id"], version["id"])
    async with uow_factory() as uow:
        counts = await uow.data_portability.delete_all(A)
    assert counts["tax_rule_sets"] == 1
    assert scalar(db, f"select count(*) from tax_rule_set_versions where user_id = '{A}'") == 0
    assert scalar(db, f"select count(*) from tax_rule_set_versions where user_id = '{B}'") == 1


def test_the_migration_reverses_and_reapplies(db):
    config = alembic_config(CORE_SCRIPT_LOCATION)
    command.downgrade(config, "core_0009_investments")
    assert scalar(db, "select to_regclass('tax_rule_sets')") is None
    command.upgrade(config, "head")
    command.check(config)
