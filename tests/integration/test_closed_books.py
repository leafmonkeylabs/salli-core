"""Closed books against a real database: the service refuses an entry on or
before the lock date, and core_0025's and core_0030's triggers refuse one
that comes any other way, or any change to an entry or posting there, so a
filed year can't change behind the service's back."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import AccountNotEmpty, BooksLocked, Direction
from tests.integration.pg import _sync, requires_postgres, scalar

pytestmark = [requires_postgres, pytest.mark.asyncio]


def _legs(debit: str, credit: str) -> list[dict[str, object]]:
    return [
        {"account_id": debit, "direction": Direction.DEBIT, "amount": Decimal("40")},
        {"account_id": credit, "direction": Direction.CREDIT, "amount": Decimal("40")},
    ]


async def test_closed_books_refuse_every_way_in(uow_factory, db):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("alice", {"base_currency": "CAD"})
    ledger = LedgerService(uow_factory, today=lambda: dt.date(2026, 3, 10))
    bank = await ledger.add_account("alice", "1000", "Bank", "asset")
    food = await ledger.add_account("alice", "5000", "Food", "expense")
    lunch = await ledger.add_entry("alice", "2025-11-20", "Lunch", "manual", _legs(food, bank))

    await ledger.set_lock_date("alice", "2025-12-31")
    with pytest.raises(BooksLocked):
        await ledger.add_entry("alice", "2025-12-31", "Late", "manual", _legs(food, bank))

    # Reversed today, in the open period; the original stays where it was.
    reversal_id = await ledger.reverse_entry("alice", lunch, "Paid by a friend")
    reversal = await ledger.get_entry("alice", reversal_id)
    assert reversal is not None
    assert (reversal.entry_date, reversal.source) == ("2026-03-10", "reversal")
    assert reversal.description == "Reversal of Lunch: Paid by a friend"

    engine = create_engine(_sync(db))
    try:
        refused = pytest.raises(Exception, match="closed up to and including 2025-12-31")
        with refused, engine.begin() as conn:
            conn.execute(
                text(
                    "insert into journal_entries (id, user_id, entry_date, description, "
                    "source, created_at, created_by, created_via, seq, hash) values ('e-back', 'alice', '2025-06-01', "
                    "'Backdated', 'manual', now(), 'alice', 'sql', 90, 'x')"
                )
            )
        with engine.begin() as conn:
            conn.execute(
                text(
                    "insert into journal_entries (id, user_id, entry_date, description, "
                    "source, created_at, created_by, created_via, seq, hash) values ('e-open', 'alice', '2026-01-01', "
                    "'Open', 'manual', now(), 'alice', 'sql', 91, 'x')"
                )
            )
    finally:
        engine.dispose()

    await ledger.set_lock_date("alice", None)
    await ledger.add_entry("alice", "2025-12-31", "Late", "manual", _legs(food, bank))


async def _books(uow_factory):
    """Alice's books, closed to the end of 2025: an entry there and one after."""
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("alice", {"base_currency": "CAD"})
    ledger = LedgerService(uow_factory, today=lambda: dt.date(2026, 3, 10))
    bank = await ledger.add_account("alice", "1000", "Bank", "asset")
    food = await ledger.add_account("alice", "5000", "Food", "expense")
    closed = await ledger.add_entry("alice", "2025-11-20", "Lunch", "manual", _legs(food, bank))
    open_ = await ledger.add_entry("alice", "2026-02-01", "Dinner", "manual", _legs(food, bank))
    await ledger.set_lock_date("alice", "2025-12-31")
    return ledger, closed, open_


@pytest.mark.parametrize(
    "statement",
    [
        "update journal_entries set description = 'Edited' where id = :closed",
        "update journal_entries set entry_date = '2026-01-05' where id = :closed",
        "update journal_entries set entry_date = '2025-12-01' where id = :open",
        "update journal_entries set reverses_id = :closed where id = :closed",
        "delete from journal_entries where id = :closed",
        "update postings set fx_rate = 2 where entry_id = :closed",
        "delete from postings where entry_id = :closed",
        "insert into postings (id, entry_id, account_id, direction, amount_minor, currency, "
        "fx_rate, base_amount_minor) select 'p-new', entry_id, account_id, 1, 1, 'CAD', 1, 1 "
        "from postings where entry_id = :closed limit 1",
        "update postings set entry_id = :closed where entry_id = :open",
    ],
)
async def test_the_database_refuses_to_change_closed_books(uow_factory, db, statement):
    _, closed, open_ = await _books(uow_factory)
    engine = create_engine(_sync(db))
    try:
        with (
            pytest.raises(Exception, match="closed up to and including 2025-12-31"),
            engine.begin() as conn,
        ):
            conn.execute(text(statement), {"closed": closed, "open": open_})
        # Nor while someone else's account is erased.
        with pytest.raises(Exception, match="closed up to and including"), engine.begin() as conn:
            conn.execute(text("select set_config('salli.erase_user', 'bob', true)"))
            conn.execute(text("delete from journal_entries where id = :closed"), {"closed": closed})
    finally:
        engine.dispose()
    assert scalar(db, f"select description from journal_entries where id = '{closed}'") == "Lunch"


