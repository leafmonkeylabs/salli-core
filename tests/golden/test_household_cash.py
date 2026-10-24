"""
Insights' cash flow, the cash forecast and safe-to-spend for the household
ledger (tests/golden/household.py).

First pinned from the insights service as it computed them before the
baseline; each figure the reconciliation changed is updated here with a
comment saying why ("was …").
"""

from __future__ import annotations

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.insights_service import InsightsService
from tests.golden import household as h

pytestmark = pytest.mark.asyncio


def _insights() -> InsightsService:
    uow = h.uow()
    today = lambda: h.AS_OF  # noqa: E731
    baselines = BaselineService(uow.factory(), fx=h.fx(), today=today)
    return InsightsService(uow.factory(), today=today, baselines=baselines)


async def test_cash_flow_by_month():
    flow = await _insights().cash_flow(h.USER, months=12)

    rows = {m["month"]: (m["income"], m["expenses"], m["net"]) for m in flow["months"]}
    # Twelve full months before October, then October so far: was the twelve
    # months ending with October, so the first row was 2025-11.
    assert list(rows)[0] == "2025-10"
    assert list(rows)[-1] == "2026-10"
    assert rows["2026-03"] == ("0.00", "0.00", "0.00")
    # Netted per month: May's doubled salary and June's refunded groceries
    # cancel with their reversals. Unchanged.
    assert rows["2026-04"] == ("4000.00", "2020.99", "1979.01")
    assert rows["2026-05"] == ("4000.00", "2051.89", "1948.11")
    assert rows["2026-06"] == ("4000.00", "2029.69", "1970.31")
    assert rows["2026-07"] == ("4000.00", "2057.99", "1942.01")
    assert rows["2026-08"] == ("4000.00", "2021.29", "1978.71")
    assert rows["2026-09"] == ("4000.00", "2040.69", "1959.31")
    assert rows["2026-10"] == ("0.00", "1750.99", "-1750.99")
    # New: the partial month is marked, and so are the months the average is
    # over (the full months from April, the first with income or expenses).
    marks = {m["month"]: (m["complete"], m["observed"]) for m in flow["months"]}
    assert marks["2026-03"] == (True, False)
    assert marks["2026-04"] == (True, True)
    assert marks["2026-10"] == (False, False)
    # New: the average, the baseline's (and FI's) monthly figures: was absent.
    # (24,000 income, 12,222.55 of spending) / 6 months.
    assert flow["average"] == {
        "months_observed": ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"],
        "income": "4000.00",
        "expenses": "2037.09",
        "net": "1962.91",
        "savings_rate": "0.4907",
    }


async def test_the_forecast():
    forecast = await _insights().forecast(h.USER, days=60)

    # Cash: every asset account whose role is cash, and the card. Savings
    # and the dollar account are cash by their role now: was checking and the
    # card only, as the accounts that had paid an expense.
    assert {a["account_id"] for a in forecast["accounts"]} == {"chk", "card", "sav", "usd"}
    # Was 5,851.47: + savings 7,800.00 + the dollar account's 2,500 USD at
    # the published 0.86 for the as-of date (2,150.00).
    assert forecast["today"] == "15801.47"
    # Was 5,777.02 (the same day, the same 74.45 out) and 9,076.59: the 300 a
    # month to savings is now a transfer within cash (+600 over the window).
    assert forecast["lowest"] == "15727.02"
    assert forecast["lowest_date"] == "2026-10-18"
    assert forecast["end_balance"] == "19626.59"
    flows = {(f["date"], f["account_id"], f["description"]): f["amount"] for f in forecast["flows"]}
    assert flows[("2026-10-26", "chk", "Savings")] == "-300.00"
    assert flows[("2026-10-26", "sav", "Savings")] == "300.00"  # was not there
    assert flows[("2026-10-26", "chk", "Brokerage")] == "-500.00"
    assert forecast["notes"] == []
    # New: the rate the total is at, and where it comes from: was no rate
    # (the latest posting's, unsaid).
    assert forecast["fx"] == [
        {"currency": "USD", "rate": "0.86", "source": "ecb", "as_of": "2026-10-09"}
    ]


async def test_safe_to_spend():
    safe = await _insights().safe_to_spend(h.USER)

    # The salary is the next income: was the card payment's card side (money
    # into the card from checking, which never leaves cash), on the 15th.
    assert safe["next_income"] == {
        "date": "2026-10-25",
        "description": "Acme Salary",
        "amount": "4000.00",
        "currency": "EUR",
    }
    assert safe["until"] == "2026-10-25"  # was 2026-10-15
    # Was 15,727.02, scheduled only: the cash accounts, less 74.45 out on the
    # 18th, less 14 days of the everyday spending beyond what is scheduled
    # (rent and the rest are; 206.96 isn't), less a tenth of a usual month's
    # spending (2,037.12) as a cushion.
    assert safe["amount"] == "15316.35"
    assert (safe["everyday_spending"], safe["cushion"], safe["held_for_goals"]) == (
        "206.96",
        "203.71",
        "0.00",
    )
    assert safe["cash_today"] == "15801.47"  # was 5,851.47
    # Was []: the window now reaches the 18th. The card payment, a transfer
    # within cash, isn't committed money.
    assert safe["committed"] == [
        {"date": "2026-10-18", "description": "Bistro Novo", "amount": "-74.45", "currency": "EUR"}
    ]
