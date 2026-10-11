"""
Properties of principles and the decision journal:

- checking a principle is deterministic: the same figures give the same
  result, whatever the caller's decimal context, and a comparison against a
  number keeps exactly when the comparison holds;
- a check prints and parses back to itself;
- a missing figure is never kept or broken.

(Appending to the journal: tests/properties/test_decision_journal.py.)
"""

from __future__ import annotations

import decimal
import operator
from collections.abc import Callable
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from salli.domain.decisions import figures as figure_set
from salli.domain.decisions.principles import Principle, check, validate
from salli.domain.taxrules.expr import parse, unparse

NUMERIC = [f.name for f in figure_set.FIGURES if f.kind != "boolean" and f.name != "account_lowest"]
OPERATORS: dict[str, Callable[[Decimal, Decimal], bool]] = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}

values = st.decimals(
    min_value=Decimal("-1E+9"), max_value=Decimal("1E+9"), places=2, allow_nan=False
)


@settings(max_examples=300)
@given(
    name=st.sampled_from(NUMERIC),
    op=st.sampled_from(list(OPERATORS)),
    threshold=values,
    value=values,
    precision=st.integers(min_value=4, max_value=40),
)
def test_a_comparison_keeps_exactly_when_it_holds(
    name: str, op: str, threshold: Decimal, value: Decimal, precision: int
):
    principle = Principle("p", f"{name} {op} {threshold:f}")
    expr = validate(principle)
    figures = figure_set.Figures("EUR", {name: value}, {}, {})
    first = check(principle, expr, figures)
    with decimal.localcontext() as ctx:
        ctx.prec = precision
        again = check(principle, expr, figures)
    assert first == again
    assert first.status == ("keeps" if OPERATORS[op](value, threshold) else "breaks")


@given(
    a=st.sampled_from(NUMERIC),
    b=st.sampled_from(NUMERIC),
    k=st.integers(min_value=0, max_value=1000),
    joiner=st.sampled_from(["and", "or"]),
)
def test_a_check_prints_and_parses_back_to_itself(a: str, b: str, k: int, joiner: str):
    text = f"({a} - {b}) * 2 >= {k} {joiner} not any_account_below_zero"
    expr = parse(text, figures=True)
    assert parse(unparse(expr), figures=True) == expr


@given(name=st.sampled_from(NUMERIC), threshold=values)
def test_a_missing_figure_is_never_kept_or_broken(name: str, threshold: Decimal):
    principle = Principle("p", f"{name} >= 0 or {name} < 0")
    expr = validate(principle)
    figures = figure_set.Figures("EUR", {}, {name: "not known"}, {})
    assert check(principle, expr, figures).status == "unknown"
