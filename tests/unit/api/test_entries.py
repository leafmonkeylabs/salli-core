import pytest

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
