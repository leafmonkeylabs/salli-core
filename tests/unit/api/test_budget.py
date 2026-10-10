"""
Budgets over HTTP.

The routes are typed now, and the hosted apps already read them, so each
response must carry exactly what the budget service returns: the same fields,
with amounts as decimal strings in the base currency's precision.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.application.services.budget_service import BudgetService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from tests.fakes import FakeRecordsUoW
from tests.unit.api.conftest import AUTH

USER = "test-user-1"
JANUARY = {"period_start": "2026-01-01", "period_end": "2026-01-31"}


def _uow(mock_services, base_currency: str = "LKR") -> FakeRecordsUoW:
    uow = FakeRecordsUoW(base_currency)
    # A budget line has to be on one of the user's accounts.
    uow.ledger.accounts = [_account("food", "Groceries", "expense", base_currency)]
    mock_services.budget = BudgetService(lambda: uow)
    return uow


def _account(id: str, name: str, type: str, currency: str = "LKR") -> Account:
    return Account(id=id, user_id=USER, code=id, name=name, type=type, currency=currency)


def _spend(entry_date: str, account_id: str, amount: str, currency: str = "LKR"):
    return StoredJournalEntry(
        id=f"e-{entry_date}",
        user_id=USER,
        entry_date=entry_date,
        description="spend",
        source="manual",
        postings=[
            Posting(
                account_id=account_id,
                direction=Direction.DEBIT,
                amount=Decimal(amount),
                currency=currency,
            ),
            Posting(
                account_id="cash",
                direction=Direction.CREDIT,
                amount=Decimal(amount),
                currency=currency,
            ),
        ],
    )


async def _create(client, lines: list[dict]) -> str:
    r = await client.post("/v1/budget/", json={**JANUARY, "lines": lines}, headers=AUTH)
    assert r.status_code == 201
    return r.json()["id"]


async def test_a_budget_reads_back_as_the_service_returns_it(client, mock_services):
    _uow(mock_services)
    budget_id = await _create(client, [{"account_id": "food", "limit_amount": 25000}])

    r = await client.get(f"/v1/budget/{budget_id}", headers=AUTH)
    assert r.status_code == 200
    budget = r.json()
    assert budget == await mock_services.budget.get_budget(USER, budget_id)
    assert budget["currency"] == "LKR"
    assert budget["lines"] == [{"account_id": "food", "limit_amount": "25000.00"}]

    r = await client.get("/v1/budget/", headers=AUTH)
    assert r.json() == {"budgets": [budget]}


async def test_the_summary_compares_limits_with_spend_in_the_period(client, mock_services):
    uow = _uow(mock_services)
    uow.ledger.accounts = [
        _account("food", "Groceries", "expense"),
        _account("cash", "Cash", "asset"),
        _account("gone", "Gone", "expense"),
    ]
    uow.ledger.entries = [
        _spend("2026-01-10", "food", "1234.50"),
        _spend("2026-02-01", "food", "9"),
    ]
    budget_id = await _create(
        client,
        [
            {"account_id": "food", "limit_amount": 25000},
            {"account_id": "gone", "limit_amount": 100.5},
        ],
    )
    # An account the ledger no longer has still reads back, under its id.
    uow.ledger.accounts.pop()

    r = await client.get(f"/v1/budget/{budget_id}/summary", headers=AUTH)
    assert r.status_code == 200
    summary = r.json()
    assert summary == await mock_services.budget.get_summary(USER, budget_id)
    assert (summary["currency"], summary["total_actual"], summary["total_variance"]) == (
        "LKR",
        "1234.50",
        "23866.00",
    )
    assert summary["lines"] == [
        {
            "account_id": "food",
            "category": "Groceries",
            "limit_amount": "25000.00",
            "actual_amount": "1234.50",
            "variance": "23765.50",
        },
        {
            "account_id": "gone",
            "category": "gone",
            "limit_amount": "100.50",
            "actual_amount": "0.00",
            "variance": "100.50",
        },
    ]


async def test_amounts_keep_the_base_currencys_own_decimals(client, mock_services):
    uow = _uow(mock_services, base_currency="JPY")
    uow.ledger.accounts = [_account("food", "Groceries", "expense", "JPY")]
    uow.ledger.entries = [_spend("2026-01-10", "food", "1500", "JPY")]
    budget_id = await _create(client, [{"account_id": "food", "limit_amount": 30000}])

    summary = (await client.get(f"/v1/budget/{budget_id}/summary", headers=AUTH)).json()
    assert summary["currency"] == "JPY"
    assert summary["lines"][0]["limit_amount"] == "30000"
    assert summary["total_variance"] == "28500"


async def test_an_update_answers_that_it_was_applied(client, mock_services):
    _uow(mock_services)
    budget_id = await _create(client, [{"account_id": "food", "limit_amount": 25000}])

    r = await client.patch(
        f"/v1/budget/{budget_id}",
        json={"lines": [{"account_id": "food", "limit_amount": 30000}]},
        headers=AUTH,
    )
    assert (r.status_code, r.json()) == (200, {"updated": True})
    budget = (await client.get(f"/v1/budget/{budget_id}", headers=AUTH)).json()
    assert budget["lines"] == [{"account_id": "food", "limit_amount": "30000.00"}]


async def test_a_line_on_an_account_that_is_not_yours_is_not_found(client, mock_services):
    uow = _uow(mock_services)

    r = await client.post(
        "/v1/budget/",
        json={**JANUARY, "lines": [{"account_id": "theirs", "limit_amount": 100}]},
        headers=AUTH,
    )

    assert r.status_code == 404
    assert r.json()["detail"] == "Account not found: theirs"
    assert await uow.budgets.list(USER) == []


@pytest.mark.parametrize("path", ["/v1/budget/nope", "/v1/budget/nope/summary"])
async def test_a_missing_budget_is_not_found(client, mock_services, path):
    _uow(mock_services)
    r = await client.get(path, headers=AUTH)
    assert r.status_code == 404
