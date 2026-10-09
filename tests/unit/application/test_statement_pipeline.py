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


# ── Rows from anywhere: import_rows ───────────────────────────────────────────


class Storage:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, bytes]] = []

    async def upload(self, user_id: str, key: str, data: bytes) -> str:
        self.uploads.append((user_id, key, data))
        return f"stored/{key}"


def _row(
    description: str,
    amount: str,
    money_in: bool = False,
    date: str = "2026-10-05",
    bank_ref: str = "",
    currency: str = "USD",
) -> RawRow:
    return RawRow(
        date=date,
        description=description,
        amount=Decimal(amount),
        credit_flag=money_in,
        currency=currency,
        bank_ref=bank_ref,
    )


async def test_rows_from_a_feed_import_without_a_file(world):
    storage = Storage()
    feed = [
        _row("BLUE BOTTLE COFFEE", "4.50", bank_ref="txn_8f2k"),
        _row("NORTHWIND PAYROLL", "2400.00", money_in=True, date="2026-10-01", bank_ref="txn_8f2m"),
    ]

    result = await world.service(storage=storage).import_rows(
        USER, feed, bank="Example Bank", account_id="checking", api_key="k"
    )

    assert storage.uploads == []  # a feed has no file to keep
    assert (result.period_start, result.period_end) == ("2026-10-01", "2026-10-05")
    assert [t.raw.bank_ref for t in result.transactions] == ["txn_8f2k", "txn_8f2m"]
    (statement,) = world.statements.statements.values()
    assert statement | {"id": "-"} == {
        "id": "-",
        "bank": "Example Bank",
        "account_id": "checking",
        "period_start": "2026-10-01",
        "period_end": "2026-10-05",
        "storage_key": "",
    }


async def test_the_original_file_is_kept(world):
    storage = Storage()
    data = _fixture("us_checking.csv")

    result = await world.service(storage=storage).parse_statement(
        USER, "october.csv", data, account_id="checking", api_key="k"
    )

    assert storage.uploads == [(USER, f"{result.statement_id}/october.csv", data)]
    assert world.statements.statements[result.statement_id]["storage_key"] == (
        f"stored/{result.statement_id}/october.csv"
    )


async def test_nothing_to_import(world):
    result = await world.service().import_rows(USER, [], bank="", account_id=None)
    assert (result.statement_id, result.errors) == ("", ["No transactions to import"])

    result = await world.service().import_rows(
        USER, [_row("HOTEL", "120.00", currency="EUR")], bank="", account_id="checking"
    )
    assert result.errors == [
        "Skipped 1 transaction(s) in EUR: Checking is kept in USD",
        "No transactions to import",
    ]
    assert world.statements.statements == {}


# ── Posting what was approved ─────────────────────────────────────────────────


def _parsed(world: World, row: RawRow, debit: str, credit: str, **fields: Any) -> str:
    """A row as an import leaves it, pending review; its id."""
    row_id = str(uuid.uuid4())
    world.statements.rows[row_id] = ParsedTransaction(
        raw=row, debit_account_id=debit, credit_account_id=credit, id=row_id, **fields
    )
    return row_id


@pytest.fixture
def usd_world() -> World:
    return World(base_currency="USD")


async def test_tags_go_on_the_other_side_never_the_bank_account(usd_world):
    paid = _parsed(
        usd_world,
        _row("KEELLS", "12.00"),
        "food",
        "checking",
        category="groceries",
        need="essential",
        account_id="checking",
    )
    received = _parsed(
        usd_world,
        _row("PAYROLL", "2400.00", money_in=True),
        "checking",
        "salary",
        category="Salary",
        account_id="checking",
    )

    await usd_world.service().post_approved(USER, [paid, received])

    spent, earned = usd_world.ledger.entries
    assert [p.tags for p in spent.postings] == [{"category": "groceries", "need": "essential"}, {}]
    # Money in: the income is the credit, so that is where the tag goes.
    assert [p.tags for p in earned.postings] == [{}, {"category": "salary"}]


async def test_without_a_statement_account_the_income_or_expense_side_is_tagged(usd_world):
    received = _parsed(
        usd_world, _row("PAYROLL", "2400.00", money_in=True), "checking", "salary", category="pay"
    )
    moved = _parsed(usd_world, _row("TO CARD", "50.00"), "card", "checking", category="transfer")

    await usd_world.service().post_approved(USER, [received, moved])

    earned, transfer = usd_world.ledger.entries
    assert [p.tags for p in earned.postings] == [{}, {"category": "pay"}]
    # Neither side is income or expense: the debit, as before.
    assert [p.tags for p in transfer.postings] == [{"category": "transfer"}, {}]


async def test_an_entry_is_booked_with_the_description_it_should_have(usd_world):
    plain = _parsed(usd_world, _row("POS 4821 WHOLEFDS", "84.17"), "food", "checking")
    renamed = _parsed(
        usd_world,
        _row("AMZN MKTP US*2K4LT0", "12.99"),
        "food",
        "checking",
        description="Amazon",
    )

    await usd_world.service().post_approved(USER, [plain, renamed])

    assert [e.description for e in usd_world.ledger.entries] == ["POS 4821 WHOLEFDS", "Amazon"]


async def test_a_row_is_posted_once(usd_world):
    row = _parsed(usd_world, _row("RENT", "1200.00"), "food", "checking")

    first = await usd_world.service().post_approved(USER, [row])
    again = await usd_world.service().post_approved(USER, [row])

    assert (len(first), again) == (1, [])
    assert len(usd_world.ledger.entries) == 1
