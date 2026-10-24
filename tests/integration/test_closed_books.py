"""Closed books against a real database: the service refuses an entry on or
before the lock date, and core_0025's trigger refuses one that comes any
other way, so a filed year can't change behind the service's back."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import BooksLocked, Direction
from tests.integration.pg import _sync, requires_postgres

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
                    "source, created_at) values ('e-back', 'alice', '2025-06-01', "
                    "'Backdated', 'manual', now())"
                )
            )
        with engine.begin() as conn:
            conn.execute(
                text(
                    "insert into journal_entries (id, user_id, entry_date, description, "
                    "source, created_at) values ('e-open', 'alice', '2026-01-01', "
                    "'Open', 'manual', now())"
                )
            )
    finally:
        engine.dispose()

    await ledger.set_lock_date("alice", None)
    await ledger.add_entry("alice", "2025-12-31", "Late", "manual", _legs(food, bank))