async def test_open_books_keep_their_entries_too_and_erasure_clears_them(uow_factory, db):
    _, closed, open_ = await _books(uow_factory)
    engine = create_engine(_sync(db))
    try:
        for statement in (
            "update journal_entries set description = 'Supper' where id = :id",
            "update postings set fx_rate = 1 where entry_id = :id",
            "delete from journal_entries where id = :id",
            "delete from postings where entry_id = :id",
        ):
            with (
                pytest.raises(Exception, match="keeps every entry as posted"),
                engine.begin() as conn,
            ):
                conn.execute(text(statement), {"id": open_})
    finally:
        engine.dispose()

    async with uow_factory() as uow:
        counts = await uow.data_portability.delete_all("alice")
    assert counts["journal_entries"] == 2
    assert scalar(db, f"select count(*) from postings where entry_id = '{closed}'") == 0


async def test_a_reversal_is_dated_the_originals_day_unless_its_books_are_closed(uow_factory):
    ledger, closed, open_ = await _books(uow_factory)

    in_open = await ledger.get_entry("alice", await ledger.reverse_entry("alice", open_, "Wrong"))
    in_closed = await ledger.get_entry("alice", await ledger.reverse_entry("alice", closed, "Gift"))

    assert in_open is not None and in_closed is not None
    assert (in_open.entry_date, in_closed.entry_date) == ("2026-02-01", "2026-03-10")
    # Nothing was written on the closed original: its reversal names it.
    original = await ledger.get_entry("alice", closed)
    assert original is not None
    assert (original.reversed_by, original.description) == (in_closed.id, "Lunch")


async def test_closed_postings_keep_their_tags_and_accounts_their_type(uow_factory, db):
    ledger, closed, open_ = await _books(uow_factory)
    food = scalar(db, "select id from accounts where code = '5000'")
    posting = scalar(db, f"select id from postings where entry_id = '{closed}' limit 1")
    later = scalar(db, f"select id from postings where entry_id = '{open_}' limit 1")

    with pytest.raises(BooksLocked):
        await ledger.set_posting_tags("alice", str(posting), {"category": "dining"})
    await ledger.set_posting_tags("alice", str(later), {"category": "dining"})
    with pytest.raises(BooksLocked, match="type and tax role"):
        await ledger.update_account("alice", str(food), "5000", "Food", "asset")
    await ledger.update_account("alice", str(food), "5000", "Meals", "expense")

    async with uow_factory() as uow:
        rows = await uow.audit_log.list("alice")
    assert [(r["action"], r["params"]["change"]) for r in rows] == [("set_lock_date", "set")]


async def test_an_account_netting_to_zero_in_closed_books_still_keeps_its_type(uow_factory, db):
    ledger, closed, _ = await _books(uow_factory)
    await ledger.set_lock_date("alice", None)
    await ledger.reverse_entry("alice", closed, "Wrong")  # dated 2025-11-20, nets to zero
    await ledger.set_lock_date("alice", "2025-12-31")
    food = str(scalar(db, "select id from accounts where code = '5000'"))

    with pytest.raises(BooksLocked, match="type and tax role"):
        await ledger.update_account("alice", food, "5000", "Food", "asset")
    engine = create_engine(_sync(db))
    try:
        with (
            pytest.raises(Exception, match="type and tax role can't change"),
            engine.begin() as conn,
        ):
            conn.execute(text("update accounts set type = 'asset' where id = :id"), {"id": food})
        with engine.begin() as conn:
            conn.execute(text("update accounts set name = 'Meals' where id = :id"), {"id": food})
            conn.execute(text("select set_config('salli.erase_user', 'alice', true)"))
            conn.execute(text("update accounts set tax_role = 'x' where id = :id"), {"id": food})
    finally:
        engine.dispose()


async def test_an_account_holding_a_balance_can_t_be_closed(uow_factory, db):
    ledger, _, _ = await _books(uow_factory)
    food = str(scalar(db, "select id from accounts where code = '5000'"))
    spare = await ledger.add_account("alice", "5100", "Spare", "expense")

    with pytest.raises(AccountNotEmpty, match="80.00 CAD"):
        await ledger.deactivate_account("alice", food)
    await ledger.deactivate_account("alice", spare)
    assert scalar(db, f"select is_active from accounts where id = '{spare}'") is False
