from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.tax.models import TaxComputation
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


@pytest.mark.asyncio
async def test_list_tax_packs(client, mock_services):
    pack = MagicMock()
    pack.country = "LK"
    pack.year = "2025/26"
    pack.version = "1.0.0"
    pack.period_start = "2025-04-01"
    pack.period_end = "2026-03-31"
    pack.personal_relief = Decimal("1800000")
    pack.filing.return_due = "2026-11-30"
    mock_services.tax.list_packs.return_value = [pack]

    r = await client.get("/tax/packs", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["year"] == "2025/26"
    assert data[0]["personal_relief"] == "1800000"


@pytest.mark.asyncio
async def test_compute_tax(client, mock_services):
    result = TaxComputation(
        pack_country="LK",
        pack_year="2025/26",
        pack_version="1.0.0",
        currency="LKR",
        gross_income=Decimal("3000000"),
        foreign_service_income=Decimal("0"),
        regular_income=Decimal("3000000"),
        personal_relief_applied=Decimal("1800000"),
        qp_deduction=Decimal("0"),
        taxable_income=Decimal("1200000"),
        band_workings=[],
        fsi_tax=Decimal("0"),
        tax_before_credits=Decimal("114000"),
        apit_credit=Decimal("0"),
        ait_credit=Decimal("0"),
        foreign_tax_credit=Decimal("0"),
        total_credits=Decimal("0"),
        tax_payable=Decimal("114000"),
        refund_due=Decimal("0"),
        rounding="none",
    )
    mock_services.tax.compute_tax.return_value = result

    r = await client.post("/tax/compute", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["tax_payable"] == "114000"
    assert body["pack_year"] == "2025/26"


@pytest.mark.asyncio
async def test_latest_tax_none(client, mock_services):
    mock_services.tax.get_latest_computation.return_value = None
    r = await client.get("/tax/latest", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"result": None}


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
