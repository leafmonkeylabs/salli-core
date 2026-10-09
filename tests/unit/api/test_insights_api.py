"""/v1/insights over HTTP."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio


@pytest.fixture
def insights(mock_services):
    mock_services.insights = AsyncMock()
    return mock_services.insights


async def test_cash_flow_takes_a_number_of_months(client, insights):
    insights.cash_flow.return_value = {
        "currency": "USD",
        "months": [
            {
                "month": "2026-10",
                "income": "10.00",
                "expenses": "5.00",
                "net": "5.00",
                "savings_rate": "0.5000",
            }
        ],
    }
    r = await client.get("/v1/insights/cash-flow?months=1", headers=AUTH)
    assert r.status_code == 200 and r.json()["months"][0]["savings_rate"] == "0.5000"
    insights.cash_flow.assert_awaited_once_with("test-user-1", 1)


@pytest.mark.parametrize("months", [0, 121])
async def test_a_window_out_of_range_is_refused(client, insights, months):
    r = await client.get(f"/v1/insights/cash-flow?months={months}", headers=AUTH)
    assert r.status_code == 422
    insights.cash_flow.assert_not_awaited()


async def test_spending_is_by_category_unless_asked_otherwise(client, insights):
    insights.spending.return_value = {"currency": "USD", "by": "need", "months": [], "lines": []}
    r = await client.get("/v1/insights/spending?by=need", headers=AUTH)
    assert r.status_code == 200
    insights.spending.assert_awaited_once_with("test-user-1", 3, "need")
    r = await client.get("/v1/insights/spending?by=merchant", headers=AUTH)
    assert r.status_code == 422


async def test_recurring_payments_say_whether_they_are_tracked(client, insights):
    insights.recurring.return_value = {
        "items": [
            {
                "payee": "Netflix",
                "cadence": "monthly",
                "typical_amount": "15.99",
                "varies": False,
                "currency": "USD",
                "account_id": "tv",
                "occurrences": 4,
                "last_date": "2026-09-30",
                "next_expected": "2026-10-30",
                "examples": ["NETFLIX.COM 866"],
                "tracked": False,
                "subscription_id": None,
            }
        ]
    }
    body = (await client.get("/v1/insights/recurring", headers=AUTH)).json()
    assert body["items"][0]["tracked"] is False
