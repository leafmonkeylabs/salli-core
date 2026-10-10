from decimal import Decimal

import pytest

from salli.domain.accounting.models import Direction, Posting, StoredJournalEntry
from tests.unit.api.conftest import AUTH, make_entry


@pytest.mark.asyncio
async def test_add_entry(client, mock_services):
    mock_services.ledger.add_entry.return_value = "entry-abc"
    payload = {
        "entry_date": "2025-04-01",
        "description": "April salary",
        "postings": [
            {"account_id": "acc-cash", "direction": 1, "amount": "150000", "currency": "LKR"},
            {"account_id": "acc-income", "direction": -1, "amount": "150000", "currency": "LKR"},
        ],
    }
    r = await client.post("/entries/", json=payload, headers=AUTH)
    assert r.status_code == 201
    assert r.json() == {"id": "entry-abc"}


@pytest.mark.asyncio
async def test_add_entry_amounts_are_strings(client, mock_services):
    """Amounts must be passed as strings, not floats."""
    mock_services.ledger.add_entry.return_value = "entry-1"
    payload = {
        "entry_date": "2025-04-01",
        "description": "Test",
        "postings": [
            {"account_id": "a", "direction": 1, "amount": "999.50", "currency": "LKR"},
            {"account_id": "b", "direction": -1, "amount": "999.50", "currency": "LKR"},
        ],
    }
    r = await client.post("/entries/", json=payload, headers=AUTH)
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_list_entries(client, mock_services):
    mock_services.ledger.get_entries.return_value = [make_entry()]
    r = await client.get("/entries/", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["description"] == "Salary"
    # Amounts are serialised as strings — never floats
    assert isinstance(data[0]["postings"][0]["amount"], str)


async def test_an_entry_reads_back_with_amounts_in_their_own_currency(client, mock_services):
    """Each posting's amount has its own currency's decimals, and the rate
    into the base currency rides along as a decimal string."""
    mock_services.ledger.get_entry.return_value = StoredJournalEntry(
        id="e1",
        user_id="u",
        entry_date="2025-04-05",
        description="Dinner in New York",
        source="manual",
        reversed_by="e2",
        postings=[
            Posting(
                id="p1",
                account_id="dining",
                direction=Direction.DEBIT,
                amount=Decimal("12.5"),
                currency="USD",
                fx_rate=Decimal("300.25"),
                tags={"category": "dining"},
            ),
            Posting(
                id="p2",
                account_id="card",
                direction=Direction.CREDIT,
                amount=Decimal("12.5"),
                currency="USD",
                fx_rate=Decimal("300.25"),
            ),
        ],
    )
    r = await client.get("/v1/entries/e1", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {
        "id": "e1",
        "entry_date": "2025-04-05",
        "description": "Dinner in New York",
        "source": "manual",
        "external_ref": None,
        "reversed_by": "e2",
        "postings": [
            {
                "id": "p1",
                "tags": {"category": "dining"},
                "account_id": "dining",
                "direction": 1,
                "amount": "12.50",
                "currency": "USD",
                "fx_rate": "300.25",
            },
            {
                "id": "p2",
                "tags": {},
                "account_id": "card",
                "direction": -1,
                "amount": "12.50",
                "currency": "USD",
                "fx_rate": "300.25",
            },
        ],
    }


async def test_reversing_returns_the_reversal(client, mock_services):
    mock_services.ledger.reverse_entry.return_value = "e2"
    r = await client.post("/v1/entries/e1/reverse", headers=AUTH)
    assert r.status_code == 201
    assert r.json() == {"id": "e2"}


async def test_provenance_of_a_statement_entry(client, mock_services):
    provenance = {
        "entry_id": "e1",
        "entry_date": "2025-04-05",
        "description": "UBER TRIP",
        "source": "statement",
        "external_ref": "txn-1",
        "statement": {
            "parsed_transaction_id": "txn-1",
            "raw_description": "UBER TRIP",
            "raw_amount": "12.50",
            "currency": "USD",
            "raw_date": "2025-04-05",
            "bank_ref": "REF1",
            "statement": {
                "id": "st-1",
                "bank": None,
                "period_start": "2025-04-01",
                "period_end": "2025-04-30",
                "storage_key": "u/st-1/april.csv",
                "status": "pending",
                "created_at": "2025-05-01T09:00:00+00:00",
            },
        },
        "receipt": None,
        "possible_subscriptions": [{"subscription_id": "s1", "name": "Uber One"}],
    }
    mock_services.ledger.get_entry_provenance.return_value = provenance
    r = await client.get("/v1/entries/e1/provenance", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == provenance


async def test_provenance_of_a_manual_entry_with_a_receipt(client, mock_services):
    provenance = {
        "entry_id": "e1",
        "entry_date": "2025-04-05",
        "description": "Groceries",
        "source": "manual",
        "external_ref": "doc-1",
        "statement": None,
        "receipt": {
            "document_id": "doc-1",
            "title": "receipt.jpg",
            "mime_type": "image/jpeg",
            "storage_key": None,
        },
        "possible_subscriptions": [],
    }
    mock_services.ledger.get_entry_provenance.return_value = provenance
    r = await client.get("/v1/entries/e1/provenance", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == provenance
