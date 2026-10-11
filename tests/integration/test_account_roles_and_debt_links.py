"""
An asset account's role and a debt's account, in a real database: core_0016,
the constraints that keep them meaningful, and the checks that keep each
user's to their own ledger (as #26 does for every other account reference).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from salli.application.ports import AccountNotFound
from salli.application.services.debt_service import DebtService
from salli.application.services.ledger_service import LedgerService
from salli.migrations.support import CORE_SCRIPT_LOCATION, alembic_config, upgrade
from tests.integration.pg import _sync, requires_postgres, scalar, scratch_database

pytestmark = requires_postgres

_BEFORE = "core_0015_fi_assumptions"


def _execute(url: str, *statements: str) -> None:
    engine = create_engine(_sync(url))
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
    engine.dispose()


def _account_sql(id_: str, type_: str, role: str | None = None, currency: str = "CHF") -> str:
    columns = "id, user_id, code, name, type, currency, is_active, created_at"
    values = f"'{id_}', 'u', '{id_}', '{id_}', '{type_}', '{currency}', true, now()"
    if role is not None:
        columns += ", asset_role"
        values += f", '{role}'"
    return f"insert into accounts ({columns}) values ({values})"


def _columns(url: str) -> int:
    return scalar(
        url,
        "select count(*) from information_schema.columns where"
        " (table_name = 'accounts' and column_name = 'asset_role')"
        " or (table_name = 'debts' and column_name = 'account_id')",
    )


def test_core_0016_gives_every_asset_account_a_role_and_reverses(monkeypatch):
    with scratch_database() as url:
        monkeypatch.setenv("DATABASE_URL", url)
        upgrade(CORE_SCRIPT_LOCATION, _BEFORE)
        _execute(
            url,
            _account_sql("bank", "asset"),
            _account_sql("loan", "liability"),
            _account_sql("food", "expense"),
            "insert into debts (id, user_id, name, principal_minor, apr, minimum_payment_minor,"
            " is_active, created_at, updated_at)"
            " values ('d', 'u', 'Loan', 100000, 0.05, 2000, true, now(), now())",
        )
        upgrade(CORE_SCRIPT_LOCATION)

        roles = "select id, asset_role from accounts order by id"
        engine = create_engine(_sync(url))
        with engine.connect() as conn:
            assert [tuple(r) for r in conn.execute(text(roles))] == [
                ("bank", "cash"),
                ("food", None),
                ("loan", None),
            ]
        engine.dispose()
        assert scalar(url, "select account_id from debts where id = 'd'") is None

        command.downgrade(alembic_config(CORE_SCRIPT_LOCATION), _BEFORE)
        assert _columns(url) == 0
        upgrade(CORE_SCRIPT_LOCATION)
        assert _columns(url) == 2
        assert scalar(url, "select asset_role from accounts where id = 'bank'") == "cash"


def test_only_an_asset_account_has_a_role_and_every_one_does(db):
    _execute(db, _account_sql("bank", "asset", "cash"), _account_sql("home", "asset", "other"))
    for sql in (
        _account_sql("nothing", "asset"),
        _account_sql("savings", "asset", "savings"),
        _account_sql("card", "liability", "cash"),
        _account_sql("rent", "expense", "investment"),
    ):
        with pytest.raises(Exception, match="ck_accounts_asset_role"):
            _execute(db, sql)


def test_at_most_one_active_debt_holds_an_account(db):
    _execute(db, _account_sql("loan", "liability"))
    debt = (
        "insert into debts (id, user_id, name, principal_minor, apr, minimum_payment_minor,"
        " is_active, account_id, created_at, updated_at)"
        " values ('{id}', 'u', 'Loan', 100000, 0.05, 2000, {active}, 'loan', now(), now())"
    )
    _execute(db, debt.format(id="old", active="false"), debt.format(id="new", active="true"))
    with pytest.raises(Exception, match="uq_debts_active_account"):
        _execute(db, debt.format(id="twin", active="true"))
    with pytest.raises(Exception, match="debts_account_id_fkey"):
        _execute(db, debt.format(id="nowhere", active="false").replace("'loan'", "'gone'"))


@pytest.fixture
async def ledgers(uow_factory) -> SimpleNamespace:
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("alice", {"base_currency": "CHF"})
        await uow.user_profiles.upsert("bob", {"base_currency": "CHF"})
    ledger = LedgerService(uow_factory)
    return SimpleNamespace(
        ledger=ledger,
        debts=DebtService(uow_factory),
        alice_loan=await ledger.add_account("alice", "2100", "Mortgage", "liability"),
        alice_bank=await ledger.add_account("alice", "1000", "Bank", "asset"),
        bob_loan=await ledger.add_account("bob", "2100", "Car loan", "liability"),
        bob_card=await ledger.add_account("bob", "2000", "Card", "liability", currency="EUR"),
        bob_bank=await ledger.add_account("bob", "1000", "Bank", "asset"),
    )


def _debt(**over: object) -> dict[str, object]:
    return {
        "name": "Car loan",
        "principal": "9000",
        "apr": "0.059",
        "minimum_payment": "300",
        **over,
    }


async def test_an_asset_role_is_stored_and_changes(ledgers):
    ledger = ledgers.ledger
    brokerage = await ledger.add_account(
        "bob", "1300", "Brokerage", "asset", asset_role="investment"
    )
    assert (await ledger.get_account("bob", ledgers.bob_bank)).asset_role == "cash"
    assert (await ledger.get_account("bob", brokerage)).asset_role == "investment"

    # A rename keeps the role; a new one replaces it.
    await ledger.update_account("bob", brokerage, "1300", "Index funds", "asset")
    assert (await ledger.get_account("bob", brokerage)).asset_role == "investment"
    await ledger.update_account(
        "bob", brokerage, "1300", "Index funds", "asset", asset_role="other"
    )
    assert (await ledger.get_account("bob", brokerage)).asset_role == "other"

    # An account that stops being an asset has no role; one that becomes one is cash.
    await ledger.update_account("bob", brokerage, "1300", "Index funds", "liability")
    assert (await ledger.get_account("bob", brokerage)).asset_role is None
    await ledger.update_account("bob", brokerage, "1300", "Index funds", "asset")
    assert (await ledger.get_account("bob", brokerage)).asset_role == "cash"

    with pytest.raises(ValueError, match="Only an asset account"):
        await ledger.add_account("bob", "5000", "Food", "expense", asset_role="cash")


async def test_nobody_sets_the_role_of_someone_elses_account(ledgers):
    with pytest.raises(KeyError):
        await ledgers.ledger.update_account(
            "bob", ledgers.alice_bank, "1000", "Bank", "asset", asset_role="other"
        )
    assert (await ledgers.ledger.get_account("alice", ledgers.alice_bank)).asset_role == "cash"


async def test_a_debt_links_to_its_owners_liability_account(ledgers):
    debts = ledgers.debts
    mine = await debts.add_debt("bob", _debt(account_id=ledgers.bob_loan))
    assert (await debts.get_debt("bob", mine))["account_id"] == ledgers.bob_loan

    # Unlinked with null, and linked again.
    await debts.update_debt("bob", mine, {"account_id": None})
    assert (await debts.get_debt("bob", mine))["account_id"] is None
    await debts.update_debt("bob", mine, {"account_id": ledgers.bob_loan})
    assert (await debts.get_debt("bob", mine))["account_id"] == ledgers.bob_loan


@pytest.mark.parametrize("whose", ["alice", "made-up"])
async def test_a_debt_cannot_link_to_someone_elses_account(ledgers, whose):
    account = ledgers.alice_loan if whose == "alice" else "made-up"
    with pytest.raises(AccountNotFound) as refused:
        await ledgers.debts.add_debt("bob", _debt(account_id=account))
    # Another user's account and one that doesn't exist read the same.
    assert str(refused.value) == f"Account not found: {account}"

    mine = await ledgers.debts.add_debt("bob", _debt())
    with pytest.raises(AccountNotFound):
        await ledgers.debts.update_debt("bob", mine, {"account_id": account})
    assert (await ledgers.debts.get_debt("bob", mine))["account_id"] is None
    assert [d["name"] for d in await ledgers.debts.list_debts("bob")] == ["Car loan"]


async def test_a_debt_links_only_to_a_base_currency_liability_holding_no_other(ledgers):
    debts = ledgers.debts
    with pytest.raises(ValueError, match="liability account"):
        await debts.add_debt("bob", _debt(account_id=ledgers.bob_bank))
    with pytest.raises(ValueError, match="base currency"):
        await debts.add_debt("bob", _debt(account_id=ledgers.bob_card))

    first = await debts.add_debt("bob", _debt(account_id=ledgers.bob_loan))
    with pytest.raises(ValueError, match="already holds"):
        await debts.add_debt("bob", _debt(name="Top-up", account_id=ledgers.bob_loan))

    # Paid off, it lets the account go; it can't come back while another holds it.
    await debts.update_debt("bob", first, {"is_active": False})
    second = await debts.add_debt("bob", _debt(name="Refinanced", account_id=ledgers.bob_loan))
    with pytest.raises(ValueError, match="already holds"):
        await debts.update_debt("bob", first, {"is_active": True})
    assert (await debts.get_debt("bob", second))["is_active"] is True


async def test_a_user_with_a_linked_debt_can_be_deleted(ledgers, uow_factory):
    await ledgers.debts.add_debt("bob", _debt(account_id=ledgers.bob_loan))
    async with uow_factory() as uow:
        counts = await uow.data_portability.delete_all("bob")
    assert counts.get("debts") == 1
    assert await ledgers.ledger.list_accounts("bob") == []
    assert [a.code for a in await ledgers.ledger.list_accounts("alice")] == ["1000", "2100"]
