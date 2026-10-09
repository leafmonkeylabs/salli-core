"""Statement imports in a real database: the account a statement is for, and
what importing the same file again finds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import salli.adapters.parsing.llm_classifier as llm_classifier
from salli.application.services.ledger_service import LedgerService
from salli.application.services.parsing_service import ParsingService
from salli.domain.parsing.models import ParsedTransaction, RawRow
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

STATEMENT = (Path(__file__).parents[1] / "fixtures" / "statements" / "us_checking.csv").read_bytes()


@pytest.fixture
async def chart(uow_factory) -> dict[str, str]:
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "USD"})
    ledger = LedgerService(uow_factory)
    return {
        "checking": await ledger.add_account("u1", "1000", "Checking", "asset"),
        "food": await ledger.add_account("u1", "5000", "Food", "expense"),
        "salary": await ledger.add_account("u1", "4000", "Salary", "income"),
    }


@pytest.fixture(autouse=True)
def model(monkeypatch, chart):
    async def classify(rows: list[RawRow], accounts: Any, **_: Any) -> list[ParsedTransaction]:
        return [
            ParsedTransaction(
                raw=row,
                debit_account_id="" if row.credit_flag else chart["food"],
                credit_account_id=chart["salary"] if row.credit_flag else "",
                category="groceries",
                confidence=0.9,
            )
            for row in rows
        ]

    monkeypatch.setattr(llm_classifier, "classify_transactions", classify)


async def _rows(uow_factory, statement_id: str) -> list[ParsedTransaction]:
    async with uow_factory() as uow:
        return await uow.statements.get_pending("u1", statement_id)


async def test_an_import_keeps_its_account_and_a_reimport_finds_it(uow_factory, chart):
    parsing = ParsingService(uow_factory)
    checking = chart["checking"]

    first = await parsing.parse_statement(
        "u1", "oct.csv", STATEMENT, account_id=checking, api_key="k"
    )

    async with uow_factory() as uow:
        statement = await uow.statements.get_statement("u1", first.statement_id)
    assert statement is not None and statement["account_id"] == checking
    imported = await _rows(uow_factory, first.statement_id)
    assert len(imported) == 5
    for txn in imported:
        assert txn.account_id == checking
        money_side = txn.debit_account_id if txn.raw.credit_flag else txn.credit_account_id
        assert money_side == checking
        assert (txn.dedup_status, txn.confidence) == ("pending", 0.9)

    # The same file again: every row is a duplicate of the first import's.
    second = await parsing.parse_statement(
        "u1", "oct.csv", STATEMENT, account_id=checking, api_key="k"
    )
    again = await _rows(uow_factory, second.statement_id)
    assert {t.dedup_status for t in again} == {"exact_duplicate"}
    assert sorted(t.duplicate_of for t in again) == sorted(t.id for t in imported)
    assert {t.confidence for t in again} == {0.0}  # nothing decided them, and that reads back

    # The first import posts; its duplicates post nothing.
    assert len(await parsing.post_approved("u1", [t.id for t in imported])) == 5
    assert await parsing.post_approved("u1", [t.id for t in again]) == []

    # A third time still finds the first import, posted or not, and never
    # the second: a duplicate is not history of its own.
    third = await parsing.parse_statement(
        "u1", "oct.csv", STATEMENT, account_id=checking, api_key="k"
    )
    assert sorted(t.duplicate_of for t in await _rows(uow_factory, third.statement_id)) == sorted(
        t.id for t in imported
    )


async def test_another_accounts_history_is_not_a_duplicate(uow_factory, chart):
    ledger = LedgerService(uow_factory)
    savings = await ledger.add_account("u1", "1100", "Savings", "asset")
    parsing = ParsingService(uow_factory)

    await parsing.parse_statement("u1", "oct.csv", STATEMENT, account_id=savings, api_key="k")
    on_checking = await parsing.parse_statement(
        "u1", "oct.csv", STATEMENT, account_id=chart["checking"], api_key="k"
    )

    assert {t.dedup_status for t in await _rows(uow_factory, on_checking.statement_id)} == {
        "pending"
    }
