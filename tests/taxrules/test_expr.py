"""
The expression language: what it computes, what it refuses, and where it says
the mistake is.

Rule sets are written by users and their agents, and an agent may have read
anything on the web while writing one, so the refusals matter as much as the
arithmetic: nothing that looks like Python reaches anything Pythonic.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.domain.taxrules.arith import Band, BandTable, Rounding
from salli.domain.taxrules.expr import (
    MAX_ARGUMENTS,
    MAX_DEPTH,
    MAX_LENGTH,
    MAX_NODES,
    Binary,
    ExprError,
    ExprEvaluationError,
    ExprLimitError,
    ExprSyntaxError,
    ExprType,
    ExprTypeError,
    Num,
    Ref,
    Scope,
    evaluate,
    parse,
    references,
    type_of,
    unparse,
)

D = Decimal

TABLE = BandTable(
    (Band(D("1000"), D("0.1")), Band(None, D("0.2"))),
    Rounding("nearest", D("1")),
)
VALUES = {
    Ref("role", "salary"): D("2500"),
    Ref("role", "zero"): D("0"),
    Ref("role", "huge"): D("9E+999990"),
    Ref("answer", "status"): "joint",
    Ref("answer", "blind"): True,
    Ref("answer", "children"): D("2"),
    Ref("line", "general"): D("100"),
    Ref("line", "general.band_1.tax"): D("40"),
}
TYPES = {
    Ref("role", "salary"): ExprType.NUMBER,
    Ref("role", "zero"): ExprType.NUMBER,
    Ref("answer", "status"): ExprType.STRING,
    Ref("answer", "blind"): ExprType.BOOLEAN,
    Ref("answer", "children"): ExprType.NUMBER,
    Ref("line", "general"): ExprType.NUMBER,
    Ref("line", "general.band_1.tax"): ExprType.NUMBER,
}


def ev(text: str) -> Decimal | bool:
    expr = parse(text)
    return evaluate(expr, Scope(VALUES, {"general": TABLE}))


# ── arithmetic ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 + 2 * 3", D(7)),
        ("(1 + 2) * 3", D(9)),
        ("-2 * 3", D(-6)),
        ("10 - 4 - 3", D(3)),  # left to right
        ("8 / 4 / 2", D(1)),
        ("1_800_000 * 0.06", D("108000.00")),
        ("--5", D(5)),
        ("1 / 3 * 3", D("0.9999999999999999999999999999")),  # 28 digits, no float
        ("role.salary - line.general", D(2400)),
        ("line.general.band_1.tax * 2", D(80)),
    ],
)
def test_arithmetic_follows_the_usual_precedence_in_decimal(text, expected):
    assert ev(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 < 2", True),
        ("2 <= 2", True),
        ("3 > 4", False),
        ("1 == 1.00", True),
        ("1 != 2", True),
        ("true == answer.blind", True),
        ("not 1 < 2", False),  # not binds looser than a comparison
        ("true and false or true", True),
        ("not true and false", False),  # (not true) and false
        ("false and 1 / 0 > 0", False),  # and stops at false
        ("true or 1 / 0 > 0", True),
    ],
)
def test_comparisons_and_logic(text, expected):
    assert ev(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("min(3, 1, 2)", D(1)),
        ("max(3, 1, 2)", D(3)),
        ("clamp(15, 10, 50)", D(15)),
        ("clamp(5, 10, 50)", D(10)),
        ("clamp(55, 10, 50)", D(50)),
        ("abs(0 - 4)", D(4)),
        ("if(answer.blind, 2000, 0)", D(2000)),
        ("if(role.zero == 0, 0, 1 / role.zero)", D(0)),  # only the chosen branch runs
        ('round(2.5, "nearest", 1)', D(3)),
        ('round(2.5, "half_even", 1)', D(2)),
        ('round(1234.567, "down", 0.01)', D("1234.56")),
        ('round(1234.561, "up", 0.01)', D("1234.57")),
        ('bands(2500, "general")', D(400)),  # 1000 × 10% + 1500 × 20%
        ('band_amount(2500, "general", 2)', D(1500)),
        ('band_amount(500, "general", 2)', D(0)),
        ('choice(answer.status, "single", 1, "joint", 2)', D(2)),
        ('choice(answer.status, "single", 1 / 0, "joint", 2)', D(2)),  # lazily
    ],
)
def test_functions(text, expected):
    assert ev(text) == expected


def test_references_lists_what_an_expression_uses_once_each():
    expr = parse("role.salary + min(role.salary, line.general.band_1.tax) + answer.children")
    assert references(expr) == {
        Ref("role", "salary"),
        Ref("line", "general.band_1.tax"),
        Ref("answer", "children"),
    }


def test_trees_compare_by_meaning_not_spacing():
    assert parse("1+2*role.a") == parse("1 + 2 * role.a")
    assert parse("(1 + 2) + 3") == parse("1 + 2 + 3")
    assert parse("1 + (2 + 3)") != parse("1 + 2 + 3")


def test_unparse_writes_only_the_parentheses_needed():
    assert unparse(parse("((1 + 2)) * (3)")) == "(1 + 2) * 3"
    assert unparse(parse("1 - (2 - 3)")) == "1 - (2 - 3)"
    assert unparse(parse("(1 - 2) - 3")) == "1 - 2 - 3"
    assert unparse(parse("-(role.a * 2)")) == "-(role.a * 2)"
    assert unparse(parse("not (true and false)")) == "not (true and false)"
    assert unparse(parse("(1 < 2) == true")) == "(1 < 2) == true"
    assert unparse(parse("1_000.50")) == "1000.50"


# ── types ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("role.salary * 0.1", ExprType.NUMBER),
        ("role.salary > 0 and answer.blind", ExprType.BOOLEAN),
        ("if(answer.blind, 1, 2)", ExprType.NUMBER),
        ('choice(answer.status, "single", true, "joint", false)', ExprType.BOOLEAN),
    ],
)
def test_type_of_reports_what_an_expression_produces(text, expected):
    assert type_of(parse(text), TYPES) is expected


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("1 + true", "must be a number"),
        ("answer.blind * 2", "must be a number"),
        ("not 1", "must be a boolean"),
        ("true < false", "must be a number"),
        ("1 == true", "compares a number with a boolean"),
        ("if(1, 2, 3)", "condition must be a boolean"),
        ("if(true, 1, false)", "same type"),
        ("answer.status + 1", "is a choice"),
        ("min(answer.status, 1)", "is a choice"),
        ('choice(answer.children, "a", 1)', "isn't one"),
        ('choice(answer.status, "single", 1, "joint", true)', "same type"),
        ("role.unknown + 1", "Unknown reference role.unknown"),
        ("true and 1", "must be a boolean"),
    ],
)
def test_type_errors_are_caught_before_evaluation(text, message):
    with pytest.raises(ExprTypeError, match=message):
        type_of(parse(text), TYPES)


# ── evaluation errors ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("1 / 0", "Division by zero"),
        ("0 / 0", "undefined"),
        ("role.missing", "No value for role.missing"),
        ("clamp(1, 5, 2)", "lower bound"),
        ('choice(answer.status, "single", 1, "widowed", 2)', "doesn't list"),
        ("role.huge * role.huge", "too large"),
        ("1 + true", "Expected a number"),  # also guarded when never type-checked
        ("answer.status", "is a choice"),
    ],
)
def test_evaluation_errors_are_the_modules_own_and_say_why(text, message):
    with pytest.raises(ExprEvaluationError, match=message):
        ev(text)


def test_an_evaluation_error_points_at_the_operation_that_failed():
    with pytest.raises(ExprEvaluationError) as caught:
        ev("1 +\n  role.salary / role.zero")
    error = caught.value
    assert (error.line, error.column) == (2, 15)
    assert error.snippet == "  role.salary / role.zero\n              ^"


def test_evaluation_ignores_whatever_decimal_context_the_caller_has():
    import decimal

    expected = ev("1 / 3")
    with decimal.localcontext() as ambient:
        ambient.prec = 2
        ambient.rounding = decimal.ROUND_FLOOR
        ambient.traps[decimal.DivisionByZero] = False
        assert ev("1 / 3") == expected
        with pytest.raises(ExprEvaluationError):
            ev("1 / 0")


# ── syntax errors and refusals ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os')",
        '__import__("os")',
        "().__class__",
        "().__class__.__bases__[0].__subclasses__()",
        "line.__class__",
        "line.general.__class__",
        "role.__dict__",
        "answer.__init__",
        "eval('1')",
        "exec",
        "open",
        "lambda: 1",
        "[1, 2]",
        "{}",
        "1 if true else 2",
        "role.salary[0]",
        "role.salary()",
        "min.__call__(1, 2)",
        "getattr(role, 'salary')",
        "role.Salary",
        "role._salary",
        "Role.salary",
        "line.",
        "line..x",
        "role.a.b",
        "answer.a.b",
        "x.y",
        "salary",
        "1e5",
        "1.",
        ".5",
        "0x10",
        "1__000",
        "1_000_",
        "'single'",
        '"Single"',
        '"a b"',
        '"unterminated',
        "1 ** 2",
        "1 // 2",
        "1 % 2",
        "1 = 1",
        "!true",
        "true && false",
        "1 < 2 < 3",
        "min()",
        "abs(1, 2)",
        "min(1)",
        "if(true, 1)",
        'round(1, "nearest")',
        'round(1, "ceiling", 1)',
        'round(1, "nearest", 0)',
        'round(1, "nearest", -1)',
        'round(1, "nearest", role.salary)',
        "round(1, nearest, 1)",
        "bands(1, general)",
        'band_amount(1, "general", 0)',
        'band_amount(1, "general", 1.5)',
        'choice(role.salary, "a", 1)',
        'choice(answer.status, "a", 1, "a", 2)',
        'choice(answer.status, "a")',
        '"single" + 1',
        "min(1, 2,)",
        "(1 + 2",
        "1 + 2)",
        "",
        "   ",
        "1 2",
        "true false",
        "and",
        "not",
        "#1",
        "1; 2",
        "role.salary\\\n+ 1",
        "１",  # a full-width digit: only ASCII digits are numbers
        "rôle.salary",
        "1 + 12345678901234567890123456789",  # 29 significant digits
    ],
)
def test_anything_outside_the_grammar_is_a_syntax_error(text):
    with pytest.raises(ExprSyntaxError):
        parse(text)


def test_syntax_errors_carry_a_line_column_and_caret():
    with pytest.raises(ExprSyntaxError) as caught:
        parse("min(role.salary,\n    line.Bad)")
    error = caught.value
    assert (error.line, error.column) == (2, 10)
    assert error.snippet == "    line.Bad)\n         ^"
    assert "line 2, column 10" in str(error)


def test_a_long_line_is_trimmed_around_the_caret():
    text = "1 + " * 30 + "?" + " + 1" * 30
    with pytest.raises(ExprSyntaxError) as caught:
        parse(text)
    source, caret = caught.value.snippet.split("\n")
    assert source[caret.index("^")] == "?"
    assert len(source) < len(text)


# ── limits ─────────────────────────────────────────────────────────────────────


def test_an_expression_longer_than_the_limit_is_refused_before_parsing():
    parse("1" + " " * (MAX_LENGTH - 1))
    with pytest.raises(ExprLimitError, match="characters"):
        parse("1" + " " * MAX_LENGTH)


def test_an_expression_with_too_many_parts_is_refused():
    inner = "min(" + ", ".join(["1"] * 63) + ")"
    text = "max(" + ", ".join([inner] * 16) + ")"  # 16 × 64 + 1 = 1025 parts
    assert len(text) <= MAX_LENGTH
    with pytest.raises(ExprLimitError, match=f"at most {MAX_NODES} parts"):
        parse(text)


@pytest.mark.parametrize(
    ("make", "name"),
    [
        (lambda n: "(" * n + "1" + ")" * n, "parentheses"),
        (lambda n: "-" * n + "1", "negations"),
        (lambda n: " + ".join(["1"] * n), "a long sum"),
        (lambda n: "abs(" * n + "1" + ")" * n, "calls"),
        (lambda n: "not " * n + "true", "nots"),
    ],
)
def test_nesting_is_held_to_the_limit(make, name):
    parse(make(MAX_DEPTH - 1))
    with pytest.raises(ExprLimitError, match="nest"):
        parse(make(MAX_DEPTH + 1))


def test_deep_nesting_well_past_the_limit_fails_cleanly_not_with_a_recursion_error():
    with pytest.raises(ExprLimitError):
        parse("(" * 1900 + "1" + ")" * 1900)
    with pytest.raises(ExprLimitError):
        parse("-" * 3999 + "1")


def test_a_function_takes_at_most_the_argument_limit():
    parse("min(" + ", ".join(["1"] * MAX_ARGUMENTS) + ")")
    with pytest.raises(ExprLimitError, match="arguments"):
        parse("min(" + ", ".join(["1"] * (MAX_ARGUMENTS + 1)) + ")")


def test_every_error_is_an_expr_error():
    for kind in (ExprSyntaxError, ExprLimitError, ExprTypeError, ExprEvaluationError):
        assert issubclass(kind, ExprError)


def test_trees_are_immutable():
    expr = parse("1 + 2")
    assert isinstance(expr.root, Binary)
    with pytest.raises(AttributeError):
        expr.root.op = "-"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        Num(D(1)).value = D(2)  # type: ignore[misc]
