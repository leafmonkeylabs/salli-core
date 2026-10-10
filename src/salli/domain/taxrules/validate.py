"""
Everything an author (a person or an agent) needs to hear about a rule set.

`validate(doc)` runs a document through every check there is, in order:

1. it is JSON (no duplicate keys, no NaN) and matches the schema;
2. it compiles: every expression parses, every reference resolves, there are no
   cycles, and the types agree;
3. warnings: figures with no source, roles, questions or band tables declared
   but never used, non-refundable credits with no cap;
4. its worked examples: each runs through the engine, and every expected figure
   must match exactly. A mismatch says which figure, what was expected, what
   came out, and the expression that produced it.

`report.ok` only when there are no errors, there is at least one example, and
every example passes. That is the bar for computing with a rule set: the design
won't let one be activated without worked examples that come out right.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from salli.domain.taxrules.arith import normalized_str
from salli.domain.taxrules.blocks import CappedShare, Credit, FinalRate, expression_fields
from salli.domain.taxrules.common import Problem, RuleSetError, join_path
from salli.domain.taxrules.engine import (
    CompiledRuleSet,
    RuleSetEvaluationError,
    compile_rule_set,
    evaluate,
)
from salli.domain.taxrules.expr import Call, ExprError, Num, Ref, Str, parse, walk
from salli.domain.taxrules.schema import RuleSet, example_inputs, schema_problems

#: The largest document accepted, in bytes of UTF-8 JSON.
MAX_DOCUMENT_BYTES = 1_048_576


@dataclass(frozen=True)
class Mismatch:
    """One expected figure that came out differently."""

    #: "payable", "refund", or the line's key.
    key: str
    expected: Decimal
    got: Decimal
    #: The expression behind the figure (the result's `net` for payable and
    #: refund).
    expr: str

    def __str__(self) -> str:
        expected, got = normalized_str(self.expected), normalized_str(self.got)
        return f"{self.key}: expected {expected}, got {got} (from {self.expr})"


@dataclass(frozen=True)
class ExampleReport:
    name: str
    passed: bool
    mismatches: tuple[Mismatch, ...] = ()
    #: Why the example couldn't be run at all, when it couldn't.
    error: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    errors: tuple[Problem, ...]
    warnings: tuple[Problem, ...]
    examples: tuple[ExampleReport, ...]
    #: The document's content hash, once it matches the schema.
    content_hash: str | None = None

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.examples) and all(e.passed for e in self.examples)


class _DuplicateKey(Exception):
    def __init__(self, key: str) -> None:
        self.key = key


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            # json.loads would keep the last silently; an author meant one.
            raise _DuplicateKey(key)
        out[key] = value
    return out


def _constant(name: str) -> Any:
    raise ValueError(f"{name} is not a number JSON allows")


def _read(doc_json: str) -> tuple[Any, list[Problem]]:
    if len(doc_json.encode("utf-8", errors="replace")) > MAX_DOCUMENT_BYTES:
        return None, [Problem("$", f"The document is larger than {MAX_DOCUMENT_BYTES} bytes")]
    try:
        return json.loads(doc_json, object_pairs_hook=_object, parse_constant=_constant), []
    except _DuplicateKey as dup:
        return None, [Problem("$", f"The key {dup.key!r} appears twice in one object")]
    except json.JSONDecodeError as error:
        return None, [
            Problem("$", f"Not valid JSON: {error.msg} (line {error.lineno}, column {error.colno})")
        ]
    except (ValueError, RecursionError) as error:
        message = str(error) if isinstance(error, ValueError) else "it nests too deeply"
        return None, [Problem("$", f"Not valid JSON: {message}")]


def validate(doc_json: str | Mapping[str, Any]) -> ValidationReport:
    """Check a document (JSON text, or already-parsed JSON) and run its examples."""
    data: Any = doc_json
    if isinstance(doc_json, str):
        data, problems = _read(doc_json)
        if problems:
            return ValidationReport(tuple(problems), (), ())
    if not isinstance(data, Mapping):
        return ValidationReport((Problem("$", "A rule set is a JSON object"),), (), ())
    try:
        doc = RuleSet.model_validate(data)
    except ValidationError as error:
        return ValidationReport(tuple(schema_problems(error)), (), ())

    try:
        compiled = compile_rule_set(doc)
    except RuleSetError as error:
        return ValidationReport(error.problems, tuple(_warnings(doc, None)), ())

    errors: list[Problem] = []
    if not doc.examples:
        errors.append(
            Problem(
                "examples", "A rule set needs at least one worked example before it can be used"
            )
        )
    examples = [_run_example(compiled, i, errors) for i in range(len(doc.examples))]
    return ValidationReport(
        tuple(errors), tuple(_warnings(doc, compiled)), tuple(examples), compiled.content_hash
    )


def _run_example(compiled: CompiledRuleSet, i: int, errors: list[Problem]) -> ExampleReport:
    doc = compiled.document
    example = doc.examples[i]
    path = join_path("examples", i)
    totals, answers, problems = example_inputs(doc, example, join_path(path, "inputs"))
    if problems:  # also reported by compile_rule_set, so never reached
        return ExampleReport(example.name, False, error="; ".join(str(p) for p in problems))
    keys = {line.key for line in compiled.lines}
    unknown = [k for k in (example.expected.lines or {}) if k not in keys]
    for key in unknown:
        errors.append(
            Problem(join_path(path, "expected", "lines", key), f"There is no line {key!r}")
        )
    if unknown:
        return ExampleReport(
            example.name, False, error=f"It expects lines that don't exist: {', '.join(unknown)}"
        )
    try:
        result = evaluate(compiled, totals, answers)
    except RuleSetEvaluationError as error:
        return ExampleReport(example.name, False, error="; ".join(str(p) for p in error.problems))

    mismatches: list[Mismatch] = []
    expected = example.expected
    if expected.payable is not None and expected.payable != result.tax_payable:
        mismatches.append(
            Mismatch("payable", expected.payable, result.tax_payable, result.net_expr)
        )
    if expected.refund is not None and expected.refund != result.refund_due:
        mismatches.append(Mismatch("refund", expected.refund, result.refund_due, result.net_expr))
    for key, amount in (expected.lines or {}).items():
        line = result.line(key)
        if line.amount != amount:
            mismatches.append(Mismatch(key, amount, line.amount, line.expr))
    return ExampleReport(example.name, not mismatches, tuple(mismatches))


# ── warnings ───────────────────────────────────────────────────────────────────


def _has_figures(text: str) -> bool:
    """Whether an expression contains a number an author took from the law.
    0 and 1 are structure (`max(0, …)`), not figures."""
    try:
        expr = parse(text)
    except ExprError:
        return False
    return any(isinstance(n, Num) and n.value not in (0, 1) for n in walk(expr))


def _warnings(doc: RuleSet, compiled: CompiledRuleSet | None) -> list[Problem]:
    warnings: list[Problem] = []
    for key, table in doc.band_tables.items():
        if table.source is None:
            warnings.append(
                Problem(join_path("band_tables", key), "This table's figures have no source")
            )
    for i, block in enumerate(doc.blocks):
        figures = isinstance(block, FinalRate | CappedShare) or any(
            _has_figures(text) for text in expression_fields(block).values()
        )
        if figures and block.source is None:
            warnings.append(Problem(join_path("blocks", i), "This block's figures have no source"))
        if isinstance(block, Credit) and not block.refundable and block.cap is None:
            warnings.append(
                Problem(
                    join_path("blocks", i),
                    "A non-refundable credit with no cap can reduce the tax below zero and create a "
                    "refund; cap it at the tax it may reduce",
                )
            )
    for i, line in enumerate(doc.lines):
        if line.source is None and _has_figures(line.expr):
            warnings.append(Problem(join_path("lines", i), "This line's figures have no source"))
    for i, deadline in enumerate(doc.deadlines):
        if deadline.source is None:
            warnings.append(Problem(join_path("deadlines", i), "This deadline has no source"))

    if compiled is None:
        return warnings
    expressions = [line.expr for line in compiled.lines] + [compiled.net]
    expressions += [f.expr for form in compiled.forms for f in form.fields]
    used: set[Ref] = set()
    tables: set[str] = set()
    for expr in expressions:
        for node in walk(expr):
            if isinstance(node, Ref):
                used.add(node)
            elif isinstance(node, Call) and node.name in ("bands", "band_amount"):
                name = node.args[1]
                assert isinstance(name, Str)
                tables.add(name.value)
    for i, role in enumerate(doc.roles):
        if Ref("role", role.key) not in used:
            warnings.append(Problem(join_path("roles", i), f"Role {role.key!r} is never used"))
    for i, question in enumerate(doc.questions):
        if Ref("answer", question.key) not in used:
            warnings.append(
                Problem(join_path("questions", i), f"Question {question.key!r} is never used")
            )
    for key in doc.band_tables:
        if key not in tables:
            warnings.append(
                Problem(join_path("band_tables", key), f"Band table {key!r} is never used")
            )
    return warnings
