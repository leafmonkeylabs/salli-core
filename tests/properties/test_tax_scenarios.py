"""
Properties of tax-aware scenarios (domain/scenarios/tax.py), on the
fictional XA 2031 household (tests/golden/taxed.py):

- a scenario that tags nothing has `tax.status` "none", and every figure
  equal to the engine's without any rules at all;
- a tag of 0 changes nothing;
- each year's monthly parts add up to its change exactly;
- tax never moves the FI number;
- at an as-of date on a tax year's last day, the baseline's projected tax
  is what TaxService computes for the year, so a scenario and the tax page
  never disagree;
- evaluating twice gives the same result, memoised or not.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from decimal import Decimal
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salli.application.services.tax_rule_service import TaxRuleService
from salli.application.services.tax_service import TaxService
from salli.domain.baseline import Baseline
from salli.domain.scenarios import engine, schema, views
from tests.baseline_ledger import USER
from tests.golden import taxed

_SETTINGS = settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])

amounts = st.decimals(min_value=Decimal("-3000"), max_value=Decimal("9000"), places=2).filter(
    lambda d: d != 0
)
days = st.integers(min_value=1, max_value=900)
roles = st.sampled_from(["salary", "pension"])

_TAXED = taxed.ledger().baseline(taxed.AS_OF)
_NO_RULES = taxed.ledger(residency=None).baseline(taxed.AS_OF)


def _day(offset: int) -> str:
    return (taxed.AS_OF + dt.timedelta(days=offset)).isoformat()


@st.composite
def changes(draw: st.DrawFn, tagged: bool) -> dict[str, Any]:
    amount = draw(amounts)
    role = {"tax_role": draw(roles)} if tagged else {}
    kind = draw(st.sampled_from(["one_off", "recurring", "income_change"]))
    if kind == "one_off":
        return {
            "type": "one_off",
            "date": _day(draw(days)),
            "amount": f"{amount}",
            **role,
            "label": "Once",
        }
    if kind == "recurring":
        return {
            "type": "recurring",
            "amount": f"{amount}",
            "cadence": draw(st.sampled_from(["monthly", "quarterly", "yearly"])),
            "start": _day(draw(days)),
            **role,
            "label": "Again",
        }
    return {
        "type": "income_change",
        "monthly": f"{amount}",
        "from": _day(draw(days)),
        **role,
        "label": "Pay",
    }


def _doc(changes: list[dict[str, Any]]) -> schema.Scenario:
    return schema.load({"schema": "salli.scenario/1", "horizon_years": 5, "changes": changes})


def _figures(baseline: Baseline, scenario: schema.Scenario) -> dict[str, Any]:
    view = views.result_view(engine.run(baseline, scenario))
    for key in ("hash", "baseline_fingerprint", "notes"):
        view.pop(key)
    view["versions"].pop("rule_sets")
    return view


@_SETTINGS
@given(st.lists(changes(tagged=False), min_size=1, max_size=3))
def test_nothing_tagged_is_as_without_rules(items):
    scenario = _doc(items)
    with_rules = _figures(_TAXED, scenario)
    assert with_rules["tax"]["status"] == "none"
    assert with_rules == _figures(_NO_RULES, scenario)


@_SETTINGS
@given(st.sampled_from(["one_off", "income_change"]), roles)
def test_a_tag_of_zero_changes_nothing(kind, role):
    if kind == "one_off":
        change = {"type": "one_off", "date": _day(30), "amount": "0.00", "label": "Zero"}
    else:
        change = {"type": "income_change", "monthly": "0", "from": _day(1), "label": "Zero"}
    plain = _figures(_TAXED, _doc([change]))
    tagged = _figures(_TAXED, _doc([{**change, "tax_role": role}]))
    assert tagged["tax"]["status"] == "computed"
    assert {y["change"] for y in tagged["tax"]["years"]} == {"0.00"}
    for key in ("cash", "monthly", "debts", "resilience", "fi", "break_evens"):
        assert tagged[key] == plain[key]


@_SETTINGS
@given(st.lists(changes(tagged=True), min_size=1, max_size=3))
def test_parts_add_up_to_each_years_change(items):
    result = engine.run(_TAXED, _doc(items))
    assert result.tax.status == "computed"
    last = result.tax.outcome.years[-1] if result.tax.outcome.years else None
    for year in result.tax.outcome.years:
        assert year.change is not None
        if year is last:
            continue  # its parts may run past the 50-year timeline
        assert sum((p for _, p in year.parts), Decimal(0)) == year.change


@_SETTINGS
@given(st.lists(changes(tagged=True), min_size=1, max_size=3))
def test_tax_never_moves_the_fi_number(items):
    untagged = [{k: v for k, v in c.items() if k != "tax_role"} for c in items]
    tagged, plain = engine.run(_TAXED, _doc(items)), engine.run(_TAXED, _doc(untagged))
    assert tagged.fi.fi_number == plain.fi.fi_number
    assert tagged.fi.monthly_spending == plain.fi.monthly_spending


@_SETTINGS
@given(st.lists(changes(tagged=True), min_size=1, max_size=3))
def test_the_same_inputs_give_the_same_tax(items):
    scenario = _doc(items)
    first = views.result_view(engine.run(_TAXED, scenario))
    again = views.result_view(engine.run(_TAXED, scenario))  # memoised now
    fresh = views.result_view(engine.run(taxed.ledger().baseline(taxed.AS_OF), scenario))
    assert first == again == fresh


@_SETTINGS
@given(st.decimals(min_value=Decimal("1000"), max_value=Decimal("12000"), places=2))
def test_on_a_years_last_day_the_scenario_agrees_with_the_tax_page(salary):
    """As of 2031-12-31, the year is all actual: the baseline's net for 2031
    is TaxService's computation for it."""
    books = taxed.ledger(months=12, salary=str(salary))
    as_of = dt.date(2031, 12, 31)
    baseline = books.baseline(as_of)
    one = {
        "type": "one_off",
        "date": "2031-12-31",
        "amount": "100.00",
        "tax_role": "salary",
        "label": "Bonus",
    }
    year = engine.run(baseline, _doc([one])).tax.outcome.years[0]
    factory = books.uow.factory()
    page = asyncio.run(
        TaxService(factory, TaxRuleService(factory), clock=lambda: as_of).compute_tax(
            USER, year="2031", persist=False
        )
    )
    assert year.net_baseline == Decimal(page["net"])
