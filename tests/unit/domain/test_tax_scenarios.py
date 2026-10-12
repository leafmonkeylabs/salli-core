"""
Tax-aware scenarios when the tax can't be computed, and the checks on tags
and answers (domain/scenarios/tax.py). The rules are the fictional XA 2031
(tests/golden/taxed.py).

Only active rules compute: with none, a draft only, no residency, a role the
active rules don't declare, a question with no answer or a missing rate, the
scenario still runs, its tagged amounts before tax, and says why.
"""

from __future__ import annotations

import copy
from decimal import Decimal as D
from typing import Any

import pytest

from salli.domain.baseline import timelines
from salli.domain.decisions import figures as figure_set
from salli.domain.scenarios import engine, schema, views
from salli.domain.scenarios.engine import ScenarioError
from salli.domain.scenarios.tax import plan
from tests.golden import taxed

RAISE = {
    "type": "income_change",
    "monthly": "+1000.00",
    "from": "2031-07-01",
    "tax_role": "salary",
    "label": "Raise",
}
UNTAGGED = {k: v for k, v in RAISE.items() if k != "tax_role"}


def scenario(*changes: dict[str, Any], **doc: Any) -> schema.Scenario:
    return schema.load({"schema": "salli.scenario/1", "changes": list(changes), **doc})


def comparable(result: engine.ScenarioResult) -> dict[str, Any]:
    """The result's figures: everything but the tax section, the
    placeholders, the notes, the hashes and the rule sets recorded."""
    view = views.result_view(result)
    for key in ("tax", "placeholders", "hash", "baseline_fingerprint", "scenario", "notes"):
        view.pop(key)
    view["versions"].pop("rule_sets")
    return view


def assert_runs_untaxed(books_kw: dict[str, Any], reason: str) -> engine.ScenarioResult:
    b = taxed.ledger(**books_kw).baseline(taxed.AS_OF)
    result = engine.run(b, scenario(RAISE))
    assert result.tax.status == "not_computed"
    assert result.tax.outcome.reason is not None and reason in result.tax.outcome.reason
    assert "tax" in result.placeholders
    # Tagged amounts flow before tax: every figure as the untagged raise's.
    assert comparable(result) == comparable(engine.run(b, scenario(UNTAGGED)))
    base = engine.baseline_outlook(b)
    _, done = engine.run_with_outlook(b, scenario(RAISE), base=base)
    figures = figure_set.compute(b, done.outlook, base, (), done.translation.tax)
    assert "tax_change_this_year" not in figures.values
    assert figures.why_missing("tax_change_this_year") == result.tax.outcome.reason
    assert views.result_view(result)["tax"]["change_this_year"] is None
    return result


def test_no_residency():
    assert_runs_untaxed({"residency": None}, "doesn't know where you're taxed")


def test_no_rule_set_at_all():
    books = taxed.ledger()
    books.uow.tax_rule_sets.active.clear()
    b = books.baseline(taxed.AS_OF)
    result = engine.run(b, scenario(RAISE))
    assert result.tax.status == "not_computed"
    assert result.tax.outcome.reason is not None
    assert result.tax.outcome.reason.startswith("You have no tax rules for")


def test_a_draft_never_computes():
    """A draft whose worked examples all pass still isn't active."""
    result = assert_runs_untaxed({"active": False}, "none is active yet")
    assert result.tax.outcome.years == ()


def test_a_role_the_active_rules_dont_declare():
    """bonus isn't a role of XA 2031: the year isn't computed. (A role no
    rule set of the person's declares at all is refused by the service.)"""
    b = taxed.ledger().baseline(taxed.AS_OF)
    result = engine.run(b, scenario({**RAISE, "tax_role": "bonus"}))
    assert result.tax.status == "not_computed"
    assert "bonus is not a role of your rules for 2031" in (result.tax.outcome.reason or "")
    assert comparable(result) == comparable(engine.run(b, scenario(UNTAGGED)))


def test_a_withholding_role_cant_be_tagged():
    b = taxed.ledger().baseline(taxed.AS_OF)
    with pytest.raises(ScenarioError) as raised:
        engine.translate(b, scenario({**RAISE, "tax_role": "tax_withheld"}))
    assert [p.path for p in raised.value.problems] == ["changes[0].tax_role"]
    assert "only income and deduction roles" in raised.value.problems[0].message


def _with_question(default: str | None = None) -> taxed.Ledger:  # type: ignore[name-defined]
    doc = copy.deepcopy(taxed.RULES)
    question: dict[str, Any] = {
        "key": "filing_status",
        "label": "Filing status",
        "type": "choice",
        "choices": ["single", "joint"],
    }
    if default:
        question["default"] = default
    doc["questions"] = [question]
    books = taxed.ledger()
    books.uow.tax_rule_sets.active[:] = [taxed.rules_row(doc)]
    return books


