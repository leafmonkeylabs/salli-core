"""Unit tests for LedgerService using in-memory fake repositories."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import Account, Direction, StoredJournalEntry

# ── In-memory fakes ────────────────────────────────────────────────────────────


class FakeLedgerRepo:
    def __init__(self):
        self._accounts: dict[str, Account] = {}
        self._entries: list[StoredJournalEntry] = []

    async def save_account(self, user_id: str, account: Account) -> str:
        self._accounts[account.id] = account
        return account.id

    async def get_accounts(self, user_id: str) -> list[Account]:
        return [a for a in self._accounts.values() if a.user_id == user_id]

    async def save_entry(self, user_id: str, entry) -> str:
        entry_id = str(uuid.uuid4())
        stored = StoredJournalEntry(
            id=entry_id,
            user_id=user_id,
            entry_date=entry.entry_date,
            description=entry.description,
            source=entry.source,
            postings=entry.postings,
        )
        self._entries.append(stored)
        return entry_id

    async def get_entries(
        self,
        user_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[StoredJournalEntry]:
        result = [e for e in self._entries if e.user_id == user_id]
        if from_date:
            result = [e for e in result if e.entry_date >= from_date]
        if to_date:
            result = [e for e in result if e.entry_date <= to_date]
        return result


class FakeTaxComputationRepo:
    async def save(self, user_id: str, computation) -> str:
        return str(uuid.uuid4())

    async def get_latest(self, user_id: str, year: str):
        return None


class FakeUoW:
    def __init__(self, ledger_repo: FakeLedgerRepo, tax_repo: FakeTaxComputationRepo):
        self.ledger = ledger_repo
        self.tax_computations = tax_repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


def make_service() -> tuple[LedgerService, FakeLedgerRepo]:
    repo = FakeLedgerRepo()
    tax_repo = FakeTaxComputationRepo()

    @asynccontextmanager
    async def uow_factory():
        yield FakeUoW(repo, tax_repo)

    return LedgerService(uow_factory), repo


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_and_list_accounts():
    svc, repo = make_service()
    acc_id = await svc.add_account("u1", "1001", "Bank", "asset", "LKR")
    assert acc_id
    accounts = await svc.list_accounts("u1")
    assert len(accounts) == 1
    assert accounts[0].code == "1001"
    assert accounts[0].type == "asset"


@pytest.mark.asyncio
async def test_list_accounts_empty():
    svc, _ = make_service()
    assert await svc.list_accounts("u-nobody") == []


@pytest.mark.asyncio
async def test_add_account_isolates_users():
    svc, _ = make_service()
    await svc.add_account("u1", "1001", "Bank", "asset")
    await svc.add_account("u2", "2001", "Cash", "asset")
    assert len(await svc.list_accounts("u1")) == 1
    assert len(await svc.list_accounts("u2")) == 1


@pytest.mark.asyncio
async def test_add_balanced_entry():
    svc, repo = make_service()
    bank_id = await svc.add_account("u1", "1001", "Bank", "asset")
    income_id = await svc.add_account("u1", "4001", "Salary", "income")

    entry_id = await svc.add_entry(
        user_id="u1",
        entry_date="2025-04-01",
        description="Salary received",
        source="manual",
        postings_data=[
            {
                "account_id": bank_id,
                "direction": Direction.DEBIT,
                "amount": Decimal("100000"),
                "currency": "LKR",
            },
            {
                "account_id": income_id,
                "direction": Direction.CREDIT,
                "amount": Decimal("100000"),
                "currency": "LKR",
            },
        ],
    )
    assert entry_id
    entries = await repo.get_entries("u1")
    assert len(entries) == 1
    assert entries[0].description == "Salary received"


@pytest.mark.asyncio
async def test_add_unbalanced_entry_raises():
    svc, _ = make_service()
    bank_id = await svc.add_account("u1", "1001", "Bank", "asset")
    income_id = await svc.add_account("u1", "4001", "Salary", "income")

    with pytest.raises(Exception):
        await svc.add_entry(
            user_id="u1",
            entry_date="2025-04-01",
            description="Broken entry",
            source="manual",
            postings_data=[
                {
                    "account_id": bank_id,
                    "direction": Direction.DEBIT,
                    "amount": Decimal("100000"),
                    "currency": "LKR",
                },
                {
                    "account_id": income_id,
                    "direction": Direction.CREDIT,
                    "amount": Decimal("99999"),
                    "currency": "LKR",
                },
            ],
        )


@pytest.mark.asyncio
async def test_add_entry_float_amount_raises():
    svc, _ = make_service()
    bank_id = await svc.add_account("u1", "1001", "Bank", "asset")
    income_id = await svc.add_account("u1", "4001", "Salary", "income")

    with pytest.raises(Exception):
        await svc.add_entry(
            user_id="u1",
            entry_date="2025-04-01",
            description="Float disaster",
            source="manual",
            postings_data=[
                {
                    "account_id": bank_id,
                    "direction": Direction.DEBIT,
                    "amount": 100000.0,
                    "currency": "LKR",
                },
                {
                    "account_id": income_id,
                    "direction": Direction.CREDIT,
                    "amount": 100000.0,
                    "currency": "LKR",
                },
            ],
        )


@pytest.mark.asyncio
async def test_trial_balance_sums_to_zero():
    svc, _ = make_service()
    bank_id = await svc.add_account("u1", "1001", "Bank", "asset")
    income_id = await svc.add_account("u1", "4001", "Salary", "income")

    await svc.add_entry(
        "u1",
        "2025-04-01",
        "Salary",
        "manual",
        [
            {
                "account_id": bank_id,
                "direction": Direction.DEBIT,
                "amount": Decimal("500000"),
                "currency": "LKR",
            },
            {
                "account_id": income_id,
                "direction": Direction.CREDIT,
                "amount": Decimal("500000"),
                "currency": "LKR",
            },
        ],
    )

    balances = await svc.get_trial_balance("u1")
    net = sum(balances.values())
    assert net == Decimal(0), f"Trial balance must net to zero, got {net}"


@pytest.mark.asyncio
async def test_trial_balance_date_filter():
    svc, _ = make_service()
    bank_id = await svc.add_account("u1", "1001", "Bank", "asset")
    income_id = await svc.add_account("u1", "4001", "Salary", "income")

    for m in ["01", "03", "06"]:
        await svc.add_entry(
            "u1",
            f"2025-{m}-01",
            f"Month {m}",
            "manual",
            [
                {
                    "account_id": bank_id,
                    "direction": Direction.DEBIT,
                    "amount": Decimal("100000"),
                    "currency": "LKR",
                },
                {
                    "account_id": income_id,
                    "direction": Direction.CREDIT,
                    "amount": Decimal("100000"),
                    "currency": "LKR",
                },
            ],
        )

    # Filter to first quarter only
    q1 = await svc.get_trial_balance("u1", from_date="2025-01-01", to_date="2025-03-31")
    # Two entries in Q1 → bank balance = 200000 debit (+200000), income = 200000 credit (−200000)
    assert q1[bank_id] == Decimal("200000")
    assert q1[income_id] == Decimal("-200000")


@pytest.mark.asyncio
async def test_multi_posting_entry():
    svc, _ = make_service()
    bank_id = await svc.add_account("u1", "1001", "Bank", "asset")
    salary_id = await svc.add_account("u1", "4001", "Salary", "income")
    interest_id = await svc.add_account("u1", "4002", "Interest", "income")

    entry_id = await svc.add_entry(
        "u1",
        "2025-05-01",
        "Salary + interest",
        "manual",
        [
            {
                "account_id": bank_id,
                "direction": Direction.DEBIT,
                "amount": Decimal("110000"),
                "currency": "LKR",
            },
            {
                "account_id": salary_id,
                "direction": Direction.CREDIT,
                "amount": Decimal("100000"),
                "currency": "LKR",
            },
            {
                "account_id": interest_id,
                "direction": Direction.CREDIT,
                "amount": Decimal("10000"),
                "currency": "LKR",
            },
        ],
    )
    assert entry_id
    balances = await svc.get_trial_balance("u1")
    assert sum(balances.values()) == Decimal(0)
