"""
FI's figures for the household ledger (tests/golden/household.py).

Pinned from the FI service as it computes them before the baseline: every
figure here that the reconciliation changes changes on purpose, with a
comment saying why.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace

import pytest

from salli.application.services import fi_service
from salli.application.services.fi_service import FiService
from tests.golden import household as h

pytestmark = pytest.mark.asyncio


class _AsOf(dt.date):
    @classmethod
    def today(cls) -> dt.date:  # type: ignore[override]
        return h.AS_OF


@pytest.fixture
def fi(monkeypatch) -> FiService:
    # The FI service reads the date itself; pin it to the household's as-of.
    monkeypatch.setattr(
        fi_service,
        "datetime",
        SimpleNamespace(date=_AsOf, datetime=dt.datetime, UTC=dt.UTC, timedelta=dt.timedelta),
    )
    return FiService(h.uow().factory())


async def test_the_snapshot(fi):
    snapshot = await fi.build_snapshot(h.USER)

    # Income and expenses: gross amounts by direction since 2025-10-11, over
    # the 8 months from the first entry (the opening balances, 2026-03-31)
    # to today, the partial October included. 28,000 of income counts the
    # salary booked twice in May, whose reversal is ignored.
    assert snapshot.monthly_income == Decimal("3500.00")
    assert snapshot.monthly_expenses == Decimal("1765.44125")
    # Liquid: every asset whose name matches no investment pattern, the flat
    # (300,000) and the brokerage (13,000) among them; the dollar account at
    # the rates its entries recorded (2,275.00).
    assert snapshot.liquid_savings == Decimal("329618.15")
    # Investments: the pension fund, by its name.
    assert snapshot.investments == Decimal("25000.00")
    assert snapshot.total_assets == Decimal("354618.15")
    # Liabilities: the card (691.68) and the car loan's account (9,900.00).
    # The declared student loan (8,000) is not counted at all.
    assert snapshot.total_liabilities == Decimal("10591.68")


async def test_the_score(fi):
    score = await fi.compute_score(h.USER)

    assert score["overall_score"] == "84.96"
    assert score["grade"] == "FI-ready"
    assert score["monthly_surplus"] == "1734.55875"
    assert Decimal(score["savings_rate"]).quantize(Decimal("0.0001")) == Decimal("0.4956")
    assert score["fi_number"] == "529632.375"
    assert score["net_worth"] == "344026.4700"
    assert score["fi_asset_base"] == "344026.4700"
    assert Decimal(score["progress_to_fi"]).quantize(Decimal("0.0001")) == Decimal("0.6496")
    assert Decimal(score["emergency_fund_months"]).quantize(Decimal("0.01")) == Decimal("186.71")
    assert Decimal(score["debt_to_asset"]).quantize(Decimal("0.0001")) == Decimal("0.0299")
    # Whole years, and a date that many years from today.
    assert score["projected_fi_years"] == "5"
    assert score["projected_fi_date"] == "2031-10-11"


async def test_reading_the_score_stores_one(fi):
    """The defect the baseline fixes: a read writes a row."""
    uow = h.uow()
    reader = FiService(uow.factory())
    await reader.get_or_compute_score(h.USER)
    assert len(uow.fi_scores.rows) == 1


async def test_the_projections(fi):
    projections = await fi.get_projections(h.USER)

    assert projections["fi_number"] == "529632.375"
    assert projections["current_portfolio"] == "344026.4700"
    assert (
        projections["fire_year_conservative"],
        projections["fire_year_base"],
        projections["fire_year_growth"],
    ) == (7, 5, 4)
    year_one = projections["points"][1]
    assert (year_one["conservative"], year_one["base"], year_one["growth"]) == (
        "371976.99",
        "379243.22",
        "386642.03",
    )
    assert len(projections["points"]) == 16  # years 0 to 15


async def test_the_surplus_breakdown(fi):
    surplus = await fi.get_surplus_breakdown(h.USER)

    # Netted (the reversals cancel), but always divided by 12 months.
    assert surplus["income_by_source"] == {"Salary": "2000.00"}
    assert surplus["expense_by_category"] == {
        "Rent": "875.00",
        "Groceries": "214.83",
        "Eating out": "37.89",
        "Loan interest": "29.17",
        "Streaming": "7.58",
    }
    assert surplus["expense_by_need"] == {"essential": "1089.83", "discretionary": "45.47"}
    assert surplus["gross_monthly_income"] == "2000.00"
    assert surplus["gross_monthly_expenses"] == "1164.47"
    assert surplus["monthly_surplus"] == "835.53"
    assert surplus["savings_rate"] == "0.42"


async def test_costing_a_purchase(fi):
    impact = await fi.simulate_purchase(
        h.USER, Decimal("2400"), term_months=12, annual_interest_rate=Decimal("0.069")
    )

    assert impact["fi_asset_base_before"] == "344026.47"
    assert impact["monthly_surplus"] == "1734.56"
    assert impact["baseline_months_to_fi"] == 59
    assert impact["emergency_months_before"] == "186.71"
    assert impact["emergency_months_after_cash"] == "185.35"
    cash, instalments = impact["options"]
    assert (cash["months_to_fi"], cash["months_delay"]) == (60, 1)
    assert (instalments["monthly_payment"], instalments["interest_cost"]) == ("207.55", "90.64")
    assert (instalments["months_to_fi"], instalments["months_delay"]) == (60, 1)
    assert impact["data_as_of"] == "2026-10-09"
    assert impact["is_stale"] is False
