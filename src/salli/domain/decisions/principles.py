"""
Principles: the user's own rules of thumb, as user data (`salli.principle/1`).

Salli doesn't decide what is wise; a principle is how a person says what
they want to hold to, and the only "should" Salli ever reports:

    {"schema": "salli.principle/1", "label": "Six months of essentials in cash",
     "check": "emergency_months >= 6"}
    {"schema": "salli.principle/1", "label": "Clear debt above 7% before investing",
     "check": "max_debt_rate_while_investing <= 0.07"}
    {"schema": "salli.principle/1", "label": "Never below 2,000 in checking",
     "check": "account_lowest >= 2000", "account": "<checking's id>"}

A check is an expression in the tax rules' safe language
(`domain/taxrules/expr.py`, in figure mode): figures by their plain names
(`figures.FIGURES`), numbers, comparisons, `and`, `or`, `not`, arithmetic,
`min`, `max`, `abs`, `clamp`, `round` and `if`. It must be true or false.
It is parsed by hand into a tree and evaluated by a small decimal
interpreter: never `eval`, and nothing a model computes.

Checking reports, for each option, whether it **keeps** or **breaks** each
principle, or that it **can't tell** (a figure it reads is missing, or the
arithmetic failed), with the figures it read. Never a score or a ranking.
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from salli.domain import canonical
from salli.domain.decisions import figures as figure_set
from salli.domain.taxrules.common import Problem
from salli.domain.taxrules.expr import (
    FIGURE,
    Call,
    Expr,
    ExprError,
    ExprEvaluationError,
    ExprType,
    Ref,
    Scope,
    evaluate,
    parse,
    reference_nodes,
    type_of,
    unparse,
    walk,
)

SCHEMA_ID = "salli.principle/1"

MAX_LABEL = 200
MAX_CHECK = 1000
MAX_NOTE = 2000
#: At most this many principles in use at once.
MAX_ACTIVE = 50

#: Functions with no place in a principle: they need a rule set's band
#: tables, or a question's answer.
_TAX_ONLY = {"bands", "band_amount", "choice"}

Status = Literal["keeps", "breaks", "unknown"]


class PrincipleError(ValueError):
    """A principle that can't be stored, with every problem found."""

    def __init__(self, problems: list[Problem] | tuple[Problem, ...]) -> None:
        self.problems = tuple(problems)
        shown = "; ".join(str(p) for p in self.problems[:5])
        super().__init__(f"{len(self.problems)} problem(s): {shown}")


@dataclass(frozen=True)
class Principle:
    """A principle as the user wrote it."""

    label: str
    check: str
    #: The cash account `account_lowest` reads, by id.
    account: str | None = None
    #: Why it matters to them, in their words.
    note: str | None = None


_TYPES: Mapping[Ref, ExprType] = {
    Ref(FIGURE, f.name): ExprType.BOOLEAN if f.kind == "boolean" else ExprType.NUMBER
    for f in figure_set.FIGURES
}


def _unknown(name: str) -> str:
    close = difflib.get_close_matches(name, list(figure_set.BY_NAME), n=1)
    hint = f" Did you mean {close[0]}?" if close else ""
    return (
        f"There is no figure {name!r}.{hint} The figures are listed by GET "
        "/v1/principles/figures (`salli principles figures`)."
    )


