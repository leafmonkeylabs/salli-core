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
                "debit_account_id": "acc-food",
                "credit_account_id": "acc-bank",
                "category": "groceries",
                "confidence": 0.92,
                "dedup_status": "pending",
            }
        ],
    }


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
            "period_start": None,
            "period_end": None,
            "status": "pending",
            "created_at": "2025-05-02T10:00:00+00:00",
        },
        {
            "id": "st-1",
            "bank": "sampath",
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
