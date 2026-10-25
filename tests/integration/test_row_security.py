"""
Row-level security, under Salli's own filtering by person (core_0051;
application/acting.py; docs/security.md): a transaction acting for one
person sees, changes and deletes only that person's rows, even through a raw
query; one acting for no one sees nothing; and every table holding a
person's data is covered, so a new one without a policy fails here.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from salli.adapters.db.models import Base
from salli.application import acting
from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import Direction
from tests.integration.pg import _sync, requires_postgres

pytestmark = requires_postgres

#: The tables holding no one's data, and why. Every other table must have a
#: forced row-level security policy.
NO_ONES: dict[str, str] = {
    "alembic_version": "the schema's version",
    "oauth_clients": "the instance's registered applications, before anyone approves one",
    "instance_settings": "the instance's own settings",
    "invitations": "the operator's invitations, before the person has an account",
    "login_failures": "sign-in throttling, under a hash of the email or address tried",
}


def test_every_table_holding_a_persons_data_has_a_forced_policy(db):
    engine = create_engine(_sync(db))
    with engine.connect() as conn:
        tables = {
            name: (secured, forced, policies)
            for name, secured, forced, policies in conn.execute(
                text(
                    "select c.relname, c.relrowsecurity, c.relforcerowsecurity,"
                    " (select count(*) from pg_policy p where p.polrelid = c.oid)"
                    " from pg_class c where c.relkind = 'r'"
                    " and c.relnamespace = 'public'::regnamespace"
                )
            )
        }
        with_user_id = {
            r[0]
            for r in conn.execute(
                text(
                    "select table_name from information_schema.columns"
                    " where table_schema = 'public' and column_name = 'user_id'"
                )
            )
        }
    engine.dispose()

    assert set(Base.metadata.tables) <= set(tables)
    assert not with_user_id & set(NO_ONES), "a table with user_id holds a person's data"
    unsecured = sorted(
        name
        for name, (secured, forced, policies) in tables.items()
        if name not in NO_ONES and not (secured and forced and policies)
    )
    assert unsecured == [], (
        "Each table holding a person's data needs ENABLE and FORCE ROW LEVEL SECURITY "
        "and a policy (as core_0051); one holding no one's goes in NO_ONES with why"
    )


@pytest.fixture
async def two_people(uow_factory):
    async with uow_factory() as uow:
        for person in ("ada", "bo"):
            await uow.user_profiles.upsert(person, {"base_currency": "NZD"})
    ledger = LedgerService(uow_factory)
    for person in ("ada", "bo"):
        cash = await ledger.add_account(person, "1000", "Cash", "asset")
        pay = await ledger.add_account(person, "4000", "Pay", "income")
        await ledger.add_entry(
            person,
            "2026-10-01",
            "Pay",
            "manual",
            [
                {"account_id": cash, "direction": Direction.DEBIT, "amount": Decimal(10)},
                {"account_id": pay, "direction": Direction.CREDIT, "amount": Decimal(10)},
            ],
        )
    return uow_factory


async def _raw(uow_factory, sql: str, **params):
    async with uow_factory() as uow:
        return (await uow._session.execute(text(sql), params)).all()  # noqa: SLF001


async def test_a_person_sees_only_their_own_rows_even_through_a_raw_query(two_people):
    with acting.acting_as("ada"):
        assert await _raw(two_people, "select distinct user_id from accounts") == [("ada",)]
        assert await _raw(two_people, "select distinct user_id from journal_entries") == [("ada",)]
        # Postings are reached through their entry's policy.
        assert await _raw(
            two_people,
            "select distinct e.user_id from postings p join journal_entries e on e.id = p.entry_id",
        ) == [("ada",)]
        assert await _raw(two_people, "select count(*) from postings") == [(2,)]
        assert await _raw(two_people, "select id from user_profiles") == [("ada",)]


async def test_a_person_cannot_change_or_delete_anothers_rows(two_people):
    with acting.acting_as("ada"):
        changed = await _raw(
            two_people, "update accounts set name = 'Mine now' where user_id = 'bo' returning id"
        )
        deleted = await _raw(two_people, "delete from reminders where user_id = 'bo' returning id")
        assert changed == [] and deleted == []
        with pytest.raises(ProgrammingError, match="row-level security"):
            await _raw(
                two_people,
                "insert into tags (id, user_id, kind, name) values ('t1', 'bo', 'project', 'x')",
            )
        with pytest.raises(ProgrammingError, match="row-level security"):
            await _raw(two_people, "update accounts set user_id = 'bo' where user_id = 'ada'")
    with acting.acting_as("bo"):
        assert {r[0] for r in await _raw(two_people, "select name from accounts")} == {
            "Cash",
            "Pay",
        }


async def test_acting_for_no_one_sees_nothing_and_the_system_path_sees_all(two_people):
    with acting.acting_as(""):
        assert await _raw(two_people, "select count(*) from accounts") == [(0,)]
    with acting.as_system("jobs"):
        assert await _raw(two_people, "select count(*) from accounts") == [(4,)]


def test_an_unlisted_system_path_is_refused():
    with pytest.raises(ValueError, match="not a system path"), acting.as_system("anything"):
        pass


async def test_over_http_a_request_acts_for_its_person_alone(db, real_boundaries):
    """Through the real boundary: sign-in lookups on the sign-in path, then
    every transaction for the signed-in person, with nothing else acting."""
    from salli.composition import build_services
    from salli.config import Settings
    from salli.interfaces.api.deps import get_services, get_settings
    from salli.interfaces.api.main import create_app

    settings = Settings(
        _env_file=None,
        database_url=db,
        environment="production",
        salli_public_url="http://test",
        mcp_signing_secret="s" * 48,
    )
    services = build_services(settings)
    ada = await services.logins.create_account("ada@example.org", "ada's long password", owner=True)
    await services.logins.create_account("bo@example.org", "bo's long password")
    with acting.acting_as(ada["user_id"]):
        await services.ledger.add_account(ada["user_id"], "1000", "Ada's cash", "asset")

    app = create_app()
    app.dependency_overrides[get_services] = lambda: services
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        async def bearer(email: str, password: str) -> dict[str, str]:
            signed_in = await client.post(
                "/v1/auth/sessions", json={"email": email, "password": password}
            )
            assert signed_in.status_code == 201, signed_in.text
            return {"Authorization": f"Bearer {signed_in.json()['token']}"}

        as_ada = await bearer("ada@example.org", "ada's long password")
        as_bo = await bearer("bo@example.org", "bo's long password")
        ada_accounts = (await client.get("/v1/accounts/", headers=as_ada)).json()
        assert [a["name"] for a in ada_accounts] == ["Ada's cash"]
        assert (await client.get("/v1/accounts/", headers=as_bo)).json() == []
        assert (
            await client.get(f"/v1/accounts/{ada_accounts[0]['id']}", headers=as_bo)
        ).status_code == 404


async def test_erasure_as_the_person_pseudonymises_their_audit_rows(two_people):
    async with two_people() as uow:
        await uow.audit_log.log("ada", "sign_in", {}, "succeeded")
        await uow.audit_log.log("e" * 64, "sign_in", {}, "refused")
    with acting.acting_as("ada"):
        async with two_people() as uow:
            counts = await uow.data_portability.delete_all("ada", "erased:ada", ["e" * 64])
        assert counts["audit_logs_pseudonymised"] == 2
        assert counts["accounts"] == 2
    with acting.acting_as("bo"):
        assert await _raw(two_people, "select count(*) from accounts") == [(2,)]
