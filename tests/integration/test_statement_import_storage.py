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
    again = second.transactions
    assert {t.dedup_status for t in again} == {"exact_duplicate"}
    assert sorted(t.duplicate_of for t in again) == sorted(t.id for t in imported)
    assert {t.confidence for t in again} == {0.0}  # nothing decided them
    # Said once, in the import's result; nothing for anyone to review.
    assert await _rows(uow_factory, second.statement_id) == []

    # The first import posts; its duplicates post nothing.
    assert len(await parsing.post_approved("u1", [t.id for t in imported])) == 5
    assert await parsing.post_approved("u1", [t.id for t in again]) == []

    # A third time still finds the first import, posted or not, and never
    # the second: a duplicate is not history of its own.
    third = await parsing.parse_statement(
        "u1", "oct.csv", STATEMENT, account_id=checking, api_key="k"
    )
    assert sorted(t.duplicate_of for t in third.transactions) == sorted(t.id for t in imported)


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


async def test_discarded_rows_leave_review_and_history(uow_factory, chart):
    parsing = ParsingService(uow_factory)
    first = await parsing.parse_statement(
        "u1", "oct.csv", STATEMENT, account_id=chart["checking"], api_key="k"
    )
    ids = [t.id for t in first.transactions]
    # The upload hands back the ids its rows were stored under.
    assert sorted(ids) == sorted(t.id for t in await _rows(uow_factory, first.statement_id))

    assert await parsing.discard("u2", first.statement_id) is None  # not theirs
    assert await parsing.discard("u1", first.statement_id, ids[:1]) == 1
    assert len(await _rows(uow_factory, first.statement_id)) == 4
    assert await parsing.post_approved("u1", ids[:1]) == []
    assert await parsing.discard("u1", first.statement_id) == 4
    assert await parsing.get_pending("u1") == []

    # What was discarded stays gone in a statement that overlaps it...
    overlapping = await parsing.parse_statement(
        "u1", "oct.csv", STATEMENT, account_id=chart["checking"], api_key="k"
    )
    assert {t.dedup_status for t in overlapping.transactions} == {"exact_duplicate"}

    # ...unless the statement is imported again on purpose, replacing the
    # import it was discarded from: then it is all new, and that import's
    # rows still in review are discarded.
    again = await parsing.parse_statement(
        "u1",
        "oct.csv",
        STATEMENT,
        account_id=chart["checking"],
        api_key="k",
        replaces=first.statement_id,
    )
    assert {t.dedup_status for t in again.transactions} == {"pending"}


async def test_a_choice_is_stored_and_posted_as_chosen(uow_factory, chart):
    # What an AI client sorts over MCP, or a person in the CLI, books as chosen.
    ledger = LedgerService(uow_factory)
    transport = await ledger.add_account("u1", "5100", "Transport", "expense")
    parsing = ParsingService(uow_factory)
    imported = await parsing.parse_statement(
        "u1", "oct.csv", STATEMENT, account_id=chart["checking"], api_key="k"
    )
    target = next(t for t in imported.transactions if not t.raw.credit_flag)

    assert await parsing.categorize(
        "u1", [{"transaction_id": target.id, "account_id": transport, "need": "essential"}]
    ) == [target.id]
    [stored] = [t for t in await parsing.get_pending("u1") if t.id == target.id]
    assert (stored.debit_account_id, stored.credit_account_id) == (transport, chart["checking"])
    assert (stored.need, stored.confidence) == ("essential", 1.0)

    [entry_id] = await parsing.post_approved("u1", [target.id])
    async with uow_factory() as uow:
        [entry] = [e for e in await uow.ledger.get_entries("u1") if e.id == entry_id]
    assert {p.account_id for p in entry.postings} == {transport, chart["checking"]}


async def test_two_approvals_at_once_post_each_row_once(uow_factory, chart):
    import asyncio

    parsing = ParsingService(uow_factory)
    first = await parsing.parse_statement(
        "u1", "oct.csv", STATEMENT, account_id=chart["checking"], api_key="k"
    )
    ids = [t.id for t in first.transactions]
    posted = await asyncio.gather(
        parsing.post_approved("u1", ids), parsing.post_approved("u1", ids)
    )
    assert sorted(len(p) for p in posted) == [0, 5]
    entries = await LedgerService(uow_factory).get_entries("u1")
    assert len(entries) == 5


async def test_history_is_read_for_the_statements_account_in_sql(uow_factory, chart):
    ledger = LedgerService(uow_factory)
    savings = await ledger.add_account("u1", "1100", "Savings", "asset")
    parsing = ParsingService(uow_factory)
    on_savings = await parsing.parse_statement(
        "u1", "oct.csv", STATEMENT, account_id=savings, api_key="k"
    )
    unnamed = await parsing.parse_statement("u1", "oct.csv", STATEMENT, api_key="k")

    async with uow_factory() as uow:
        rows = await uow.statements.imported_between(
            "u1", "2026-10-01", "2026-10-31", account_id=chart["checking"]
        )
        replaced = await uow.statements.imported_between(
            "u1", "2026-10-01", "2026-10-31", excluding_statement=on_savings.statement_id
        )
    # Not savings' rows; the account-less statement's may be on any account.
    assert {t.statement_id for t in rows} == {unnamed.statement_id}
    assert on_savings.statement_id not in {t.statement_id for t in replaced}


async def test_the_data_export_carries_statements_and_their_rows(uow_factory, chart):
    parsing = ParsingService(uow_factory)
    first = await parsing.parse_statement(
        "u1", "oct.csv", STATEMENT, account_id=chart["checking"], api_key="k"
    )
    await parsing.discard("u1", first.statement_id)
    async with uow_factory() as uow:
        [statement] = await uow.statements.export("u1")
    assert statement["id"] == first.statement_id
    assert {t.dedup_status for t in statement["transactions"]} == {"discarded"}
    assert len(statement["transactions"]) == 5
