"""
A decision reviewed against what the household's ledger shows happened
(tests/golden/household.py): decided as of 2026-08-11, reviewed on
2026-10-11, compared at the end of September. Every figure worked by hand.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.decision_service import DecisionService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.scenario_service import ScenarioService
from tests.fakes import FakeFx
from tests.golden import household as h

pytestmark = pytest.mark.asyncio

D = Decimal


async def test_a_decision_from_august_reviewed_against_september():
    """Decided as of 2026-08-11 to change nothing, reviewed on 2026-10-11:
    the review compares at the end of September, the last month's end
    before it, the projection with the books as of that day."""
    uow = h.uow()
    fx = FakeFx({("USD", h.BASE, None): (D("0.86"), "ecb")})
    baselines = BaselineService(uow.factory(), fx=fx, today=lambda: h.AS_OF)
    scenarios = ScenarioService(uow.factory(), baselines=baselines)
    decisions = DecisionService(
        uow.factory(),
        scenarios,
        PrincipleService(uow.factory(), scenarios),
        now=lambda: dt.datetime(2026, 10, 11, 9, tzinfo=dt.UTC),
    )
    keep = {"schema": "salli.scenario/1", "label": "Keep as is", "as_of": "2026-08-11"}
    recorded = await decisions.record(
        h.USER,
        {
            "question": "Change anything?",
            "options": [keep],
            "chosen": "Keep as is",
            "reasons": "It works.",
            "review_on": "2026-09-30",
        },
        via={"channel": "api"},
    )
    reviewed = await decisions.review(h.USER, recorded["id"], "It did.")
    c = reviewed["review"]["comparison"]
    assert (c["at"], c["option"], c["terms"]) == ("2026-09-30", "Keep as is", "nominal")
    rows = {r["figure"]: r for r in c["figures"]}
    # What happened, on 2026-09-30. Checking: 3,200.00 opening, six months
    # of salary less rent, the loan, the brokerage and savings (6 × 1,350.00),
    # less the card bills paid May to September (2,431.85) and the dollars
    # bought (475.00): 8,393.15. Savings 6,000 + 6 × 300 = 7,800.00; the
    # dollars 2,500 at 0.86 = 2,150.00; September's card, unpaid, 490.69.
    assert rows["cash"]["actual"] == "17852.46"
    # The brokerage's 10,000 + 6 × 500 and the pension's 25,000.
    assert rows["investments"]["actual"] == "38000.00"
    # The car loan's 12,000 less six payments of 300, and the student loan's 8,000.
    assert rows["owed"]["actual"] == "18200.00"
    # 17,852.46 + 38,000.00 + the flat's 300,000.00 - 18,200.00.
    assert rows["net_worth"]["actual"] == "337652.46"
    # What was projected: as of 2026-08-11, cash was 13,466.20 (checking
    # 4,822.43, savings 7,200.00, dollars 2,150.00, the card's 706.23), and
    # with the whole surplus invested (the placeholder) every month ends
    # there. The household kept far more in cash than that: the difference
    # is the placeholder, which the review makes plain.
    assert rows["cash"]["projected"] == "13466.20"
    assert rows["cash"]["difference"] == "4386.26"
    for row in rows.values():
        assert D(row["difference"]) == D(row["actual"]) - D(row["projected"])
    # Spending in September: rent 1,500.00, the loan's interest 50.00,
    # streaming 12.99, groceries 179.90 and 220.10, eating out 77.70:
    # 2,040.69. Projected: the average of April to July as of August,
    # (2,020.99 + 2,051.89 + 2,029.69 + 2,057.99) / 4 = 2,040.14.
    assert c["spending"] == {
        "months": ["2026-09"],
        "projected": "2040.14",
        "actual": "2040.69",
        "difference": "0.55",
    }
    assert c["is_stale"] is False and c["data_as_of"] == "2026-09-26"
