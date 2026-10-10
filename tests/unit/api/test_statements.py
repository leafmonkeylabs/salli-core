"""
Statement import over HTTP: what an upload returns, what is pending review,
and what posting produced.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from salli.domain.parsing.models import ParsedTransaction, ParseResult, RawRow
from tests.unit.api.conftest import AUTH


@pytest.fixture(autouse=True)
def _parsing(mock_services):
    mock_services.parsing = AsyncMock()


def _transaction(
    amount: str = "1234.5",
    currency: str = "LKR",
    debit: str | None = "acc-food",
    category: str | None = "groceries",
    id: str = "txn-1",
) -> ParsedTransaction:
    return ParsedTransaction(
        raw=RawRow(
            date="2025-04-05",
            description="KEELLS SUPER",
            amount=Decimal(amount),
            credit_flag=False,
            currency=currency,
            bank_ref="REF1",
        ),
        debit_account_id=debit,  # type: ignore[arg-type]  # the classifier's JSON may hold null
        credit_account_id="acc-bank",
        category=category,  # type: ignore[arg-type]
        confidence=0.92,
        dedup_status="pending",
        id=id,
    )


async def test_an_upload_returns_its_transactions_for_review(client, mock_services):
    mock_services.parsing.parse_statement.return_value = ParseResult(
        statement_id="st-1",
        bank="sampath",
        period_start="2025-04-01",
        period_end="2025-04-30",
        transactions=[_transaction()],
        raw_rows=[_transaction().raw],
    )
    r = await client.post(
        "/v1/statements/upload",
        files={"file": ("april.csv", b"date,description,amount\n", "text/csv")},
        params={"bank": "sampath"},
        headers=AUTH,
    )
    assert r.status_code == 202
    assert r.json() == {
        "statement_id": "st-1",
        "bank": "sampath",
        "period_start": "2025-04-01",
        "period_end": "2025-04-30",
        "total_rows": 1,
        "parsed": 1,
        "errors": [],
        "transactions": [
            {
                "id": "txn-1",
                "date": "2025-04-05",
                "description": "KEELLS SUPER",
                # The statement's figure, at its currency's two decimals.
                "amount": "1234.50",
                "credit_flag": False,
                "bank_ref": "REF1",
                "currency": "LKR",
                "account_id": None,
                "debit_account_id": "acc-food",
                "credit_account_id": "acc-bank",
                "category": "groceries",
                "need": None,
                "rule_id": None,
                "description_override": None,
                "confidence": 0.92,
                "dedup_status": "pending",
                "duplicate_of": None,
            }
        ],
    }


async def test_what_rules_and_dedup_decided_comes_back_for_review(client, mock_services):
    decided = _transaction(id="txn-2")
    decided.account_id = "acc-bank"
    decided.rule_id, decided.need, decided.description = "rule-1", "essential", "Keells"
    repeated = _transaction(id="txn-3")
    repeated.dedup_status, repeated.duplicate_of = "exact_duplicate", "txn-0"
    mock_services.parsing.get_statement.return_value = {"id": "st-1"}
    mock_services.parsing.get_pending.return_value = [decided, repeated]

    r = await client.get("/v1/statements/st-1", headers=AUTH)

    first, second = r.json()["transactions"]
    assert {k: first[k] for k in ("account_id", "rule_id", "need", "description_override")} == {
        "account_id": "acc-bank",
        "rule_id": "rule-1",
        "need": "essential",
        "description_override": "Keells",
    }
    assert first["description"] == "KEELLS SUPER"  # the bank's, as it was
    assert (second["dedup_status"], second["duplicate_of"]) == ("exact_duplicate", "txn-0")


async def test_an_upload_names_the_account_the_statement_is_for(client, mock_services):
    mock_services.parsing.parse_statement.return_value = ParseResult(
        statement_id="st-1",
        bank="",
        period_start="2025-04-05",
        period_end="2025-04-05",
        transactions=[_transaction()],
        raw_rows=[_transaction().raw],
    )
    r = await client.post(
        "/v1/statements/upload",
        files={"file": ("april.csv", b"date,description,amount\n", "text/csv")},
        params={"account_id": "acc-bank"},
        headers=AUTH,
    )
    assert r.status_code == 202
    assert mock_services.parsing.parse_statement.await_args.kwargs["account_id"] == "acc-bank"


async def test_pending_transactions_may_be_unclassified(client, mock_services):
    """The classifier's output is the model's JSON: an account or a category
    it could not decide can come back null, and still has to be reviewable."""
    mock_services.parsing.get_pending.return_value = [
        _transaction(amount="1500", currency="JPY", debit=None, category=None)
    ]
    r = await client.get("/v1/statements/st-1", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["statement_id"] == "st-1"
    (txn,) = body["transactions"]
    assert (txn["amount"], txn["currency"]) == ("1500", "JPY")
    assert (txn["debit_account_id"], txn["category"]) == (None, None)


async def test_statements_list(client, mock_services):
    statements = [
        {
            "id": "st-2",
            "bank": None,
            "account_id": "acc-bank",
            "period_start": None,
            "period_end": None,
            "status": "pending",
            "created_at": "2025-05-02T10:00:00+00:00",
        },
        {
            "id": "st-1",
            "bank": "sampath",
            "account_id": None,
            "period_start": "2025-04-01",
            "period_end": "2025-04-30",
            "status": "pending",
            "created_at": "2025-05-01T10:00:00+00:00",
        },
    ]
    mock_services.parsing.list_statements.return_value = statements
    r = await client.get("/v1/statements/", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"statements": statements}


async def test_posting_reports_the_entries_it_made(client, mock_services):
    mock_services.parsing.post_approved.return_value = ["e1", "e2"]
    r = await client.post(
        "/v1/statements/st-1/post", json={"approved_ids": ["txn-1", "txn-2"]}, headers=AUTH
    )
    assert r.status_code == 200
    assert r.json() == {"posted": 2, "entry_ids": ["e1", "e2"]}


async def test_a_statements_own_pending_transactions(client, mock_services):
    mock_services.parsing.get_statement.return_value = {"id": "st-1"}
    mock_services.parsing.get_pending.return_value = [_transaction()]

    r = await client.get("/v1/statements/st-1", headers=AUTH)

    assert r.status_code == 200
    assert [t["id"] for t in r.json()["transactions"]] == ["txn-1"]
    mock_services.parsing.get_pending.assert_awaited_once_with("test-user-1", "st-1")


async def test_a_statement_that_is_not_yours_is_not_found(client, mock_services):
    mock_services.parsing.get_statement.return_value = None

    r = await client.get("/v1/statements/st-9", headers=AUTH)

    assert r.status_code == 404
    mock_services.parsing.get_pending.assert_not_awaited()


async def test_discarding_some_or_every_pending_transaction(client, mock_services):
    mock_services.parsing.discard.return_value = 2

    r = await client.post(
        "/v1/statements/st-1/discard", json={"ids": ["txn-1", "txn-2"]}, headers=AUTH
    )
    assert (r.status_code, r.json()) == (200, {"discarded": 2})
    mock_services.parsing.discard.assert_awaited_with("test-user-1", "st-1", ["txn-1", "txn-2"])

    # Without ids, the statement's every pending transaction.
    r = await client.post("/v1/statements/st-1/discard", headers=AUTH)
    assert r.status_code == 200
    mock_services.parsing.discard.assert_awaited_with("test-user-1", "st-1", None)


async def test_discarding_in_a_statement_that_is_not_yours(client, mock_services):
    mock_services.parsing.discard.return_value = None
    r = await client.post("/v1/statements/st-9/discard", json={}, headers=AUTH)
    assert r.status_code == 404


async def test_choices_are_handed_over_and_a_bad_need_is_refused(client, mock_services):
    mock_services.parsing.categorize.return_value = ["t1"]
    r = await client.post(
        "/v1/statements/categorize",
        json={"choices": [{"transaction_id": "t1", "account_id": "food", "need": "essential"}]},
        headers=AUTH,
    )
    assert (r.status_code, r.json()) == (200, {"updated": ["t1"]})
    mock_services.parsing.categorize.assert_awaited_once_with(
        "test-user-1", [{"transaction_id": "t1", "account_id": "food", "need": "essential"}]
    )
    bad = await client.post(
        "/v1/statements/categorize",
        json={"choices": [{"transaction_id": "t1", "account_id": "food", "need": "wants"}]},
        headers=AUTH,
    )
    assert bad.status_code == 422
