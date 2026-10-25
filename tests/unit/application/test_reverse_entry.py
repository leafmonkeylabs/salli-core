"""
Direct coverage for `LedgerService.reverse_entry`, and the closed books it respects.

Entries are immutable, so reversal is the *only* sanctioned way to correct a
posted entry — and until now nothing tested it. Two separate test files each
reimplemented a "mirror" of it to test something else, which meant a real bug in
the actual implementation (tags carried as `list(p.tags)`, which on a dict
yields the keys) sailed straight through the suite.
"""

from __future__ import annotations

import datetime as dt
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import BooksLocked, StoredJournalEntry
from tests.fakes import FakeProfiles

TODAY = dt.date(2026, 10, 25)


class FakeLedgerRepo:
    def __init__(self) -> None:
        self.entries: dict[str, StoredJournalEntry] = {}

    async def save_entry(self, user_id, entry):
        entry_id = str(uuid.uuid4())
        self.entries[entry_id] = StoredJournalEntry(
            id=entry_id, user_id=user_id, **entry.model_dump(exclude={"id", "user_id"})
        )
        return entry_id

    async def get_entry_by_id(self, user_id, entry_id):
        row = self.entries.get(entry_id)
        return row if row and row.user_id == user_id else None

    async def set_reversed_by(self, entry_id, reversing_id):
        original = self.entries[entry_id]
        self.entries[entry_id] = original.model_copy(update={"reversed_by": reversing_id})


class FakeUoW:
    def __init__(self, ledger, profiles):
        self.ledger = ledger
        self.user_profiles = profiles

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


def _service():
    repo = FakeLedgerRepo()
    profiles = FakeProfiles()

    @asynccontextmanager
    async def factory():
        yield FakeUoW(repo, profiles)

    return LedgerService(factory, today=lambda: TODAY), repo


async def _post_tagged_expense(svc, entry_date="2026-08-01"):
    return await svc.add_entry(
        user_id="u1",
        entry_date=entry_date,
        description="Weekly groceries",
        source="manual",
        postings_data=[
            {
                "account_id": "exp",
                "direction": 1,
                "amount": Decimal("12500"),
                "currency": "LKR",
                "tags": {"category": "groceries", "need": "essential"},
            },
            {
                "account_id": "bank",
                "direction": -1,
                "amount": Decimal("12500"),
                "currency": "LKR",
            },
        ],
    )


@pytest.mark.asyncio
async def test_reversal_flips_direction_and_balances():
    svc, repo = _service()
    entry_id = await _post_tagged_expense(svc)

    reversing_id = await svc.reverse_entry("u1", entry_id, "Booked twice")
    reversing = repo.entries[reversing_id]

    original = repo.entries[entry_id]
    for before, after in zip(original.postings, reversing.postings, strict=True):
        assert after.direction.value == -before.direction.value
        assert after.amount == before.amount
    # JournalEntry's own validator would have rejected an unbalanced reversal,
    # but assert it explicitly — this is the ledger's core invariant.
    assert sum((p.base_signed for p in reversing.postings), Decimal(0)) == Decimal(0)


@pytest.mark.asyncio
async def test_reversal_carries_the_original_tags():
    """Without this the money nets out but the *classification* does not, so a
    spend-by-category report keeps counting a reversed expense forever."""
    svc, repo = _service()
    entry_id = await _post_tagged_expense(svc)

    reversing = repo.entries[await svc.reverse_entry("u1", entry_id, "Booked twice")]
    expense_side = next(p for p in reversing.postings if p.account_id == "exp")

    assert expense_side.tags == {"category": "groceries", "need": "essential"}, (
        "the reversal must mirror the original's tags, not its tag axes"
    )


@pytest.mark.asyncio
async def test_reversal_marks_the_original_and_refuses_a_second_one():
    svc, repo = _service()
    entry_id = await _post_tagged_expense(svc)

    reversing_id = await svc.reverse_entry("u1", entry_id, "Booked twice")
    assert repo.entries[entry_id].reversed_by == reversing_id

    with pytest.raises(ValueError, match="already reversed"):
        await svc.reverse_entry("u1", entry_id, "Booked twice")


@pytest.mark.asyncio
async def test_cannot_reverse_another_users_entry():
    svc, _ = _service()
    entry_id = await _post_tagged_expense(svc)

    with pytest.raises(ValueError, match="not found"):
        await svc.reverse_entry("someone-else", entry_id, "Not mine")


@pytest.mark.asyncio
async def test_a_reversal_is_dated_today_and_says_why():
    """Dated the day it is made, never the original's (whose period may be
    closed), with its own source and the reason in its description."""
    svc, repo = _service()
    entry_id = await _post_tagged_expense(svc)

    reversing = repo.entries[await svc.reverse_entry("u1", entry_id, "  Booked twice ")]

    assert reversing.entry_date == "2026-10-25"
    assert reversing.source == "reversal"
    assert reversing.description == "Reversal of Weekly groceries: Booked twice"


@pytest.mark.asyncio
async def test_a_reversal_needs_a_reason():
    svc, repo = _service()
    entry_id = await _post_tagged_expense(svc)

    with pytest.raises(ValueError, match="needs a reason"):
        await svc.reverse_entry("u1", entry_id, "   ")
    assert repo.entries[entry_id].reversed_by is None


@pytest.mark.asyncio
async def test_closed_books_refuse_an_entry_on_or_before_the_lock_date():
    svc, repo = _service()
    await svc.set_lock_date("u1", "2026-08-01")
    assert await svc.lock_date("u1") == "2026-08-01"

    for day in ("2026-07-15", "2026-08-01"):
        with pytest.raises(BooksLocked, match="closed up to and including 2026-08-01"):
            await _post_tagged_expense(svc, entry_date=day)
    assert repo.entries == {}
    await _post_tagged_expense(svc, entry_date="2026-08-02")


@pytest.mark.asyncio
async def test_an_entry_in_closed_books_is_corrected_today():
    """The original stays in the closed period; its reversal lands today, so
    the closed books are never changed, and a backdated correction is refused."""
    svc, repo = _service()
    entry_id = await _post_tagged_expense(svc)
    await svc.set_lock_date("u1", "2026-09-30")

    reversing = repo.entries[await svc.reverse_entry("u1", entry_id, "Wrong account")]
    assert reversing.entry_date == "2026-10-25"
    with pytest.raises(BooksLocked):
        await _post_tagged_expense(svc, entry_date="2026-08-01")


@pytest.mark.asyncio
async def test_the_books_close_only_up_to_yesterday_and_open_again():
    svc, _ = _service()
    with pytest.raises(ValueError, match="only up to yesterday"):
        await svc.set_lock_date("u1", "2026-10-25")
    await svc.set_lock_date("u1", "2026-10-24")
    await svc.set_lock_date("u1", None)
    assert await svc.lock_date("u1") is None
