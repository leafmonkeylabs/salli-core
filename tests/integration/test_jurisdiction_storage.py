"""
Tax residency and tax ids in a real database: migration core_0008 turns the
profile's Sri Lankan numbers into tax ids and makes the users who have them
Sri Lankan, and the repository writes the new columns, NULL included.
"""

from __future__ import annotations

import json

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from salli.migrations.support import CORE_SCRIPT_LOCATION, alembic_config, upgrade
from tests.integration.pg import _sync, requires_postgres, scalar, scratch_database

pytestmark = requires_postgres


def _execute(url: str, *statements: tuple[str, dict]) -> None:
    engine = create_engine(_sync(url))
    with engine.begin() as conn:
        for sql, params in statements:
            conn.execute(text(sql), params)
    engine.dispose()


def _profile(user_id: str, ird_number: str | None = None) -> tuple[str, dict]:
    return (
        "insert into user_profiles (id, base_currency, ird_number, mcp_enabled,"
        " daily_briefing_enabled, created_at, updated_at)"
        " values (:id, 'LKR', :ird, false, false, now(), now())",
        {"id": user_id, "ird": ird_number},
    )


def _memory(user_id: str, slug: str, content: str) -> tuple[str, dict]:
    return (
        "insert into agent_documents (id, user_id, title, content, mime_type, tags, source,"
        " namespace, slug, created_at, updated_at)"
        " values (:id, :user, :slug, :content, 'text/plain', '[]', 'agent_memory',"
        " 'memories', :slug, now(), now())",
        {"id": f"{user_id}-{slug}", "user": user_id, "slug": slug, "content": content},
    )


def _computation(user_id: str, result: dict) -> tuple[str, dict]:
    return (
        "insert into tax_computations (id, user_id, year, pack_version, inputs_hash,"
        " result_json, created_at)"
        " values (:id, :user, '2025/26', '1.0.0', 'h', cast(:result as jsonb), now())",
        {"id": f"{user_id}-tc", "user": user_id, "result": json.dumps(result)},
    )


def _row(url: str, user_id: str) -> tuple[object, object, object]:
    engine = create_engine(_sync(url))
    with engine.connect() as conn:
        row = conn.execute(
            text("select tax_residency, tax_ids, ird_number from user_profiles where id = :id"),
            {"id": user_id},
        ).one()
    engine.dispose()
    return row[0], row[1], row[2]


def test_existing_sri_lankan_numbers_become_tax_ids(monkeypatch):
    with scratch_database() as url:
        monkeypatch.setenv("DATABASE_URL", url)
        upgrade(CORE_SCRIPT_LOCATION, "core_0007_ai_connections")
        _execute(
            url,
            # The TIN in the column, and the NIC only ever kept as a memory.
            _profile("both", ird_number="123456789"),
            _memory("both", "nic_number", " 200012345678 "),
            # The TIN only in onboarding's memory: the column was never filled.
            _profile("memory-tin"),
            _memory("memory-tin", "ird_number", "987654321"),
            # A Sri Lankan tax computation and no numbers; one stored before
            # computations recorded their country.
            _profile("computed"),
            _computation("computed", {"pack_country": "LK", "tax_payable": "0"}),
            _profile("computed-long-ago"),
            _computation("computed-long-ago", {"tax_payable": "0"}),
            # Nothing Sri Lankan at all.
            _profile("nobody"),
            # Blank values, and one too long to be a number: none are copied.
            _profile("blank", ird_number="   "),
            _memory("blank", "nic_number", ""),
            _profile("too-long"),
            _memory("too-long", "nic_number", "x" * 40),
        )

        upgrade(CORE_SCRIPT_LOCATION)

        assert _row(url, "both") == (
            "LK",
            [
                {"scheme": "LK-TIN", "value": "123456789"},
                {"scheme": "LK-NIC", "value": "200012345678"},
            ],
            "123456789",
        )
        # The column now agrees with the TIN taken from the memory.
        assert _row(url, "memory-tin") == (
            "LK",
            [{"scheme": "LK-TIN", "value": "987654321"}],
            "987654321",
        )
        assert _row(url, "computed") == ("LK", [], None)
        assert _row(url, "computed-long-ago") == ("LK", [], None)
        assert _row(url, "nobody") == (None, [], None)
        assert _row(url, "blank") == (None, [], "   ")
        assert _row(url, "too-long") == (None, [], None)
        # The memories themselves are untouched.
        assert scalar(url, "select count(*) from agent_documents") == 4


def test_the_migration_reverses(monkeypatch):
    with scratch_database() as url:
        monkeypatch.setenv("DATABASE_URL", url)
        upgrade(CORE_SCRIPT_LOCATION)
        _execute(url, _profile("u", ird_number="123"))
        command.downgrade(alembic_config(CORE_SCRIPT_LOCATION), "core_0007_ai_connections")
        assert scalar(url, "select ird_number from user_profiles where id = 'u'") == "123"
        assert (
            scalar(
                url,
                "select count(*) from information_schema.columns"
                " where table_name = 'user_profiles' and column_name like 'tax_%'",
            )
            == 0
        )


def test_a_residency_is_an_upper_case_code_and_tax_ids_a_list(db):
    _execute(db, _profile("u"))
    for bad in (
        "update user_profiles set tax_residency = 'lk'",
        "update user_profiles set tax_residency = 'L1'",
    ):
        with pytest.raises(Exception, match="ck_user_profiles_tax_residency"):
            _execute(db, (bad, {}))
    with pytest.raises(Exception, match="ck_user_profiles_tax_ids"):
        _execute(db, ("update user_profiles set tax_ids = '{}'::jsonb", {}))


async def test_the_repository_writes_the_tax_identity_and_can_clear_it(db, uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u", {"base_currency": "LKR"})
        assert (await uow.user_profiles.get("u"))["tax_ids"] == []
        await uow.user_profiles.set_tax_identity(
            "u",
            tax_residency="LK",
            tax_ids=[{"scheme": "LK-TIN", "value": "1"}],
            ird_number="1",
        )
    async with uow_factory() as uow:
        profile = await uow.user_profiles.get("u")
        assert (profile["tax_residency"], profile["tax_ids"], profile["ird_number"]) == (
            "LK",
            [{"scheme": "LK-TIN", "value": "1"}],
            "1",
        )
        await uow.user_profiles.set_tax_identity(
            "u", tax_residency=None, tax_ids=[], ird_number=None
        )
    async with uow_factory() as uow:
        profile = await uow.user_profiles.get("u")
        assert (profile["tax_residency"], profile["tax_ids"], profile["ird_number"]) == (
            None,
            [],
            None,
        )
        with pytest.raises(LookupError):
            await uow.user_profiles.set_tax_identity(
                "nobody", tax_residency=None, tax_ids=[], ird_number=None
            )
