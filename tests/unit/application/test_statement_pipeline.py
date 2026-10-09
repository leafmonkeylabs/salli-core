"""
The statement import pipeline as a service: the account a statement is for,
and what happens to its rows on the way to review and posting.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import salli.adapters.parsing.llm_classifier as llm_classifier
from salli.application.services.parsing_service import ParsingService
from salli.domain.accounting.models import Account, StoredJournalEntry
from salli.domain.parsing.models import ParsedTransaction, RawRow
from tests.fakes import FakeProfiles

USER = "u1"
FIXTURES = Path(__file__).parents[2] / "fixtures" / "statements"


def _account(id_: str, type_: str, currency: str = "USD", active: bool = True) -> Account:
    return Account(
        id=id_,
        user_id=USER,
        code=id_,
        name=id_.title(),
        type=type_,
        currency=currency,
        is_active=active,
    )


ACCOUNTS = [
    _account("checking", "asset"),
    _account("card", "liability"),
    _account("euros", "asset", currency="EUR"),
    _account("closed", "asset", active=False),
    _account("food", "expense"),
    _account("salary", "income"),
]


class Ledger:
    def __init__(self, accounts: list[Account]) -> None:
        self.accounts = {a.id: a for a in accounts}
        self.entries: list[StoredJournalEntry] = []

    async def get_account(self, user_id: str, account_id: str) -> Account | None:
        return self.accounts.get(account_id)

    async def get_accounts(self, user_id: str, include_inactive: bool = False) -> list[Account]:
        return [a for a in self.accounts.values() if include_inactive or a.is_active]

    async def get_entries(
        self, user_id: str, from_date: str | None = None, to_date: str | None = None
    ) -> list[StoredJournalEntry]:
        return [
            e
            for e in self.entries
            if (from_date is None or e.entry_date >= from_date)
            and (to_date is None or e.entry_date <= to_date)
        ]

    async def save_entry(self, user_id: str, entry: Any) -> str:
        entry_id = f"e{len(self.entries) + 1}"
        self.entries.append(StoredJournalEntry(id=entry_id, user_id=user_id, **entry.model_dump()))
        return entry_id


class Statements:
    def __init__(self) -> None:
        self.statements: dict[str, dict[str, Any]] = {}
        self.rows: dict[str, ParsedTransaction] = {}

    async def save_statement(
        self,
        user_id: str,
        statement_id: str,
        bank: str,
        period_start: str,
        period_end: str,
        transactions: list[ParsedTransaction],
        storage_key: str = "",
        account_id: str | None = None,
    ) -> None:
        self.statements[statement_id] = {
            "id": statement_id,
            "bank": bank,
            "account_id": account_id,
            "period_start": period_start,
            "period_end": period_end,
            "storage_key": storage_key,
        }
        for txn in transactions:
            row_id = str(uuid.uuid4())
            self.rows[row_id] = replace(
                txn, id=row_id, statement_id=statement_id, account_id=account_id or ""
            )

    async def get_by_ids(self, user_id: str, ids: list[str]) -> list[ParsedTransaction]:
        return [replace(self.rows[i]) for i in ids if i in self.rows]

    async def mark_posted(self, transaction_id: str, entry_id: str) -> None:
        self.rows[transaction_id].dedup_status = "posted"


class World:
    def __init__(self, base_currency: str = "LKR") -> None:
        self.ledger = Ledger(ACCOUNTS)
        self.statements = Statements()
        self.user_profiles = FakeProfiles(base_currency)

    @asynccontextmanager
    async def uow(self):
        yield self

    def service(self, **kwargs: Any) -> ParsingService:
        return ParsingService(self.uow, **kwargs)


@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture(autouse=True)
def model(monkeypatch):
    """A stand-in for the model: groceries to food, everything else to salary,
    and the money side on a bank account the statement may not be for."""
    calls: list[list[RawRow]] = []

    async def classify(rows: list[RawRow], accounts: Any, **_: Any) -> list[ParsedTransaction]:
        calls.append(list(rows))
        return [
            ParsedTransaction(
                raw=row,
                debit_account_id="savings" if row.credit_flag else "food",
                credit_account_id="salary" if row.credit_flag else "savings",
                category="groceries",
                confidence=0.9,
            )
            for row in rows
        ]

    monkeypatch.setattr(llm_classifier, "classify_transactions", classify)
    return calls


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# ── The account a statement is for ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("account_id", "message"),
    [
        ("food", "Food is an expense account"),
        ("closed", "No active account 'closed'"),
        ("nowhere", "No active account 'nowhere'"),
    ],
)
async def test_a_statement_is_for_one_of_the_users_money_accounts(world, account_id, message):
    with pytest.raises(ValueError, match=message):
        await world.service().parse_statement(
            USER, "s.csv", _fixture("us_checking.csv"), account_id=account_id, api_key="k"
        )


async def test_the_account_is_the_money_side_and_its_currency_the_default(world):
    # A CSV names no currency: its rows are in the account's (USD), not the
    # user's base currency (LKR).
    result = await world.service().parse_statement(
        USER, "s.csv", _fixture("us_checking.csv"), account_id="checking", api_key="k"
    )

    assert {t.raw.currency for t in result.transactions} == {"USD"}
    for txn in result.transactions:
        assert txn.account_id == "checking"
        if txn.raw.credit_flag:  # money in: the account is debited
            assert (txn.debit_account_id, txn.credit_account_id) == ("checking", "salary")
        else:  # money out: the account is credited
            assert (txn.debit_account_id, txn.credit_account_id) == ("food", "checking")
    (statement,) = world.statements.statements.values()
    assert statement["account_id"] == "checking"


async def test_a_row_in_another_currency_than_the_account_is_skipped(world):
    # The fixture's wire from London is in pounds; the account is in dollars.
    result = await world.service().parse_statement(
        USER, "s.ofx", _fixture("ofx1_checking.ofx"), account_id="checking", api_key="k"
    )

    assert len(result.transactions) == 6
    assert "INCOMING WIRE" not in " ".join(t.raw.description for t in result.transactions)
    assert result.errors == ["Skipped 1 transaction(s) in GBP: Checking is kept in USD"]


async def test_a_currency_that_contradicts_the_account_is_refused(world):
    with pytest.raises(ValueError, match="Euros is kept in EUR, not USD"):
        await world.service().parse_statement(
            USER,
            "s.csv",
            _fixture("us_checking.csv"),
            account_id="euros",
            currency="USD",
            api_key="k",
        )


async def test_without_an_account_rows_are_in_the_base_currency(world):
    result = await world.service().parse_statement(
        USER, "s.csv", _fixture("us_checking.csv"), api_key="k"
    )
    assert {t.raw.currency for t in result.transactions} == {"LKR"}
    assert {t.account_id for t in result.transactions} == {""}
    first = result.transactions[0]
    assert first.raw.amount == Decimal("84.17")
    # Nothing forces a side: both are as the model chose them.
    assert (first.debit_account_id, first.credit_account_id) == ("food", "savings")
