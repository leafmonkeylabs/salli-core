"""
The household (tests/golden/household.py) with its savings account (7,800.00,
300 a month in from checking on the 26th) marked `savings`: cash it keeps,
not cash it spends.

Every figure is set against the household as it is, where the account's role
is cash: what is free to spend and the daily cash forecast lose the 7,800.00,
and nothing else moves. Net worth, FI and the emergency fund count it as they
did, and the monthly timeline's cash holds it beside the daily one.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.fi_service import FiService
from salli.application.services.insights_service import InsightsService
from salli.domain.baseline import Baseline, timelines
from salli.domain.scenarios import engine, schema
from tests.fakes import FakeUoW
from tests.golden import household as h

pytestmark = pytest.mark.asyncio

KEPT = Decimal("7800.00")


def _uow(savings: bool) -> FakeUoW:
    uow = h.uow()
    if savings:
        uow.ledger.accounts = [
            a.model_copy(update={"asset_role": "savings"}) if a.id == "sav" else a
            for a in uow.ledger.accounts
        ]
    return uow


def _baselines(uow: FakeUoW) -> BaselineService:
    return BaselineService(uow.factory(), fx=h.fx(), today=lambda: h.AS_OF)


def _insights(savings: bool) -> InsightsService:
    uow = _uow(savings)
    return InsightsService(uow.factory(), today=lambda: h.AS_OF, baselines=_baselines(uow))


def _fi(savings: bool) -> FiService:
    uow = _uow(savings)
    return FiService(uow.factory(), baselines=_baselines(uow), today=lambda: h.AS_OF)


async def _baseline(savings: bool) -> Baseline:
    return await _baselines(_uow(savings)).build(h.USER)


async def test_savings_are_not_free_until_payday():
    safe = await _insights(savings=True).safe_to_spend(h.USER)

    # Was 15,316.35 and 15,801.47 with savings as cash: the 7,800.00 kept is
    # neither. The low point before the salary on the 25th is 7,800.00 lower
    # too: the 300 to savings goes on the 26th, after it.
    assert safe["amount"] == "7516.35"
    assert safe["cash_today"] == "8001.47"
    assert safe["low_point"] == "7720.06"
    assert safe["until"] == "2026-10-25"


async def test_the_cash_forecast_leaves_savings_out():
    forecast = await _insights(savings=True).forecast(h.USER, days=60)

    assert {a["account_id"] for a in forecast["accounts"]} == {"chk", "card", "usd"}
    assert forecast["today"] == "8001.47"
    assert (forecast["lowest"], forecast["lowest_date"]) == ("7927.02", "2026-10-18")
    # Was 19,626.59: less the 7,800.00, and the two 300.00 moves into savings
    # in the window (the 26th of October and of November) now leave cash.
    assert forecast["end_balance"] == "11226.59"
    flows = {(f["date"], f["account_id"], f["description"]): f["amount"] for f in forecast["flows"]}
    assert flows[("2026-10-26", "chk", "Savings")] == "-300.00"
    assert ("2026-10-26", "sav", "Savings") not in flows


async def test_savings_count_in_net_worth_fi_and_the_emergency_fund():
    cash = await _fi(savings=False).compute_score(h.USER)
    kept = await _fi(savings=True).compute_score(h.USER)

    for key in (
        "net_worth",
        "fi_asset_base",
        "emergency_fund_months",
        "overall_score",
        "projected_fi_month",
    ):
        assert kept[key] == cash[key], key
    assert kept["net_worth"] == "335901.4700"
    assert Decimal(kept["emergency_fund_months"]).quantize(Decimal("0.01")) == Decimal("8.10")
    assert kept["projected_fi_month"] == "2044-08"  # was 2042-05 (test_household_fi.py)


async def test_the_monthly_timeline_holds_savings_beside_the_daily_one():
    cash, kept = await _baseline(savings=False), await _baseline(savings=True)

    assert (kept.savings, kept.cash) == (KEPT, cash.cash - KEPT)
    assert (kept.liquid, kept.net_worth) == (cash.liquid, cash.net_worth)
    saving = next(b for b in kept.balances if b.account_id == "sav")
    assert (saving.role, saving.in_cash) == ("savings", False)
    # The plan counts a move into savings as staying in its cash, so every
    # month-end is the same; the daily timeline's are the 7,800.00 lower.
    assert timelines.monthly(kept, 50).points == timelines.monthly(cash, 50).points
    daily = timelines.daily(kept).month_ends
    assert [v + KEPT for _, v in daily] == [v for _, v in timelines.daily(cash).month_ends]

    # Emergency-fund months count the savings beside the cash timeline: at
    # the year's end as before, 15,801.47 over essential spending.
    nothing = schema.load({"schema": "salli.scenario/1", "changes": []})
    was, now = engine.run(cash, nothing), engine.run(kept, nothing)
    assert now.resilience.at_end.baseline == was.resilience.at_end.baseline
    assert now.cash.safe_to_spend.baseline == Decimal("7516.35")
