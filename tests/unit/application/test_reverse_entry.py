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
from salli.domain.accounting.models import Account, BooksLocked, StoredJournalEntry
from tests.fakes import FakeAuditLog, FakeProfiles, FakeTaxReturns

TODAY = dt.date(2026, 10, 25)


class FakeLedgerRepo:
    def __init__(self) -> None:
        self.entries: dict[str, StoredJournalEntry] = {}
        self.accounts: dict[str, Account] = {}
        self.posting_days: dict[str, str] = {}
        self.tags: dict[str, dict[str, str]] = {}

    async def save_entry(self, user_id, entry):
        entry_id = str(uuid.uuid4())
        self.entries[entry_id] = StoredJournalEntry(
            id=entry_id, user_id=user_id, **entry.model_dump(exclude={"id", "user_id"})
        )
        if entry.reverses:
            original = self.entries[entry.reverses]
            self.entries[entry.reverses] = original.model_copy(update={"reversed_by": entry_id})
        return entry_id

    async def get_entry_by_id(self, user_id, entry_id):
        row = self.entries.get(entry_id)
        return row if row and row.user_id == user_id else None

    async def get_account(self, user_id, account_id):
        return self.accounts.get(account_id)

    async def posting_totals(self, user_id, account_ids, to_date=None):
        return [
            (p.account_id, p.currency, p.amount, p.amount)
            for e in self.entries.values()
            if e.user_id == user_id and (to_date is None or e.entry_date <= to_date)
            for p in e.postings
            if p.account_id in account_ids
        ]

    async def update_account(self, user_id, account_id, **fields):
        self.accounts[account_id] = self.accounts[account_id].model_copy(update=fields)

    async def posting_entry_date(self, user_id, posting_id):
        return self.posting_days.get(posting_id)

    async def set_posting_tags(self, user_id, posting_id, tags):
        self.tags[posting_id] = tags


class FakeUoW:
    def __init__(self, ledger, profiles, audit_log):
        self.ledger = ledger
        self.user_profiles = profiles
        self.audit_log = audit_log
        self.tax_returns = FakeTaxReturns()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


def _service():
    repo = FakeLedgerRepo()
    profiles = FakeProfiles()
    audit = FakeAuditLog()

    @asynccontextmanager
    async def factory():
        yield FakeUoW(repo, profiles, audit)

    svc = LedgerService(factory, today=lambda: TODAY)
    svc.audit = audit  # type: ignore[attr-defined]
    return svc, repo


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
async def test_a_reversal_in_open_books_is_dated_the_originals_day_and_says_why():
    """Correcting last month's category corrects last month: the reversal
    lands on the original's day, with its own source and the reason."""
    svc, repo = _service()
    entry_id = await _post_tagged_expense(svc)
    await svc.set_lock_date("u1", "2026-07-31")

    reversing = repo.entries[await svc.reverse_entry("u1", entry_id, "  Booked twice ")]

    assert reversing.entry_date == "2026-08-01"
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
async def test_an_entry_in_closed_books_is_reversed_today():
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


@pytest.mark.asyncio
async def test_an_accounts_type_and_tax_role_freeze_once_it_has_closed_postings():
    svc, repo = _service()
    repo.accounts["exp"] = Account(
        id="exp", user_id="u1", code="5000", name="Groceries", type="expense", currency="LKR"
    )
    await _post_tagged_expense(svc)
    await svc.set_lock_date("u1", "2026-08-31")

    for change in ({"type": "asset"}, {"tax_role": "deduction"}):
        fields = {"code": "5000", "name": "Groceries", "type": "expense", **change}
        with pytest.raises(BooksLocked, match="type and tax role can't change"):
            await svc.update_account("u1", "exp", **fields)  # type: ignore[arg-type]
    await svc.update_account("u1", "exp", code="5001", name="Food", type="expense")
    assert repo.accounts["exp"].name == "Food"

    await svc.set_lock_date("u1", "2026-07-31")
    await svc.update_account("u1", "exp", code="5001", name="Food", type="liability")
    assert repo.accounts["exp"].type == "liability"


@pytest.mark.asyncio
async def test_a_posting_in_closed_books_keeps_its_tags():
    svc, repo = _service()
    repo.posting_days.update({"closed": "2026-08-01", "open": "2026-09-01"})
    await svc.set_lock_date("u1", "2026-08-31")

    with pytest.raises(BooksLocked):
        await svc.set_posting_tags("u1", "closed", {"category": "dining"})
    await svc.set_posting_tags("u1", "open", {"category": "dining"})
    assert repo.tags == {"open": {"category": "dining"}}


@pytest.mark.asyncio
async def test_every_lock_date_change_is_audited():
    svc, _ = _service()
    await svc.set_lock_date("u1", "2026-06-30", client_id="salli-console", via="oauth")
    await svc.set_lock_date("u1", "2026-06-30")  # no change: no row
    await svc.set_lock_date("u1", "2026-08-31", via="session")
    await svc.set_lock_date("u1", "2026-03-31", via="pat")
    await svc.set_lock_date("u1", None, via="session")

    rows = svc.audit.rows  # type: ignore[attr-defined]
    assert [(r["action"], r["decision"]) for r in rows] == [("set_lock_date", "succeeded")] * 4
    assert [r["params"] for r in rows] == [
        {"change": "set", "from": None, "to": "2026-06-30", "via": "oauth"},
        {"change": "later", "from": "2026-06-30", "to": "2026-08-31", "via": "session"},
        {"change": "earlier", "from": "2026-08-31", "to": "2026-03-31", "via": "pat"},
        {"change": "clear", "from": "2026-03-31", "to": None, "via": "session"},
    ]
    assert [r["client_id"] for r in rows] == ["salli-console", None, None, None]
