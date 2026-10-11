"""
Principles (domain/decisions/principles.py): the user's own rules of thumb,
written in the tax rules' safe expression language over the decision
figures, validated on write and checked by hand-worked examples.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.domain.decisions import figures as figure_set
from salli.domain.decisions.principles import (
    Principle,
    PrincipleError,
    check,
    compile_check,
    content_hash,
    validate,
)
from salli.domain.taxrules.expr import parse, unparse

D = Decimal


def _figures(**values: Decimal | bool) -> figure_set.Figures:
    return figure_set.Figures("EUR", values, {}, {})


def _problems(principle: Principle) -> list[tuple[str, str]]:
    with pytest.raises(PrincipleError) as caught:
        validate(principle)
    return [(p.path, p.message) for p in caught.value.problems]


# ── The design's examples are expressible ────────────────────────────────────


@pytest.mark.parametrize(
    ("label", "text", "account"),
    [
        ("Six months of essentials in cash", "emergency_months >= 6", None),
        ("Clear debt above 7% before investing", "max_debt_rate_while_investing <= 0.07", None),
        ("Never drop below 2,000 in checking", "account_lowest >= 2_000", "chk"),
        ("Never below zero anywhere", "not any_account_below_zero", None),
        ("FI no later because of this", "fi_months_gained >= 0", None),
        ("Debt-free within five years", "debt_free_months <= 60", None),
        (
            "A year's spending in cash by next year",
            "cash_in_12_months >= 12 * monthly_spending",
            None,
        ),
        ("Borrow at most a tenth of net worth", "borrowed <= net_worth_1y / 10", None),
    ],
)
def test_the_rules_people_have_are_principles(label: str, text: str, account: str | None):
    expr = validate(Principle(label, text, account))
    assert unparse(expr)  # it parses, type-checks and prints


# ── Validated on write, every problem with its path ──────────────────────────


def test_an_unknown_figure_is_named_with_the_nearest_one():
    [(path, message)] = _problems(Principle("x", "emergency_month >= 6"))
    assert path == "check"
    assert "no figure 'emergency_month'" in message and "emergency_months" in message


def test_a_check_must_be_true_or_false():
    [(path, message)] = _problems(Principle("x", "emergency_months - 6"))
    assert path == "check" and "must be true or false" in message


def test_types_are_checked():
    [(path, message)] = _problems(Principle("x", "any_account_below_zero >= 1"))
    assert path == "check" and "must be a number" in message


def test_account_lowest_needs_an_account_and_an_account_needs_account_lowest():
    assert _problems(Principle("x", "account_lowest >= 2000")) == [
        (
            "account",
            "is required: account_lowest is the lowest of one account, so name the cash "
            "account it reads",
        )
    ]
    [(path, _)] = _problems(Principle("x", "lowest_cash >= 0", "chk"))
    assert path == "account"


def test_tax_functions_and_dotted_names_have_no_place_in_a_principle():
    [(_, message)] = _problems(Principle("x", 'bands(lowest_cash, "t") > 0'))
    assert "belongs to tax rules" in message
    [(_, message)] = _problems(Principle("x", "role.salary > 0"))
    assert "Name a figure plainly" in message


def test_every_problem_comes_at_once():
    found = _problems(Principle("", "nonsense_figure > 1", None, "n" * 3000))
    assert {path for path, _ in found} == {"label", "note", "check"}


def test_a_syntax_error_points_at_the_mistake():
    with pytest.raises(PrincipleError) as caught:
        compile_check(Principle("x", "emergency_months >= "))
    [problem] = caught.value.problems
    assert problem.snippet is not None and "^" in problem.snippet


def test_the_content_hash_ignores_spacing_but_not_meaning():
    a = content_hash(Principle("Six months", "emergency_months>=6"))
    b = content_hash(Principle("Six months", "  emergency_months  >=  6 "))
    c = content_hash(Principle("Six months", "emergency_months >= 7"))
    assert a == b != c


def test_a_figure_prints_as_its_plain_name():
    expr = parse("not (emergency_months < 6) and borrowed == 0", figures=True)
    assert unparse(expr) == "not emergency_months < 6 and borrowed == 0"
    assert parse(unparse(expr), figures=True) == expr


# ── Checking: hand-worked ────────────────────────────────────────────────────


def test_six_months_kept_and_broken():
    principle = Principle("Six months", "emergency_months >= 6")
    expr = validate(principle)
    kept = check(principle, expr, _figures(emergency_months=D("7.37")))
    assert (kept.status, kept.figures) == ("keeps", {"emergency_months": D("7.37")})
    assert kept.reason == "emergency_months >= 6 holds: emergency_months is 7.37."
    broken = check(principle, expr, _figures(emergency_months=D("5.99")))
    assert broken.status == "breaks"
    assert broken.reason == "emergency_months >= 6 doesn't hold: emergency_months is 5.99."


def test_clearing_dear_debt_before_investing():
    principle = Principle("Clear debt above 7%", "max_debt_rate_while_investing <= 0.07")
    expr = validate(principle)
    # A card at 19.9% still owed while the surplus is invested: broken.
    assert check(principle, expr, _figures(max_debt_rate_while_investing=D("0.199"))).status == (
        "breaks"
    )
    # Only a 5.9% loan owed while investing: kept; exactly 7% is kept too.
    for rate in ("0.059", "0.07", "0"):
        result = check(principle, expr, _figures(max_debt_rate_while_investing=D(rate)))
        assert result.status == "keeps", rate


def test_an_accounts_own_lowest_in_its_own_currency():
    principle = Principle("Checking above 2,000", "account_lowest >= 2000", "chk")
    expr = validate(principle)
    figures = figure_set.Figures(
        "EUR", {}, {}, {"chk": ("EUR", D("1999.99")), "sav": ("EUR", D("9000.00"))}
    )
    result = check(principle, expr, figures)
    assert (result.status, result.figures) == ("breaks", {"account_lowest": D("1999.99")})
    gone = figure_set.Figures("EUR", {}, {}, {"sav": ("EUR", D("9000.00"))})
    unknown = check(principle, expr, gone)
    assert unknown.status == "unknown" and "isn't one of the cash accounts" in unknown.reason


def test_arithmetic_over_figures():
    principle = Principle("A year of spending in cash", "lowest_cash >= 12 * monthly_spending")
    expr = validate(principle)
    # 12 × 1,898.32 = 22,779.84: 22,779.84 keeps it, a cent less breaks it.
    at = check(principle, expr, _figures(lowest_cash=D("22779.84"), monthly_spending=D("1898.32")))
    below = check(
        principle, expr, _figures(lowest_cash=D("22779.83"), monthly_spending=D("1898.32"))
    )
    assert (at.status, below.status) == ("keeps", "breaks")


def test_a_missing_figure_means_it_cant_tell_and_says_why():
    principle = Principle("FI sooner", "fi_months_gained >= 0")
    expr = validate(principle)
    figures = figure_set.Figures(
        "EUR", {}, {"fi_months_gained": "the FI number isn't reached within 50 years"}, {}
    )
    result = check(principle, expr, figures)
    assert result.status == "unknown"
    assert result.reason == (
        "Can't tell: fi_months_gained: the FI number isn't reached within 50 years."
    )
    assert result.figures == {"fi_months_gained": None}


def test_a_failed_calculation_means_it_cant_tell():
    principle = Principle("Ratio", "lowest_cash / borrowed >= 2")
    expr = validate(principle)
    result = check(principle, expr, _figures(lowest_cash=D("100"), borrowed=D("0")))
    assert (result.status, result.reason) == ("unknown", "Can't tell: Division by zero.")


def test_a_boolean_figure():
    principle = Principle("Never below zero", "not any_account_below_zero")
    expr = validate(principle)
    assert check(principle, expr, _figures(any_account_below_zero=False)).status == "keeps"
    result = check(principle, expr, _figures(any_account_below_zero=True))
    assert result.status == "breaks"
    assert (
        result.reason == "not any_account_below_zero doesn't hold: any_account_below_zero is true."
    )


def test_every_figure_is_documented_with_a_unit_and_terms():
    names = [f.name for f in figure_set.FIGURES]
    assert len(names) == len(set(names))
    for spec in figure_set.FIGURES:
        assert spec.description.endswith(".") and spec.unit
        assert spec.terms in ("nominal", "real", "none")
        if spec.kind == "amount":
            assert spec.terms != "none", spec.name
