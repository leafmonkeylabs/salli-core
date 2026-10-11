"""
FI's figures for the household ledger (tests/golden/household.py).

First pinned from the FI service as it computed them before the baseline;
each figure the reconciliation changed is updated here with a comment saying
why ("was …"). FI now reads the baseline: its income and expenses (netted per
month, over the full months observed), its asset split by account role, its
balances at the published rate for the as-of date, and its debts counted once.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.fi_service import FiService
from tests.golden import household as h

pytestmark = pytest.mark.asyncio


def _fi(uow=None) -> FiService:
    uow = uow or h.uow()
    today = lambda: h.AS_OF  # noqa: E731
    baselines = BaselineService(uow.factory(), fx=h.fx(), today=today)
    return FiService(uow.factory(), baselines=baselines, today=today)


@pytest.fixture
def fi() -> FiService:
    return _fi()


async def test_the_snapshot(fi):
    snapshot = await fi.build_snapshot(h.USER)

    # Was 3,500.00: 28,000 over 8 months, gross by direction since 2025-10-11
    # with the partial October counted, the doubled May salary in it. Now
    # netted per month (its reversal cancels it) over the 6 full months from
    # April, the first with income: 24,000 / 6.
    assert snapshot.monthly_income == Decimal("4000.00")
    # Was 1,765.44125 (14,123.53 / 8, the refunded 150 counted, October's
    # 1,750.99 in it): now 12,222.55 / 6.
    assert snapshot.monthly_expenses == Decimal("2037.09")
    # Was 329,618.15, every asset no name pattern matched: the flat (300,000)
    # and the brokerage (13,000) among them, and the dollar account at its
    # entries' rates (2,275.00). Now the cash accounts only: checking
    # 6,543.15, savings 7,800.00, and 2,500 USD at the published 0.86 for
    # the as-of date (2,150.00).
    assert snapshot.liquid_savings == Decimal("16493.15")
    # Was 25,000.00 (the pension fund, by its name): now both accounts whose
    # role is investment, the brokerage's 13,000 too.
    assert snapshot.investments == Decimal("38000.00")
    # Was 354,618.15: the dollar account at 0.86 rather than its entries'
    # 0.90 and 0.95 (-125.00).
    assert snapshot.total_assets == Decimal("354493.15")
    # Was 10,591.68 (the card and the car loan's account): + the declared
    # student loan (8,000), which the ledger doesn't hold. The car loan is
    # counted once, from its account.
    assert snapshot.total_liabilities == Decimal("18591.68")


async def test_the_score(fi):
    score = await fi.compute_score(h.USER)

    # Was 84.96 and "FI-ready": the flat no longer counts towards FI.
    assert score["overall_score"] == "60.08"
    assert score["grade"] == "Strong"
    assert score["monthly_surplus"] == "1962.91"  # was 1,734.55875
    # Was 0.4956.
    assert Decimal(score["savings_rate"]).quantize(Decimal("0.0001")) == Decimal("0.4907")
    # Was 529,632.375: 2,037.09 × 12 / 0.04.
    assert score["fi_number"] == "611127"
    # Was 344,026.47: the 125.00 revaluation and the 8,000 student loan.
    assert score["net_worth"] == "335901.4700"
    # Was 344,026.47: liquid 16,493.15 + investments 38,000 - liabilities
    # 18,591.68 (the flat is owned, but funds no withdrawals).
    assert score["fi_asset_base"] == "35901.4700"
    assert Decimal(score["progress_to_fi"]).quantize(Decimal("0.0001")) == Decimal("0.0587")
    # Was 186.71: the flat was "liquid".
    assert Decimal(score["emergency_fund_months"]).quantize(Decimal("0.01")) == Decimal("8.10")
    assert Decimal(score["debt_to_asset"]).quantize(Decimal("0.0001")) == Decimal("0.0524")
    # Was 5 whole years and the date that many years on (2031-10-11): now
    # the month, from the same walk, and the base is far smaller.
    assert "projected_fi_years" not in score and "projected_fi_date" not in score
    assert (score["projected_fi_months"], score["projected_fi_month"]) == (197, "2043-03")
    assert score["as_of"] == "2026-10-11"


async def test_reading_the_score_stores_nothing():
    """Was: a read stored a row. Only `record_score` writes, and not twice
    for the same inputs."""
    uow = h.uow()
    fi = _fi(uow)
    await fi.compute_score(h.USER)
    assert uow.fi_scores.rows == []
    recorded = await fi.record_score(h.USER)
    await fi.record_score(h.USER)
    assert [r["inputs_hash"] for r in uow.fi_scores.rows] == [recorded["inputs_hash"]]


async def test_the_projections(fi):
    projections = await fi.get_projections(h.USER)

    assert projections["fi_number"] == "611127"  # was 529,632.375
    assert projections["current_portfolio"] == "35901.4700"  # was 344,026.47
    # Was 7, 5 and 4 whole years: now the month in each scenario.
    assert projections["fi_by"] == {
        "conservative": {"months": 233, "month": "2046-03"},
        "base": {"months": 197, "month": "2043-03"},
        "growth": {"months": 171, "month": "2041-01"},
    }
    year_one = projections["points"][1]
    # Was 371,976.99 / 379,243.22 / 386,642.03, from the larger base.
    assert (year_one["conservative"], year_one["base"], year_one["growth"]) == (
        "60398.16",
        "61355.75",
        "62329.39",
    )
    # Was 16 (years 0 to 15): the chart runs on to show the crossing.
    assert len(projections["points"]) == 23


async def test_the_surplus_breakdown(fi):
    surplus = await fi.get_surplus_breakdown(h.USER)

    # Was divided by 12 always: now by the 6 months observed, which it names.
    assert surplus["months_observed"] == [
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
    ]
    assert surplus["income_by_source"] == {"Salary": "4000.00"}  # was 2,000.00
    assert surplus["expense_by_category"] == {
        "Rent": "1500.00",  # was 875.00
        "Groceries": "398.32",  # was 214.83
        "Eating out": "75.78",  # was 37.89
        "Loan interest": "50.00",  # was 29.17
        "Streaming": "12.99",  # was 7.58
    }
    # Was essential 1,089.83 and discretionary 45.47.
    assert surplus["expense_by_need"] == {"essential": "1898.32", "discretionary": "88.77"}
    # The totals are the baseline's (was 2,000.00, 1,164.47, 835.53, 0.42).
    assert surplus["gross_monthly_income"] == "4000.00"
    assert surplus["gross_monthly_expenses"] == "2037.09"
    assert surplus["monthly_surplus"] == "1962.91"
    assert surplus["savings_rate"] == "0.49"


async def test_costing_a_purchase(fi):
    impact = await fi.simulate_purchase(
        h.USER, Decimal("2400"), term_months=12, annual_interest_rate=Decimal("0.069")
    )

    assert impact["fi_asset_base_before"] == "35901.47"  # was 344,026.47
    assert impact["monthly_surplus"] == "1962.91"  # was 1,734.56
    assert impact["baseline_months_to_fi"] == 197  # was 59
    assert impact["emergency_months_before"] == "8.10"  # was 186.71
    assert impact["emergency_months_after_cash"] == "6.92"  # was 185.35
    cash, instalments = impact["options"]
    assert (cash["months_to_fi"], cash["months_delay"]) == (198, 1)  # was (60, 1)
    assert (instalments["monthly_payment"], instalments["interest_cost"]) == ("207.55", "90.64")
    assert (instalments["months_to_fi"], instalments["months_delay"]) == (198, 1)  # was (60, 1)
    assert impact["data_as_of"] == "2026-10-09"
    assert impact["is_stale"] is False
    assert impact["as_of"] == "2026-10-11"


async def test_a_purchase_out_of_bounds_is_refused_whoever_asks(fi):
    """Was checked by the API alone: MCP and the agent passed anything on."""
    for amount, term, rate in (
        (Decimal("-1"), None, Decimal(0)),
        (Decimal("100"), 0, Decimal(0)),
        (Decimal("100"), 601, Decimal(0)),
        (Decimal("100"), 12, Decimal("18")),
        (Decimal("100"), 12, Decimal("-0.01")),
        (Decimal("1E+19"), None, Decimal(0)),
    ):
        with pytest.raises(ValueError):
            await fi.simulate_purchase(h.USER, amount, term_months=term, annual_interest_rate=rate)
