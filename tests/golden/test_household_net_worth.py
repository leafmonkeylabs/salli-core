"""
One net worth for the household (tests/golden/household.py), whichever read
gives it: the MCP overview, the net worth history's latest point (MCP and
REST), FI's snapshot and score, and the reports' balance sheet and net-worth
statement. Each is the baseline's as of the day: balances at the published
rate for it, and the student loan the ledger doesn't hold counted at its
declared principal.

The history was book value: the dollar account at its entries' 0.90 and
0.95 (2,275.00, not 2,150.00 at the published 0.86) and no student loan, so
it said 344,026.47 for the day the overview said 335,901.47.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from benchmark.households import Salli
from salli.application.services.baseline_service import BaselineService
from salli.application.services.fi_service import FiService
from salli.application.services.insights_service import InsightsService
from salli.application.services.ledger_service import LedgerService
from salli.application.services.report_service import ReportService
from tests.golden import household as h

pytestmark = pytest.mark.asyncio


@pytest.fixture
def services() -> SimpleNamespace:
    factory = h.uow().factory()
    today = lambda: h.AS_OF  # noqa: E731
    baselines = BaselineService(factory, fx=h.fx(), today=today)
    ledger = LedgerService(factory, fx=h.fx(), today=today)
    fi = FiService(factory, baselines=baselines, today=today)
    return SimpleNamespace(
        ledger=ledger,
        baseline=baselines,
        insights=InsightsService(factory, today=today, baselines=baselines),
        fi=fi,
        reports=ReportService(ledger, fi, baselines),
    )


async def test_every_read_gives_the_same_net_worth_for_the_day(services):
    salli = Salli("household")  # the MCP tools, on the same books and day
    overview = await salli.call("get_overview")
    history = await salli.call("get_net_worth_history", {"months": 7})
    baseline = await services.baseline.build(h.USER)
    snapshot = await services.fi.build_snapshot(h.USER)
    score = await services.fi.compute_score(h.USER)
    sheet = await services.reports.get_balance_sheet(h.USER)
    statement = await services.reports.get_net_worth_statement(h.USER)

    assert overview["net_worth"] == "335901.47"
    assert baseline.net_worth == Decimal("335901.47")
    latest = history["points"][-1]
    # Was 344,026.47: the dollar account at book (+125.00) and no student
    # loan (+8,000.00).
    assert (latest["month"], latest["net_worth"]) == ("2026-10", "335901.47")
    assert (latest["assets"], latest["liabilities"]) == ("354493.15", "18591.68")
    assert snapshot.total_assets - snapshot.total_liabilities == baseline.net_worth
    assert Decimal(score["net_worth"]) == baseline.net_worth
    assert Decimal(statement["current_net_worth"]) == baseline.net_worth
    # Was 344,026.47 too: the trial balance at book, without the loan.
    assert (sheet["total_assets"], sheet["total_liabilities"], sheet["net_worth"]) == (
        "354493.15",
        "18591.68",
        "335901.47",
    )
    assert {"account_id": None, "code": "", "name": "Student loan", "balance": "8000.00"} in sheet[
        "liabilities"
    ]


async def test_a_month_end_without_a_published_rate_leaves_the_dollars_out_and_says_so(
    services,
):
    history = await services.insights.net_worth(h.USER, months=7)
    by_month = {p["month"]: p for p in history["points"]}

    # The household's rates have only the as-of date's: each earlier month
    # end counts what it can, the student loan included, and says what it
    # left out.
    september = by_month["2026-09"]
    assert september["notes"] == [
        "Dollar account: no published USD rate for 2026-09-30, so it is left out of the "
        "totals in EUR"
    ]
    assert by_month["2026-10"]["notes"] == []
    assert all(p["notes"] for m, p in by_month.items() if m != "2026-10")