def test_a_question_with_no_answer():
    b = _with_question().baseline(taxed.AS_OF)
    result = engine.run(b, scenario(RAISE))
    assert result.tax.status == "not_computed"
    assert "Filing status (`filing_status`)" in (result.tax.outcome.reason or "")
    assert "tax.answers" in (result.tax.outcome.reason or "")
    answered = engine.run(b, scenario(RAISE, tax={"answers": {"filing_status": "single"}}))
    assert answered.tax.status == "computed"
    assert answered.tax.outcome.change_this_year == D("1600.00")


def test_answers_are_checked_with_paths():
    b = _with_question("single").baseline(taxed.AS_OF)
    with pytest.raises(ScenarioError) as raised:
        engine.translate(
            b, scenario(RAISE, tax={"answers": {"filing_status": "widowed", "pets": "2"}})
        )
    assert sorted(p.path for p in raised.value.problems) == [
        "tax.answers.filing_status",
        "tax.answers.pets",
    ]


def test_a_missing_rate():
    """Rules in another currency than the books', and no published rate:
    never a guessed one."""
    doc = copy.deepcopy(taxed.RULES)
    doc["currency"] = "AUD"
    books = taxed.ledger()
    books.uow.tax_rule_sets.active[:] = [taxed.rules_row(doc)]
    result = engine.run(books.baseline(taxed.AS_OF), scenario(RAISE))
    assert result.tax.status == "not_computed"
    assert "no NZD→AUD exchange rate for 2031-06-30" in (result.tax.outcome.reason or "")


def test_rules_in_another_currency_convert_at_the_rates():
    """At 0.5 AUD to the NZD, every amount is halved into AUD: 24,000 →
    12,000 projected, 27,000 with the raise; 12,000 − 12,000 relief → 0 and
    15,000 → 3,000 at 20% = 600.00 AUD more, 1,200.00 NZD."""
    doc = copy.deepcopy(taxed.RULES)
    doc["currency"] = "AUD"
    books = taxed.ledger()
    books.uow.tax_rule_sets.active[:] = [taxed.rules_row(doc)]
    books.rates[("NZD", "AUD", None)] = (D("0.5"), "test-bank")
    result = engine.run(books.baseline(taxed.AS_OF), scenario(RAISE))
    y2031 = result.tax.outcome.years[0]
    assert y2031.currency == "AUD"
    assert (y2031.roles[0].projected, y2031.roles[0].scenario) == (D("24000.00"), D("27000.00"))
    assert (y2031.net_baseline, y2031.net_scenario) == (D("2400.00"), D("3000.00"))
    assert y2031.change == D("1200.00")


def test_nothing_tagged_reads_no_rules():
    b = taxed.ledger(residency=None).baseline(taxed.AS_OF)
    result = engine.run(b, scenario(UNTAGGED))
    assert result.tax.status == "none" and result.tax.outcome.reason is None
    assert "tax" not in result.placeholders


def test_tax_years_are_planned_from_the_as_of_year():
    b = taxed.ledger().baseline(taxed.AS_OF)
    years = plan(b.tax, taxed.AS_OF, timelines.periods(taxed.AS_OF, 30)[-1].end)
    assert [(y.label, y.carried) for y in years] == [("2031", 0), ("2032", 1), ("2033", 2)]
    assert years[0].start.isoformat() == "2031-01-01"


def _xa(total: D) -> D:
    """XA 2031 by hand: a relief of 12,000, 20% to 40,000, 40% above."""
    taxable = max(D(0), total - 12000)
    return min(taxable, D(40000)) * D("0.20") + max(D(0), taxable - 40000) * D("0.40")


def test_inflation_holds_carried_rules_level_in_todays_money():
    """With inflation of 2.4% (0.2% a month), 2032's totals are in 2032's
    money: each is deflated by twelve months of it (1.002^12) into 2031's,
    taxed by XA 2031, and the tax grown back. So the relief and the bands
    rise with prices, as every carried-forward amount does."""
    books = taxed.ledger()
    books.assume(inflation="0.024")
    b = books.baseline(taxed.AS_OF)
    y2032 = next(y for y in engine.run(b, scenario(RAISE)).tax.outcome.years if y.label == "2032")
    assert y2032.carried_forward and y2032.change is not None
    factor = D("1.002") ** 12
    cent = D("0.01")
    (salary,) = y2032.roles
    # The year's projections grow with prices: more than 48,000 and 60,000.
    assert salary.projected > 48000 and salary.scenario > 60000
    for total, net in (
        (salary.projected, y2032.net_baseline),
        (salary.scenario, y2032.net_scenario),
    ):
        deflated = (total / factor).quantize(cent)
        assert net == (_xa(deflated).quantize(cent) * factor).quantize(cent)
    assert y2032.change == y2032.net_scenario - y2032.net_baseline  # type: ignore[operator]
