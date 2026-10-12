"""
Hand-worked tax-aware scenarios on the fictional rule set "XA 2031"
(tests/golden/taxed.py): a relief of 12,000 on salary less pension
contributions, then 20% to 40,000 and 40% above; the year 2031-01-01 to
2031-12-31; as of 2031-06-30; a salary of 4,000.00 a month so far (24,000.00
actual, 4,000.00 on average); no inflation set.

Each test shows its arithmetic. Every figure is the scenario engine's,
through the baseline the API builds.
"""

from __future__ import annotations

import copy
import datetime as dt
from decimal import Decimal as D
from typing import Any

from salli.domain.baseline import Baseline, timelines
from salli.domain.decisions import figures as figure_set
from salli.domain.scenarios import engine, schema, views
from salli.domain.scenarios.tax import YearTax
from tests.golden import taxed

RAISE = {
    "type": "income_change",
    "monthly": "+1000.00",
    "from": "2031-07-01",
    "tax_role": "salary",
    "label": "Raise",
}


def scenario(*changes: dict[str, Any], **doc: Any) -> schema.Scenario:
    return schema.load({"schema": "salli.scenario/1", "changes": list(changes), **doc})


def baseline(**kw: Any) -> Baseline:
    return taxed.ledger(**kw).baseline(taxed.AS_OF)


def year(result: engine.ScenarioResult, label: str) -> YearTax:
    return next(y for y in result.tax.outcome.years if y.label == label)


def regular_by_month(b: Baseline, s: schema.Scenario) -> dict[str, D]:
    """Each month's regular surplus under the scenario, less the baseline's."""
    months = timelines.periods(b.as_of, timelines.horizon_months(3))
    changes = engine.translate(b, s).changes
    base = timelines.cash_plan(b, months, timelines.debt_paths(b, months))
    mine = timelines.cash_plan(b, months, timelines.debt_paths(b, months, changes), changes)
    return {p.period.month: m.regular - p.regular for p, m in zip(base, mine, strict=True)}


def test_a_raise_before_tax_this_year():
    """Baseline 2031: 24,000 actual + six months at 4,000 = 48,000; less the
    relief, 36,000 at 20% = 7,200.00. A raise of 1,000 a month from July,
    tagged salary: 54,000; 42,000 taxed = 40,000 × 20% + 2,000 × 40% =
    8,000.00 + 800.00 = 8,800.00. The change: 1,600.00, from July to
    December: 1,600 / 6 = 266.67 five times, and 266.65 in December."""
    b = baseline()
    result = engine.run(b, scenario(RAISE))
    assert result.tax.status == "computed"
    y2031 = year(result, "2031")
    (salary,) = y2031.roles
    assert (salary.key, salary.actual, salary.projected, salary.scenario) == (
        "salary",
        D("24000.00"),
        D("48000.00"),
        D("54000.00"),
    )
    assert (y2031.net_baseline, y2031.net_scenario, y2031.change) == (
        D("7200.00"),
        D("8800.00"),
        D("1600.00"),
    )
    assert y2031.parts == (
        ("2031-07", D("266.67")),
        ("2031-08", D("266.67")),
        ("2031-09", D("266.67")),
        ("2031-10", D("266.67")),
        ("2031-11", D("266.67")),
        ("2031-12", D("266.65")),
    )
    assert not y2031.carried_forward and y2031.rules is not None
    assert y2031.rules.rule_set_id == "rs-xa-2031"
    assert result.tax.outcome.change_this_year == D("1600.00")

    # Each month's regular surplus rises by 1,000.00 less its part:
    # 733.33, and 733.35 in December.
    rise = regular_by_month(b, scenario(RAISE))
    assert rise["2031-06"] == 0
    assert [rise[f"2031-{m:02d}"] for m in range(7, 12)] == [D("733.33")] * 5
    assert rise["2031-12"] == D("733.35")


def test_next_year_carries_the_rules_forward():
    """2032 has no active rules: XA 2031 carried forward, level in today's
    money (no inflation, so as they are). 48,000 gives 7,200.00; the raise's
    60,000 gives 40,000 × 20% + 8,000 × 40% = 8,000.00 + 3,200.00 =
    11,200.00. The change: 4,000.00, 333.33 eleven times and 333.37 in
    December, labelled tax_rules_carried_forward."""
    result = engine.run(baseline(), scenario(RAISE))
    y2032 = year(result, "2032")
    assert (y2032.start, y2032.end) == (dt.date(2032, 1, 1), dt.date(2032, 12, 31))
    assert y2032.carried_forward and y2032.status == "computed"
    assert (y2032.roles[0].actual, y2032.roles[0].projected, y2032.roles[0].scenario) == (
        D("0.00"),
        D("48000.00"),
        D("60000.00"),
    )
    assert (y2032.net_baseline, y2032.net_scenario, y2032.change) == (
        D("7200.00"),
        D("11200.00"),
        D("4000.00"),
    )
    assert [p for _, p in y2032.parts] == [D("333.33")] * 11 + [D("333.37")]
    assert "tax_rules_carried_forward" in result.placeholders
    view = views.result_view(result)["tax"]
    assert view["years"][1]["rules"]["carried_forward"] is True
    assert view["this_year"]["change"] == "1600.00"
    assert view["change_this_year"] == "1600.00"
    # Over the 20-year horizon (to 2051-06), in today's money: 1,600 + 19 ×
    # 4,000 + six months of 2051's 333.33 = 79,599.98.
    assert view["total_change"] == "79599.98"


