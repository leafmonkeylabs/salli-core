"""
Hand-worked decisions on the household ledger (tests/golden/household.py):
the figures a principle reads, and what an option projects month by month
(a review of one is tests/golden/test_household_decision_review.py).

The household as of Sunday 2026-10-11, in euros (see
tests/golden/test_household_scenarios.py for where each figure comes from):
cash 15,801.47, its lowest 13,998.91 on 2027-02-24; essential spending
1,898.32 a month; a car loan at 5.9% (9,900.00 owed) and a student loan at
4.5% (8,000.00, the last paid off, in 2033-03); FI in 187 months
(2042-05); the share of the surplus invested is the placeholder, all of it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.domain.baseline import Baseline
from salli.domain.decisions import figures as figure_set
from salli.domain.decisions import projection
from salli.domain.scenarios import engine, schema, views
from tests.golden import household as h

pytestmark = pytest.mark.asyncio

D = Decimal


async def _baseline(**profile: object) -> Baseline:
    uow = h.uow(**profile)
    return await BaselineService(uow.factory(), fx=h.fx(), today=lambda: h.AS_OF).build(h.USER)


def scenario(*changes: dict[str, object], label: str = "Option") -> schema.Scenario:
    return schema.load({"schema": "salli.scenario/1", "label": label, "changes": list(changes)})


def figures_of(baseline: Baseline, option: schema.Scenario | None = None) -> figure_set.Figures:
    base = engine.baseline_outlook(baseline)
    if option is None:
        return figure_set.compute(baseline, base, base)
    _, evaluated = engine.run_with_outlook(baseline, option, base=base)
    return figure_set.compute(
        baseline, evaluated.outlook, base, evaluated.translation.changes.loans
    )


LAPTOP = {"type": "one_off", "date": "2026-11-02", "amount": "-2400.00", "account": "chk",
          "label": "Laptop"}  # fmt: skip
LOAN = {"type": "loan", "principal": "2400.00", "annual_rate": "0.069", "term_months": 12,
        "start": "2026-11-02", "into": "chk", "label": "Instalments"}  # fmt: skip


async def test_the_baselines_figures_by_hand():
    values = figures_of(await _baseline()).values
    assert values["lowest_cash"] == D("13998.91")
    # 13,998.91 / 1,898.32 of essential spending a month = 7.374…
    assert (values["monthly_spending"], values["emergency_months"]) == (D("1898.32"), D("7.37"))
    # Every month ends where today does: the whole surplus is invested.
    assert values["cash_in_12_months"] == D("15801.47")
    assert values["emergency_months_in_12_months"] == D("8.32")  # 15,801.47 / 1,898.32
    # The student loan, the last paid off, in 2033-03: 6 years and 5 months on.
    assert values["debt_free_months"] == D(77)
    # The car loan is the dearer of the two; and with all the surplus
    # invested every month, it is owed while money is invested.
    assert values["max_debt_rate"] == D("0.059")
    assert values["max_debt_rate_while_investing"] == D("0.059")
    assert values["borrowed"] == D("0.00")
    assert (values["fi_months"], values["fi_months_gained"]) == (D(187), D(0))
    assert values["any_account_below_zero"] is False


async def test_debt_owed_while_investing_follows_what_is_invested():
    """With none of the surplus invested, nothing is invested while the
    loans are owed; a lump sum invested in December is, while the car loan
    is owed; one invested in 2034, after both are paid off, isn't."""
    kept = await _baseline(
        fi_assumptions={"surplus_invested": {"value": "0", "source": "kept in cash"}}
    )
    assert figures_of(kept).values["max_debt_rate_while_investing"] == D(0)
    assert figures_of(kept).values["max_debt_rate"] == D("0.059")
    invest = {"type": "invest", "amount": "5000.00", "label": "Bonus"}
    december = figures_of(kept, scenario({**invest, "date": "2026-12-15"}))
    later = figures_of(kept, scenario({**invest, "date": "2034-01-15"}))
    assert december.values["max_debt_rate_while_investing"] == D("0.059")
    assert later.values["max_debt_rate_while_investing"] == D(0)


async def test_a_loans_rate_and_what_it_borrows():
    values = figures_of(await _baseline(), scenario(LAPTOP, LOAN)).values
    assert values["borrowed"] == D("2400.00")
    assert values["max_debt_rate"] == D("0.069")
    # Eleven payments of 207.55 and a last of 207.63 cost 90.68 of interest,
    # on top of the baseline's 2,009.25.
    assert values["total_interest"] == D("2099.93")


async def test_an_options_figures_are_the_ones_its_scenario_result_shows():
    """A check reads exactly what the person reads in run_scenario."""
    baseline = await _baseline()
    option = scenario(LAPTOP, LOAN, label="Instalments")
    shown = views.result_view(engine.run(baseline, option))
    values = figure_set.view(figures_of(baseline, option))
    assert values["lowest_cash"] == shown["cash"]["lowest"]["scenario"]
    assert values["cash_in_12_months"] == shown["cash"]["at_end"]["scenario"]
    assert values["safe_to_spend"] == shown["cash"]["safe_to_spend"]["scenario"]
    assert values["emergency_months"] == shown["resilience"]["lowest"]["scenario"]
    assert values["monthly_spending"] == shown["resilience"]["monthly_spending"]
    for point in shown["monthly"]:
        for name in ("net_worth", "cash", "investments", "debts"):
            assert values[f"{name}_{point['years']}y"] == point[name]["scenario"]
    assert values["total_interest"] == shown["debts"]["total_interest"]["scenario"]
    assert values["fi_number"] == shown["fi"]["fi_number"]["scenario"]
    assert values["fi_months_gained"] == shown["fi"]["months_gained"]
    assert values["debt_free_months"] == projection.months_to(
        "2026-10", shown["debts"]["debt_free"]["scenario"]
    )


async def test_an_options_projection_month_by_month():
    baseline = await _baseline()
    option = scenario(
        LAPTOP,
        {
            "type": "recurring",
            "amount": "-450.00",
            "cadence": "monthly",
            "start": "2027-01-01",
            "label": "New flat",
        },  # fmt: skip
    )
    _, evaluated = engine.run_with_outlook(baseline, option)
    points = projection.projection(baseline, option, evaluated.outlook, 4)
    # The as-of point: 15,801.47 + 38,000.00 + the flat's 300,000.00, less
    # the loans' 9,900.00 and 8,000.00.
    assert points[0] == {
        "month": "2026-10",
        "date": "2026-10-11",
        "cash": "15801.47",
        "investments": "38000.00",
        "owed": "17900.00",
        "net_worth": "335901.47",
        "spending": None,
    }
    # The laptop leaves cash for good (the surplus is invested, so nothing
    # rebuilds it): 15,801.47 - 2,400.00 from November on.
    assert [p["cash"] for p in points[1:]] == ["15801.47", "13401.47", "13401.47", "13401.47"]
    # Spending: the household's 2,037.09 a month on average, and from
    # January the new flat's 450.00 on top.
    assert [p["spending"] for p in points] == [None, None, "2037.09", "2037.09", "2487.09"]


async def test_a_stopped_payment_comes_off_the_projected_spending():
    baseline = await _baseline()
    option = scenario({"type": "stop_recurring", "key": "streamflix", "from": "2026-12-01"})
    _, evaluated = engine.run_with_outlook(baseline, option)
    points = projection.projection(baseline, option, evaluated.outlook, 4)
    # 12.99 a month less from December: 2,037.09 - 12.99 = 2,024.10.
    assert [p["spending"] for p in points[2:]] == ["2037.09", "2024.10", "2024.10"]
