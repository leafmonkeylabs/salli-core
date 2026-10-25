from decimal import Decimal

import pytest

from salli.domain.accounting.models import (
    AccountNotEmpty,
    BeforeBooksStart,
    BooksLocked,
    Direction,
    Posting,
    StoredJournalEntry,
)
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
        "reverses": None,
        "created_by": None,
        "created_via": None,
        "seq": None,
        "hash": None,
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
    r = await client.post("/v1/entries/e1/reverse", json={"reason": "Booked twice"}, headers=AUTH)
    assert r.status_code == 201
    assert r.json() == {"id": "e2"}
    mock_services.ledger.reverse_entry.assert_awaited_once_with("test-user-1", "e1", "Booked twice")


async def test_reversing_needs_a_reason(client, mock_services):
    r = await client.post("/v1/entries/e1/reverse", json={}, headers=AUTH)
    assert r.status_code == 422
    mock_services.ledger.reverse_entry.assert_not_awaited()


async def test_closed_books_are_a_conflict(client, mock_services):
    mock_services.ledger.reverse_entry.side_effect = BooksLocked("2025-06-30", "2025-12-31")
    r = await client.post("/v1/entries/e1/reverse", json={"reason": "Wrong"}, headers=AUTH)
    assert r.status_code == 409
    assert r.json()["type"] == "/problems/books-locked"
    assert "closed up to and including 2025-12-31" in r.json()["detail"]


async def test_closing_an_account_holding_a_balance_is_a_conflict(client, mock_services):
    mock_services.ledger.deactivate_account.side_effect = AccountNotEmpty("80.00 CAD")
    r = await client.delete("/v1/accounts/a1", headers=AUTH)
    assert r.status_code == 409
    assert r.json()["type"] == "/problems/account-not-empty"


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


@pytest.mark.parametrize("amount", ["abc", "1,000", "NaN", "1e3", 999.5])
async def test_an_amount_that_is_not_a_decimal_string_is_refused(client, mock_services, amount):
    # "abc" used to reach Decimal() in the handler and come back as a 500.
    payload = {
        "entry_date": "2025-04-01",
        "description": "Test",
        "postings": [
            {"account_id": "a", "direction": 1, "amount": amount, "currency": "LKR"},
            {"account_id": "b", "direction": -1, "amount": "999.50", "currency": "LKR"},
        ],
    }
    r = await client.post("/v1/entries/", json=payload, headers=AUTH)
    assert r.status_code == 422
    mock_services.ledger.add_entry.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_pages_entries_with_totals_over_every_match(client, mock_services):
    mock_services.ledger.search_entries.return_value = {
        "entries": [make_entry()],
        "matches": 3,
        "totals": [{"account_type": "income", "currency": "LKR", "net": "-450000.00"}],
        "amounts_in": "LKR",
        "next_cursor": "c2",
    }
    r = await client.get(
        "/entries/search",
        params={"text": "salary", "min_amount": "100", "limit": 1, "cursor": "c1"},
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert [e["description"] for e in body["entries"]] == ["Salary"]
    assert (body["matches"], body["next_cursor"]) == (3, "c2")
    assert body["totals"][0]["net"] == "-450000.00"
    kwargs = mock_services.ledger.search_entries.await_args.kwargs
    assert (kwargs["text"], kwargs["min_amount"], kwargs["limit"]) == ("salary", Decimal(100), 1)

    assert (await client.get("/entries/search?limit=201", headers=AUTH)).status_code == 422
    assert (await client.get("/entries/search?min_amount=1e3", headers=AUTH)).status_code == 422
    mock_services.ledger.search_entries.side_effect = ValueError("That cursor is not one")
    assert (await client.get("/entries/search?cursor=x", headers=AUTH)).status_code == 422


async def test_an_entry_before_the_books_start_is_a_conflict(client, mock_services):
    mock_services.ledger.reverse_entry.side_effect = BeforeBooksStart("2025-03-31", "2025-04-01")
    r = await client.post("/v1/entries/e1/reverse", json={"reason": "Wrong"}, headers=AUTH)
    assert r.status_code == 409
    assert r.json()["type"] == "/problems/before-books-start"
    assert "opening balances" in r.json()["detail"]