def test_a_year_with_its_own_rules_uses_them():
    """With 2032's own rules active (the same rules, a relief of 15,000),
    2032 uses them: 48,000 − 15,000 = 33,000 → 6,600.00; 60,000 − 15,000 =
    45,000 → 8,000.00 + 2,000.00 = 10,000.00; a change of 3,400.00, not
    carried forward."""
    books = taxed.ledger()
    doc = copy.deepcopy(taxed.RULES)
    doc["year"] = {"label": "2032", "start": "2032-01-01", "end": "2032-12-31"}
    doc["blocks"][0]["amount"] = "15000"
    doc["examples"] = [
        {"name": "48,000", "inputs": {"salary": "48000"}, "expected": {"payable": "6600"}}
    ]
    books.uow.tax_rule_sets.active.append(taxed.rules_row(doc, rule_set_id="rs-xa-2032"))
    result = engine.run(books.baseline(taxed.AS_OF), scenario(RAISE))
    y2032 = year(result, "2032")
    assert not y2032.carried_forward
    assert y2032.rules is not None and y2032.rules.rule_set_id == "rs-xa-2032"
    assert (y2032.net_baseline, y2032.net_scenario, y2032.change) == (
        D("6600.00"),
        D("10000.00"),
        D("3400.00"),
    )
    # 2033 carries 2032's rules forward, the latest active.
    y2033 = year(result, "2033")
    assert y2033.carried_forward and y2033.rules is not None
    assert y2033.rules.rule_set_id == "rs-xa-2032"


def test_the_same_raise_untagged_has_no_tax():
    """Untagged, the raise is what reaches cash: no tax years, no tax among
    the placeholders, and the regular surplus rises by the whole 1,000.00."""
    b = baseline()
    untagged = scenario({k: v for k, v in RAISE.items() if k != "tax_role"})
    result = engine.run(b, untagged)
    assert result.tax.status == "none" and result.tax.outcome.years == ()
    assert "tax" not in result.placeholders
    assert "tax_rules_carried_forward" not in result.placeholders
    assert regular_by_month(b, untagged)["2031-07"] == D("1000.00")
    assert views.result_view(result)["tax"]["change_this_year"] == "0.00"


def test_a_pension_contribution_is_a_deduction():
    """6,000.00 paid into a pension on 2031-07-15, tagged with the deduction
    role: taxable 48,000 − 6,000 − 12,000 = 30,000 → 6,000.00, against
    7,200.00: 1,200.00 less tax, back into cash at 200.00 a month from July
    to December."""
    result = engine.run(
        baseline(),
        scenario(
            {
                "type": "one_off",
                "date": "2031-07-15",
                "amount": "-6000.00",
                "tax_role": "pension",
                "label": "Into the pension",
            }
        ),
    )
    y2031 = year(result, "2031")
    assert (y2031.roles[0].key, y2031.roles[0].scenario) == ("pension", D("6000.00"))
    assert y2031.change == D("-1200.00")
    assert [p for _, p in y2031.parts] == [D("-200.00")] * 6
    assert result.tax.outcome.change_this_year == D("-1200.00")


def test_a_stopped_salary_comes_off_its_role():
    """The ledger's salary (its account's role is salary) stopped from
    2031-07-01: 2031's salary is 24,000 → 12,000 taxed → 2,400.00, 4,800.00
    less; and 2032's, carried forward, nothing: 7,200.00 less."""
    result = engine.run(
        baseline(), scenario({"type": "stop_recurring", "key": "acme", "from": "2031-07-01"})
    )
    assert result.tax.status == "computed"
    assert year(result, "2031").change == D("-4800.00")
    assert year(result, "2032").change == D("-7200.00")


def test_tax_never_moves_the_fi_number():
    """The FI number is built on spending to live on: the raise's tax isn't
    any, tagged or not."""
    b = baseline()
    tagged = engine.run(b, scenario(RAISE))
    untagged = engine.run(b, scenario({k: v for k, v in RAISE.items() if k != "tax_role"}))
    assert tagged.fi.fi_number == untagged.fi.fi_number
    assert tagged.fi.monthly_spending == untagged.fi.monthly_spending
    # The tax comes out of the regular surplus, so less is invested.
    assert tagged.monthly[0].investments.delta is not None
    assert untagged.monthly[0].investments.delta is not None
    assert tagged.monthly[0].investments.delta < untagged.monthly[0].investments.delta


def test_the_figure_is_the_years_change():
    b = baseline()
    base = engine.baseline_outlook(b)
    _, done = engine.run_with_outlook(b, scenario(RAISE), base=base)
    mine = figure_set.compute(b, done.outlook, base, (), done.translation.tax)
    assert mine.values["tax_change_this_year"] == D("1600.00")
    assert figure_set.compute(b, base, base).values["tax_change_this_year"] == D("0.00")
    assert len(figure_set.FIGURES) == 33


def test_the_cash_floor_break_even_is_after_tax():
    """A side income tagged salary, and a recurring cost that takes cash
    below zero: the floor is found with the tax rerun at every step, so it
    is lower than without the tag (the side income keeps less)."""
    b = taxed.ledger().baseline(taxed.AS_OF)
    cost = {
        "type": "recurring",
        "amount": "-8000.00",
        "cadence": "monthly",
        "start": "2031-07-02",
        "label": "A cost",
    }
    side = {
        "type": "recurring",
        "amount": "+2000.00",
        "cadence": "monthly",
        "start": "2031-07-01",
        "label": "Side income",
    }
    plain = engine.run(b, scenario(side, cost))
    taxed_ = engine.run(b, scenario({**side, "tax_role": "salary"}, cost))
    (a,), (t,) = plain.break_evens, taxed_.break_evens
    assert a.status == t.status == "found"
    assert a.value is not None and t.value is not None and t.value < a.value
