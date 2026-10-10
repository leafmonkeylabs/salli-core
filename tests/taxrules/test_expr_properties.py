"""
Fuzzing and properties for the expression language.

The language is an attack surface: its input comes from users and from agents
that read the web. So whatever text arrives, parsing either succeeds or raises
one of the module's own errors, and the same goes for type-checking and
evaluating whatever parsed. Nothing else (a RecursionError, a TypeError, a raw
decimal signal) may escape.

And two properties every tree must have: printing it and parsing it back gives
the same tree, and evaluating it gives the same answer every time, whatever the
caller's decimal context.
"""

from __future__ import annotations

import decimal
from decimal import Decimal
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salli.domain.taxrules.arith import Band, BandTable, Rounding
from salli.domain.taxrules.expr import (
    Binary,
    Bool,
    Call,
    Expr,
    ExprError,
    ExprType,
    Node,
    Num,
    Ref,
    Scope,
    Str,
    Unary,
    evaluate,
    parse,
    type_of,
    unparse,
)

D = Decimal

TABLES = {
    "t": BandTable((Band(D("100"), D("0.1")), Band(D("300"), D("0.25")), Band(None, D("0.4")))),
    "r": BandTable((Band(D("50"), D("0.05")), Band(None, D("0.2"))), Rounding("nearest", D("1"))),
}
TYPES = {
    Ref("role", "a"): ExprType.NUMBER,
    Ref("role", "b"): ExprType.NUMBER,
    Ref("answer", "n"): ExprType.NUMBER,
    Ref("answer", "flag"): ExprType.BOOLEAN,
    Ref("answer", "c"): ExprType.STRING,
    Ref("line", "x.y"): ExprType.NUMBER,
}

numbers = st.decimals(
    min_value=D("-1E+12"), max_value=D("1E+12"), places=4, allow_nan=False, allow_infinity=False
)


@st.composite
def scopes(draw: Any) -> Scope:
    return Scope(
        {
            Ref("role", "a"): draw(numbers),
            Ref("role", "b"): draw(numbers),
            Ref("answer", "n"): draw(numbers),
            Ref("answer", "flag"): draw(st.booleans()),
            Ref("answer", "c"): draw(st.sampled_from(["a", "b", "z"])),
            Ref("line", "x.y"): draw(numbers),
        },
        TABLES,
    )


# ── fuzzing ────────────────────────────────────────────────────────────────────

TOKENS = [
    "1",
    "0",
    "2.5",
    "1_000",
    "0.15",
    "role.a",
    "role.b",
    "answer.n",
    "answer.flag",
    "answer.c",
    "line.x.y",
    "line.x",
    "role.zz",
    "true",
    "false",
    "+",
    "-",
    "*",
    "/",
    "<",
    "<=",
    ">",
    ">=",
    "==",
    "!=",
    "and",
    "or",
    "not",
    "(",
    ")",
    ",",
    "min",
    "max",
    "clamp",
    "abs",
    "if",
    "round",
    "bands",
    "band_amount",
    "choice",
    '"nearest"',
    '"down"',
    '"up"',
    '"half_even"',
    '"t"',
    '"r"',
    '"a"',
    '"b"',
    '"q"',
    "__import__",
    "__class__",
    ".",
    "[",
    "]",
    "'",
    '"',
    "=",
    "\n",
    "\\",
    "1e3",
    "-0",
    "99999999999999",
]

token_soup = st.lists(st.sampled_from(TOKENS), max_size=40).map(" ".join)
dense_soup = st.lists(st.sampled_from(TOKENS), max_size=40).map("".join)


def _exercise(text: str, scope: Scope) -> None:
    try:
        expr = parse(text)
    except ExprError:
        return
    try:
        type_of(expr, TYPES)
    except ExprError:
        pass
    try:
        evaluate(expr, scope)
    except ExprError:
        pass


