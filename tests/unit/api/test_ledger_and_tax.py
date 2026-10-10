import dataclasses
import json
import re
from decimal import Decimal
from typing import get_args

import pytest

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.tax.engine import compute
from salli.domain.tax.models import LedgerView, TaxComputation
from salli.domain.tax.packs import registry
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26
from salli.interfaces.api.routers.tax import Rounding
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
async def test_list_tax_packs(client, mock_services):
    # The pack itself rather than a mock of it: a mock left the currency and
    # most of the filing calendar as MagicMock attributes.
    mock_services.tax.list_packs.return_value = [LK_2025_26]

    r = await client.get("/tax/packs", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["year"] == "2025/26"
    # An amount, with its currency and that currency's decimals.
    assert (data[0]["personal_relief"], data[0]["currency"]) == ("1800000.00", "LKR")
    assert data[0]["installments"] == ["08-15", "11-15", "02-15", "05-15"]


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
        # A mode the engine applies; it refuses any other.
        rounding="nearest_rupee",
    )
    mock_services.tax.compute_tax.return_value = result

    r = await client.post("/tax/compute", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["tax_payable"] == "114000.00"
    assert body["pack_year"] == "2025/26"


@pytest.mark.asyncio
async def test_latest_tax_none(client, mock_services):
    mock_services.tax.get_latest_computation.return_value = None
    r = await client.get("/tax/latest", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"result": None}


_AMOUNTS = (
    "gross_income",
    "foreign_service_income",
    "regular_income",
    "personal_relief_applied",
    "qp_deduction",
    "taxable_income",
    "fsi_tax",
    "tax_before_credits",
    "apit_credit",
    "ait_credit",
    "foreign_tax_credit",
    "total_credits",
    "tax_payable",
    "refund_due",
)
_BAND_AMOUNTS = ("from_amount", "to_amount", "taxable_in_band", "tax")
_LKR = re.compile(r"^-?\d+\.\d{2}$")


def _amounts(computation: dict) -> list[str]:
    return [computation[k] for k in _AMOUNTS] + [
        band[k]
        for band in computation["band_workings"]
        for k in _BAND_AMOUNTS
        if band[k] is not None
    ]


def _view(**figures: str) -> LedgerView:
    fields = (
        "total_income",
        "foreign_service_income",
        "apit_withheld",
        "ait_withheld",
        "foreign_tax_paid",
        "qualifying_payments",
    )
    return LedgerView(**{f: Decimal(figures.get(f, "0")) for f in fields})


async def test_computed_amounts_have_the_currencys_decimals(client, mock_services):
    """The qualifying-payment cap is a third of taxable income, so the engine's
    figures carry repeating decimals; the API quotes them at LKR's two."""
    mock_services.tax.compute_tax.return_value = compute(
        _view(total_income="1900000", qualifying_payments="50000"), LK_2025_26
    )
    r = await client.post("/v1/tax/compute", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert (body["qp_deduction"], body["taxable_income"]) == ("33333.33", "66666.67")
    assert all(_LKR.match(a) for a in _amounts(body)), _amounts(body)


async def test_a_stored_computation_reads_back_at_the_currencys_precision(client, mock_services):
    """A stored row keeps the scale the engine's sums had (the exchange rate's
    eight decimals on top of the amount's two), written as the repository
    writes it."""
    computation = compute(
        _view(total_income="3000000.0000000000", apit_withheld="250000.0000000000"),
        LK_2025_26,
    )
    stored = json.loads(json.dumps(dataclasses.asdict(computation), default=str))
    assert stored["gross_income"] == "3000000.0000000000"
    mock_services.tax.get_latest_computation.return_value = stored

    r = await client.get("/v1/tax/latest", headers=AUTH)
    assert r.status_code == 200
    result = r.json()["result"]
    assert (result["gross_income"], result["apit_credit"]) == ("3000000.00", "250000.00")
    assert all(_LKR.match(a) for a in _amounts(result)), _amounts(result)


async def test_a_row_from_before_currency_and_refunds_were_recorded(client, mock_services):
    mock_services.tax.get_latest_computation.return_value = {
        "pack_country": "LK",
        "pack_year": "2025/26",
        "pack_version": "1.0.0",
        "gross_income": "3000000",
        "tax_payable": "114000",
        "band_workings": [],
    }
    r = await client.get("/v1/tax/latest", headers=AUTH)
    assert r.status_code == 200
    result = r.json()["result"]
    assert (result["currency"], result["rounding"]) == ("LKR", "nearest_rupee")
    assert (result["tax_payable"], result["refund_due"]) == ("114000.00", "0.00")


def test_every_pack_rounds_in_a_mode_the_api_describes():
    """`rounding` is a closed set in the contract. A pack with a new mode has to
    extend it, or every computation made with that pack would fail its type."""
    assert {p.rounding for p in registry.list_packs()} <= set(get_args(Rounding))


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