def compile_check(principle: Principle) -> Expr:
    """The principle's check, parsed and type-checked; PrincipleError with
    every problem found (each with a caret under the mistake) otherwise."""
    problems: list[Problem] = []
    text = principle.check
    if not text.strip():
        raise PrincipleError([Problem("check", "is empty: write one, like emergency_months >= 6")])
    if len(text) > MAX_CHECK:
        raise PrincipleError([Problem("check", f"may be at most {MAX_CHECK} characters")])
    try:
        expr = parse(text, figures=True)
    except ExprError as error:
        raise PrincipleError([Problem("check", error.message, error.snippet)]) from None

    for node in walk(expr):
        if isinstance(node, Call) and node.name in _TAX_ONLY:
            located = ExprError("", text, node.pos)
            problems.append(
                Problem(
                    "check",
                    f"{node.name}() belongs to tax rules, not to a principle",
                    located.snippet,
                )
            )
    named: set[str] = set()
    for ref in reference_nodes(expr):
        if ref.key in named:
            continue
        named.add(ref.key)
        if ref.key not in figure_set.BY_NAME:
            problems.append(
                Problem("check", _unknown(ref.key), ExprError("", text, ref.pos).snippet)
            )
    if problems:
        raise PrincipleError(problems)

    if "account_lowest" in named and not principle.account:
        problems.append(
            Problem(
                "account",
                "is required: account_lowest is the lowest of one account, so name the cash "
                "account it reads",
            )
        )
    if principle.account and "account_lowest" not in named:
        problems.append(
            Problem("account", "is only read by account_lowest, which the check doesn't use")
        )
    try:
        kind = type_of(expr, _TYPES)
    except ExprError as error:
        problems.append(Problem("check", error.message, error.snippet))
    else:
        if kind is not ExprType.BOOLEAN:
            problems.append(
                Problem(
                    "check",
                    "must be true or false, like emergency_months >= 6; this one is a "
                    f"{kind.value}",
                )
            )
    if problems:
        raise PrincipleError(problems)
    return expr


def validate(principle: Principle) -> Expr:
    """The principle's compiled check, after checking every field;
    PrincipleError with every problem found."""
    problems: list[Problem] = []
    label = principle.label.strip()
    if not label:
        problems.append(Problem("label", "is empty: say what the principle is, in a few words"))
    elif len(label) > MAX_LABEL:
        problems.append(Problem("label", f"may be at most {MAX_LABEL} characters"))
    if principle.note is not None and len(principle.note) > MAX_NOTE:
        problems.append(Problem("note", f"may be at most {MAX_NOTE} characters"))
    try:
        expr = compile_check(principle)
    except PrincipleError as error:
        raise PrincipleError([*problems, *error.problems]) from None
    if problems:
        raise PrincipleError(problems)
    return expr


def content_hash(principle: Principle) -> str:
    """A content hash of what the principle says: its label, its check (in
    its canonical text, so spacing doesn't change it) and its account."""
    expr = compile_check(principle)
    return canonical.digest(
        {
            "schema": SCHEMA_ID,
            "label": principle.label.strip(),
            "check": unparse(expr),
            "account": principle.account,
        }
    )


@dataclass(frozen=True)
class CheckResult:
    """Whether an option keeps a principle, breaks it, or can't tell; why;
    and the figures the check read (None where one is missing)."""

    status: Status
    reason: str
    figures: Mapping[str, figure_set.Value | None] = field(
        default_factory=dict[str, figure_set.Value | None]
    )


def _shown(name: str, value: figure_set.Value | None) -> str:
    text = figure_set.value_text(name, value)
    if isinstance(text, bool):
        return "true" if text else "false"
    return str(text)


def check(principle: Principle, expr: Expr, figures: figure_set.Figures) -> CheckResult:
    """`expr` (the principle's compiled check) over `figures`. Deterministic:
    the same figures always give the same result."""
    names = list(dict.fromkeys(ref.key for ref in reference_nodes(expr)))
    read: dict[str, figure_set.Value | None] = {
        name: figures.get(name, principle.account) for name in names
    }
    gaps = [
        f"{name}: {why}"
        for name in names
        if (why := figures.why_missing(name, principle.account)) is not None
    ]
    if gaps:
        return CheckResult("unknown", "Can't tell: " + "; ".join(gaps) + ".", read)
    scope = Scope({Ref(FIGURE, name): value for name, value in read.items() if value is not None})
    try:
        held = evaluate(expr, scope)
    except ExprEvaluationError as error:
        return CheckResult("unknown", f"Can't tell: {error.message}.", read)
    values = ", ".join(f"{name} is {_shown(name, value)}" for name, value in read.items())
    text = unparse(expr)
    if held is True:
        return CheckResult("keeps", f"{text} holds: {values}.", read)
    return CheckResult("breaks", f"{text} doesn't hold: {values}.", read)


def result_view(result: CheckResult) -> dict[str, object]:
    return {
        "status": result.status,
        "reason": result.reason,
        "figures": {
            name: figure_set.value_text(name, value) for name, value in result.figures.items()
        },
    }
