"""
Direct coverage for `LedgerService.reverse_entry`.

Entries are immutable, so reversal is the *only* sanctioned way to correct a
posted entry — and until now nothing tested it. Two separate test files each
reimplemented a "mirror" of it to test something else, which meant a real bug in
the actual implementation (tags carried as `list(p.tags)`, which on a dict
yields the keys) sailed straight through the suite.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import StoredJournalEntry
from tests.fakes import FakeProfiles


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
    def __init__(self, ledger):
        self.ledger = ledger
        self.user_profiles = FakeProfiles()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


def _service():
    repo = FakeLedgerRepo()

    @asynccontextmanager
    async def factory():
        yield FakeUoW(repo)

    return LedgerService(factory), repo


async def _post_tagged_expense(svc):
    return await svc.add_entry(
        user_id="u1",
        entry_date="2026-08-01",
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

    reversing_id = await svc.reverse_entry("u1", entry_id)
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

    reversing = repo.entries[await svc.reverse_entry("u1", entry_id)]
    expense_side = next(p for p in reversing.postings if p.account_id == "exp")

    assert expense_side.tags == {"category": "groceries", "need": "essential"}, (
        "the reversal must mirror the original's tags, not its tag axes"
    )


@pytest.mark.asyncio
async def test_reversal_marks_the_original_and_refuses_a_second_one():
    svc, repo = _service()
    entry_id = await _post_tagged_expense(svc)

    reversing_id = await svc.reverse_entry("u1", entry_id)
    assert repo.entries[entry_id].reversed_by == reversing_id

    with pytest.raises(ValueError, match="already reversed"):
        await svc.reverse_entry("u1", entry_id)


@pytest.mark.asyncio
async def test_cannot_reverse_another_users_entry():
    svc, _ = _service()
    entry_id = await _post_tagged_expense(svc)

    with pytest.raises(ValueError, match="not found"):
        await svc.reverse_entry("someone-else", entry_id)