@settings(max_examples=3000, suppress_health_check=[HealthCheck.too_slow])
@given(st.text(max_size=300))
def test_any_text_parses_or_raises_only_the_modules_own_errors(text):
    try:
        parse(text)
    except ExprError:
        pass


@settings(max_examples=3000, suppress_health_check=[HealthCheck.too_slow])
@given(st.one_of(token_soup, dense_soup), scopes())
def test_token_soup_parses_checks_and_evaluates_with_only_the_modules_own_errors(text, scope):
    _exercise(text, scope)


# ── trees ──────────────────────────────────────────────────────────────────────

leaf_numbers = st.decimals(min_value=0, max_value=D("1E+9"), places=3, allow_nan=False)
leaves: st.SearchStrategy[Node] = st.one_of(
    leaf_numbers.map(Num),
    st.booleans().map(Bool),
    st.sampled_from(
        [
            Ref("role", "a"),
            Ref("role", "b"),
            Ref("answer", "n"),
            Ref("answer", "flag"),
            Ref("line", "x.y"),
        ]
    ),
)
binary_ops = st.sampled_from(["+", "-", "*", "/", "<", "<=", ">", ">=", "==", "!=", "and", "or"])


def _extend(children: st.SearchStrategy[Node]) -> st.SearchStrategy[Node]:
    unit = st.sampled_from([D("1"), D("0.01"), D("5"), D("0.05")]).map(Num)
    mode = st.sampled_from(["nearest", "down", "up", "half_even"]).map(Str)
    table = st.sampled_from(["t", "r"]).map(Str)
    return st.one_of(
        st.tuples(st.sampled_from(["-", "not"]), children).map(lambda t: Unary(t[0], t[1])),  # type: ignore[arg-type]
        st.tuples(binary_ops, children, children).map(lambda t: Binary(t[0], t[1], t[2])),  # type: ignore[arg-type]
        st.tuples(st.sampled_from(["min", "max"]), st.lists(children, min_size=2, max_size=4)).map(
            lambda t: Call(t[0], tuple(t[1]))
        ),
        st.tuples(children, children, children).map(lambda t: Call("clamp", t)),
        children.map(lambda c: Call("abs", (c,))),
        st.tuples(children, children, children).map(lambda t: Call("if", t)),
        st.tuples(children, mode, unit).map(lambda t: Call("round", t)),
        st.tuples(children, table).map(lambda t: Call("bands", t)),
        st.tuples(children, st.sampled_from([D(1), D(2)]).map(Num)).map(
            lambda t: Call("band_amount", (t[0], Str("r"), t[1]))
        ),
        st.tuples(children, children).map(
            lambda t: Call("choice", (Ref("answer", "c"), Str("a"), t[0], Str("b"), t[1]))
        ),
    )


trees = st.recursive(leaves, _extend, max_leaves=25)


@settings(max_examples=2000, suppress_health_check=[HealthCheck.too_slow])
@given(trees)
def test_printing_a_tree_and_parsing_it_back_gives_the_same_tree(tree):
    text = unparse(tree)
    parsed = parse(text)
    assert parsed == Expr(tree)
    assert unparse(parsed) == text  # and printing is stable


@settings(max_examples=2000, suppress_health_check=[HealthCheck.too_slow])
@given(trees, scopes())
def test_evaluation_is_deterministic_whatever_the_callers_context(tree, scope):
    expr = parse(unparse(tree))

    def outcome() -> tuple[str, Any]:
        try:
            return ("value", evaluate(expr, scope))
        except ExprError as error:
            return ("error", str(error))

    first = outcome()
    with decimal.localcontext() as ambient:
        ambient.prec = 3
        ambient.rounding = decimal.ROUND_FLOOR
        ambient.traps[decimal.InvalidOperation] = False
        ambient.traps[decimal.DivisionByZero] = False
        second = outcome()
    third = outcome()
    assert first == second == third
    if first[0] == "value":
        value = first[1]
        assert isinstance(value, bool) or (isinstance(value, Decimal) and value.is_finite())
