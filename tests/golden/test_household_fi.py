"""
FI's figures for the household ledger (tests/golden/household.py).

First pinned from the FI service as it computed them before the baseline;
each figure the reconciliation changed is updated here with a comment saying
why ("was …"). FI now reads the baseline: its income and expenses (netted per
month, over the full months observed), its asset split by account role, its
balances at the published rate for the as-of date, and its debts counted once.

Phase 1b ("1b: was …"): when FI is reached, and the projections, come from
the baseline's monthly timeline, where cash, investments and debts are kept
apart, instead of a walk that grew the whole asset base at the real return
with the surplus invested. On the timeline, first, the surplus stayed in
cash, which earns nothing, and FI moved four years later (2047-05). Now the
share of each month's regular surplus invested is a planning assumption
(`surplus_invested`), and its placeholder is all of it, the convention FI
projections start from ("surplus invested at the placeholder 100%"): only
the 15,801.47 of cash the household holds today earns nothing; the debts
follow their schedules, and once each is paid off its payment joins the
surplus that is invested. With the share at 0 the 1b figures come back
exactly (`test_with_none_of_the_surplus_invested_...`). What a purchase
costs is a scenario too now (tests/golden/test_household_scenarios.py), so
the purchase costing that was pinned here is gone with the engine's own
walk.
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

    # Was 84.96 and "FI-ready": the flat no longer counts towards FI. Was
    # 60.08: debt is scored by its rates, weighted by balance (pack 3.0.0).
    assert score["overall_score"] == "57.59"
    # Was "Strong": under 50% of the way to FI, the top grades are not given.
    assert score["grade"] == "On track"
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
    # the month, and the base is far smaller.
    assert "projected_fi_years" not in score and "projected_fi_date" not in score
    # 1b: was 197 months (2043-03), the base of 35,901.47 compounding at 4%
    # with 1,962.91 a month invested; then 247 (2047-05), the surplus kept in
    # cash. Now 187 (2042-05): surplus invested at the placeholder 100%.
    #
    # Ten months sooner than the old walk, though both invest the surplus,
    # because the timeline keeps cash, investments and debts apart. Each
    # month the base grows by what is invested and the debts' principal
    # repaid: 2,052.91 at first (1,661.59 of regular surplus, 391.32 of
    # principal), against the old walk's flat 1,962.91, since the surplus
    # already holds 168.68 of the debts' payments (the car loan's interest,
    # the student loan's whole minimum) and the debts charge only 78.68 of
    # interest; 2,131.59 once both are paid off (the car loan in 2029-05, the
    # student loan in 2033-03), their payments freed. And the rest of October
    # (3,459.66, its salary in it) is invested at October's end. Fed those
    # flows, the old walk reaches FI in 185 months; but the 15,801.47 of cash
    # earns nothing, where the old walk compounded the whole base, and that
    # puts it back two months, to 187.
    assert (score["projected_fi_months"], score["projected_fi_month"]) == (187, "2042-05")
    assert score["as_of"] == "2026-10-11"
    # New: six full months observed (April to September), enough to show it.
    assert (score["status"], score["months_observed"]) == ("ok", 6)


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
    # Was 344,026.47; then 35901.4700. 1b: the timeline's as-of point, cash
    # 15,801.47 + investments 38,000 − debts 17,900, in the currency's
    # precision.
    assert projections["current_portfolio"] == "35901.47"
    # Was 7, 5 and 4 whole years: now the month in each scenario.
    # 1b: was 233 (2046-03), 197 (2043-03) and 171 (2041-01); then 260
    # (2048-06), 247 (2047-05) and 231 (2046-01), the surplus kept in cash.
    # Now each is the timeline with its investments, the surplus invested at
    # the placeholder 100% among them, at 2%, 4% and 6% (see the score).
    assert projections["fi_by"] == {
        "conservative": {"months": 220, "month": "2045-02"},
        "base": {"months": 187, "month": "2042-05"},
        "growth": {"months": 165, "month": "2040-07"},
    }
    year_one = projections["points"][1]
    # Was 371,976.99 / 379,243.22 / 386,642.03, from the larger base; then
    # 60,398.16 / 61,355.75 / 62,329.39, the base compounding as one; then
    # 64,928.83 / 65,755.54 / 66,598.47, the surplus kept in cash.
    # Now, surplus invested at the placeholder 100%: the timeline's point at
    # the end of 2027-10, cash 15,801.47 (each month's regular surplus
    # invested, so it stays where it is) less debts 13,082.15, plus the
    # investments. At 4%: 38,000 × (1 + 0.04/12 × 21/31) × (1 + 0.04/12)^12
    # = 39,637.48 (the as-of month's 21 days left, then twelve months), the
    # rest of October's 3,459.66 grown twelve months, 3,600.61, and 1,661.59
    # at each month's end from November, 20,308.72: 63,546.81, so 66,266.13.
    assert (year_one["conservative"], year_one["base"], year_one["growth"]) == (
        "65182.46",
        "66266.13",
        "67369.42",
    )
    # Was 16 (years 0 to 15): the chart runs on to show the crossing.
    # 1b: was 23, then 25 (the conservative crossing in year 22). Now the
    # conservative crossing is in year 19 (220 months), and the chart runs
    # two years past it: surplus invested at the placeholder 100%.
    assert len(projections["points"]) == 22


async def test_with_none_of_the_surplus_invested_fi_is_the_cash_only_timelines():
    """The share at 0 keeps the whole surplus in cash, which earns nothing:
    exactly the figures before the share was an assumption (1b's)."""
    fi = _fi(h.uow(fi_assumptions={"surplus_invested": {"value": "0", "source": "none of it"}}))
    score = await fi.compute_score(h.USER)
    assert (score["projected_fi_months"], score["projected_fi_month"]) == (247, "2047-05")
    assert "surplus_invested" not in score["assumptions"]["placeholders"]
    assert score["assumptions"]["surplus_invested"] == {
        "value": "0",
        "origin": "user",
        "source": "none of it",
        "note": None,
    }
    projections = await fi.get_projections(h.USER)
    assert projections["fi_by"] == {
        "conservative": {"months": 260, "month": "2048-06"},
        "base": {"months": 247, "month": "2047-05"},
        "growth": {"months": 231, "month": "2046-01"},
    }
    year_one = projections["points"][1]
    assert (year_one["conservative"], year_one["base"], year_one["growth"]) == (
        "64928.83",
        "65755.54",
        "66598.47",
    )


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
