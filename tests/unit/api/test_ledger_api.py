from decimal import Decimal

import pytest

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from tests.unit.api.conftest import AUTH


@pytest.mark.asyncio
async def test_trial_balance(client, mock_services):
    mock_services.ledger.get_trial_balance.return_value = {
        "acc-1": Decimal("500000"),
        "acc-2": Decimal("-500000"),
    }
    r = await client.get("/ledger/trial-balance", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["currency"] == "LKR"
    assert body["net"] == "0.00"
    assert body["balances"]["acc-1"] == "500000.00"


@pytest.mark.asyncio
async def test_income_statement(client, mock_services):
    bank = Account(id="bank", user_id="u", code="1200", name="Bank", type="asset", currency="LKR")
    salary = Account(
        id="salary", user_id="u", code="4100", name="Salary", type="income", currency="LKR"
    )
    rent = Account(id="rent", user_id="u", code="5100", name="Rent", type="expense", currency="LKR")
    mock_services.ledger.list_accounts.return_value = [bank, salary, rent]
    mock_services.ledger.get_entries.return_value = [
        StoredJournalEntry(
            id="e1",
            user_id="u",
            entry_date="2025-04-05",
            description="Salary",
            source="manual",
            postings=[
                Posting(
                    account_id="bank",
                    direction=Direction.DEBIT,
                    amount=Decimal("150000"),
                    currency="LKR",
                ),
                Posting(
                    account_id="salary",
                    direction=Direction.CREDIT,
                    amount=Decimal("150000"),
                    currency="LKR",
                ),
            ],
        ),
        StoredJournalEntry(
            id="e2",
            user_id="u",
            entry_date="2025-04-10",
            description="Rent",
            source="manual",
            postings=[
                Posting(
                    account_id="rent",
                    direction=Direction.DEBIT,
                    amount=Decimal("30000"),
                    currency="LKR",
                ),
                Posting(
                    account_id="bank",
                    direction=Direction.CREDIT,
                    amount=Decimal("30000"),
                    currency="LKR",
                ),
            ],
        ),
    ]
    r = await client.get(
        "/ledger/income-statement",
        params={"from_date": "2025-04-01", "to_date": "2026-03-31"},
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["currency"] == "LKR"
    assert body["income"]["Salary"] == "150000.00"
    assert body["expenses"]["Rent"] == "30000.00"
    assert body["net_income"] == "120000.00"


async def test_a_quiet_period_still_reads_in_the_currencys_precision(client, mock_services):
    mock_services.ledger.list_accounts.return_value = []
    mock_services.ledger.get_entries.return_value = []
    r = await client.get(
        "/v1/ledger/income-statement",
        params={"from_date": "2025-04-01", "to_date": "2025-04-30"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json() == {
        "from_date": "2025-04-01",
        "to_date": "2025-04-30",
        "currency": "LKR",
        "income": {},
        "expenses": {},
        "total_income": "0.00",
        "total_expenses": "0.00",
        "net_income": "0.00",
        "lines": [],
    }


def _spend(id_: str, account: str, amount: str) -> StoredJournalEntry:
    leg = {"amount": Decimal(amount), "currency": "LKR"}
    return StoredJournalEntry(
        id=id_,
        user_id="u",
        entry_date="2025-04-05",
        description=id_,
        source="manual",
        postings=[
            Posting(account_id=account, direction=Direction.DEBIT, **leg),
            Posting(account_id="bank", direction=Direction.CREDIT, **leg),
        ],
    )


async def test_closed_accounts_and_shared_names_still_add_up(client, mock_services):
    def expense(id_: str, code: str, name: str, active: bool = True) -> Account:
        return Account(
            id=id_,
            user_id="u",
            code=code,
            name=name,
            type="expense",
            currency="LKR",
            is_active=active,
        )

    mock_services.ledger.list_accounts.return_value = [
        expense("rent-a", "5100", "Rent"),
        expense("rent-b", "5110", "Rent"),
        expense("gym", "5200", "Gym", active=False),
    ]
    mock_services.ledger.get_entries.return_value = [
        _spend("e1", "rent-a", "1000"),
        _spend("e2", "rent-b", "500"),
        _spend("e3", "gym", "40"),
    ]
    r = await client.get(
        "/v1/ledger/income-statement",
        params={"from_date": "2025-04-01", "to_date": "2025-04-30"},
        headers=AUTH,
    )
    body = r.json()
    mock_services.ledger.list_accounts.assert_awaited_with("test-user-1", include_inactive=True)
    assert body["expenses"] == {"Rent (5100)": "1000.00", "Rent (5110)": "500.00", "Gym": "40.00"}
    assert (body["total_expenses"], body["net_income"]) == ("1540.00", "-1540.00")
    assert [(line["code"], line["is_active"]) for line in body["lines"]] == [
        ("5100", True),
        ("5110", True),
        ("5200", False),
    ]


async def test_tags_list(client, mock_services):
    from salli.domain.accounting.models import Tag

    mock_services.ledger.list_tags.return_value = [
        Tag(id="t1", user_id="u", slug="groceries", name="Groceries", kind="category"),
        Tag(
            id="t2",
            user_id="u",
            slug="essential",
            name="Needs",
            kind="need",
            color="#2f855a",
            is_system=True,
        ),
    ]
    r = await client.get("/v1/tags/", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {
        "tags": [
            {
                "id": "t1",
                "slug": "groceries",
                "name": "Groceries",
                "kind": "category",
                "color": "",
                "is_system": False,
            },
            {
                "id": "t2",
                "slug": "essential",
                "name": "Needs",
                "kind": "need",
                "color": "#2f855a",
                "is_system": True,
            },
        ]
    }


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
