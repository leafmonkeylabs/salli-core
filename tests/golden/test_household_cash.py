"""
Insights' cash flow, the cash forecast and safe-to-spend for the household
ledger (tests/golden/household.py).

Pinned from the insights service as it computes them before the baseline:
every figure the reconciliation changes changes on purpose, with a comment
saying why.
"""

from __future__ import annotations

import pytest

from salli.application.services.insights_service import InsightsService
from tests.golden import household as h

pytestmark = pytest.mark.asyncio


def _insights() -> InsightsService:
    return InsightsService(h.uow().factory(), today=lambda: h.AS_OF)


async def test_cash_flow_by_month():
    flow = await _insights().cash_flow(h.USER, months=12)

    rows = {m["month"]: (m["income"], m["expenses"], m["net"]) for m in flow["months"]}
    # Twelve months ending with October; nothing booked before April.
    assert list(rows)[0] == "2025-11"
    assert list(rows)[-1] == "2026-10"
    assert rows["2026-03"] == ("0.00", "0.00", "0.00")
    # Netted per month: May's doubled salary and June's refunded groceries
    # cancel with their reversals.
    assert rows["2026-04"] == ("4000.00", "2020.99", "1979.01")
    assert rows["2026-05"] == ("4000.00", "2051.89", "1948.11")
    assert rows["2026-06"] == ("4000.00", "2029.69", "1970.31")
    assert rows["2026-07"] == ("4000.00", "2057.99", "1942.01")
    assert rows["2026-08"] == ("4000.00", "2021.29", "1978.71")
    assert rows["2026-09"] == ("4000.00", "2040.69", "1959.31")
    # The partial month, side by side with the full ones, and no average.
    assert rows["2026-10"] == ("0.00", "1750.99", "-1750.99")
    assert set(flow) == {"currency", "months"}


async def test_the_forecast():
    forecast = await _insights().forecast(h.USER, days=60)

    # Cash: the accounts that paid an expense (checking, the card). The
    # savings and dollar accounts never did, so they are left out, and a
    # transfer into savings reads as money leaving.
    assert {a["account_id"] for a in forecast["accounts"]} == {"chk", "card"}
    assert forecast["today"] == "5851.47"
    assert forecast["lowest"] == "5777.02"
    assert forecast["lowest_date"] == "2026-10-18"
    assert forecast["end_balance"] == "9076.59"
    flows = {(f["date"], f["account_id"], f["description"]): f["amount"] for f in forecast["flows"]}
    assert flows[("2026-10-26", "chk", "Savings")] == "-300.00"
    assert flows[("2026-10-26", "chk", "Brokerage")] == "-500.00"
    assert forecast["notes"] == []
    assert "fx" not in forecast


async def test_safe_to_spend():
    safe = await _insights().safe_to_spend(h.USER)

    # The card payment's card side (money into the card) is taken for the
    # next income, so safe-to-spend runs only to the 15th.
    assert safe["next_income"] == {
        "date": "2026-10-15",
        "description": "Thank",
        "amount": "479.69",
        "currency": "EUR",
    }
    assert safe["until"] == "2026-10-15"
    assert safe["amount"] == "5851.47"
    assert safe["cash_today"] == "5851.47"
    assert safe["committed"] == []
