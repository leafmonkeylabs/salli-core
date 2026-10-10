"""
Compile a rule set into an ordered graph of lines, and evaluate it.

`compile_rule_set` does everything that doesn't depend on the taxpayer's
numbers, once: it expands the building blocks into lines, parses every
expression, resolves every reference (to a role, a question, another line or a
band table), rejects cycles, checks types and puts the lines in an order where
each comes after everything it uses. Every problem is collected, with a path
into the document, before `RuleSetError` is raised.

`evaluate` then applies the compiled rules to one taxpayer's role totals and
answers. It can only fail on the inputs or on arithmetic (a division by zero an
author didn't guard against, say); the result lists every line with the
expression behind it, so each figure can be explained.

The engine never calls a model and never computes anything a rule set didn't
say: it is the deterministic half of "an agent may write rules; only Salli's
engine applies them".
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal, cast

from pydantic import ValidationError

from salli.domain.taxrules.arith import BandTable, Rounding, decimal_context, normalized_str
from salli.domain.taxrules.blocks import Schedule, derived_keys, expand, expression_fields
from salli.domain.taxrules.common import Problem, RuleSetError, join_path, parse_decimal
from salli.domain.taxrules.expr import (
    Call,
    Expr,
    ExprError,
    ExprEvaluationError,
    ExprType,
    Num,
    Ref,
    Scope,
    Str,
    Value,
    parse,
    reference_nodes,
    type_of,
    unparse,
    walk,
)
from salli.domain.taxrules.expr import (
    evaluate as evaluate_expr,
)
from salli.domain.taxrules.schema import (
    RuleSet,
    answer_value,
    check_document,
    load,
    schema_problems,
)

#: Lines after the blocks are expanded. Bounds the work one document can ask
#: for (each schedule adds two lines per band).
MAX_COMPILED_LINES = 2_000


class RuleSetEvaluationError(RuleSetError):
    """Inputs that don't fit the rule set, or arithmetic that failed."""


# ── compiled form ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CompiledLine:
    key: str
    label: str
    expr: Expr
    source: str | None
    #: For a credit block's line: whether the credit is refundable. None for
    #: every other line.
    refundable: bool | None
    #: Where it came from: `lines[3].expr`, or `blocks[2]` for a block's line.
    path: str
    #: The block type it was compiled from, or None for a declared line.
    block: str | None


@dataclass(frozen=True)
class CompiledField:
    id: str
    label: str
    expr: Expr


@dataclass(frozen=True)
class CompiledForm:
    key: str
    label: str
    fields: tuple[CompiledField, ...]


@dataclass(frozen=True)
class CompiledRuleSet:
    document: RuleSet
    #: Every line, each after the lines it uses (see `_order`).
    lines: tuple[CompiledLine, ...]
    net: Expr
    rounding: Rounding | None
    tables: Mapping[str, BandTable]
    forms: tuple[CompiledForm, ...]
    content_hash: str

    @property
    def currency(self) -> str:
        return self.document.currency

    def line(self, key: str) -> CompiledLine:
        for line in self.lines:
            if line.key == key:
                return line
        raise KeyError(key)


# ── result ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ComputedLine:
    key: str
    label: str
    amount: Decimal
    #: The expression the amount came from.
    expr: str
    source: str | None
    refundable: bool | None
    path: str


@dataclass(frozen=True)
class RuleSetResult:
    country: str
    year: str
    currency: str
    #: The rule set's `content_hash`: which rules produced this.
    content_hash: str
    lines: tuple[ComputedLine, ...]
    #: `result.net` after the result's rounding: owed when positive, a refund
    #: when negative.
    net: Decimal
    net_expr: str
    tax_payable: Decimal
    refund_due: Decimal
    #: Each form's field values, by form key then field id.
    forms: Mapping[str, Mapping[str, Decimal | bool]]

    def line(self, key: str) -> ComputedLine:
        for line in self.lines:
            if line.key == key:
                return line
        raise KeyError(key)

    def amount(self, key: str) -> Decimal:
        return self.line(key).amount


# ── content hash ───────────────────────────────────────────────────────────────


def _canonical(value: Any) -> Any:
    if isinstance(value, Decimal):
        return normalized_str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in cast(dict[Any, Any], value).items()}
    if isinstance(value, list | tuple):
        return [_canonical(v) for v in cast(list[Any], value)]
    return value


def content_hash(doc: RuleSet | Mapping[str, Any]) -> str:
    """sha256 (hex) of the document's canonical JSON: the validated document
    with every field present, keys sorted, no whitespace, and decimals as their
    shortest string ("0.150" and "0.15" hash alike). Two spellings of the same
    rules hash the same; any change to them doesn't."""
    data = _canonical(load(doc).model_dump(mode="python", by_alias=True))
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── compiling ──────────────────────────────────────────────────────────────────

Want = Literal["number", "value"]


@dataclass
class _Source:
    """One expression an author wrote, where it is, and what it must produce."""

    path: str
    expr: Expr
    want: Want


def _expr_problem(path: str, error: ExprError) -> Problem:
    return Problem(path, str(error), error.snippet)


def compile_rule_set(doc: RuleSet | Mapping[str, Any]) -> CompiledRuleSet:
    """Compile `doc`, or raise `RuleSetError` with every problem in it."""
    try:
        doc = load(doc)
    except ValidationError as error:
        raise RuleSetError(schema_problems(error)) from None

    problems = check_document(doc)
    tables = {key: spec.to_table() for key, spec in doc.band_tables.items()}
    authored: list[_Source] = []

    def parse_at(text: str, path: str, want: Want) -> Expr | None:
        try:
            expr = parse(text)
        except ExprError as error:
            problems.append(_expr_problem(path, error))
            return None
        authored.append(_Source(path, expr, want))
        return expr

    # Blocks first, then declared lines: this is also the order lines are
    # listed in when nothing forces otherwise.
    lines: dict[str, CompiledLine] = {}
    known: set[str] = set()  # every line key, including those of broken blocks

    def add(line: CompiledLine) -> None:
        # A duplicate key is already a problem (check_document); keep the first.
        lines.setdefault(line.key, line)

    for i, block in enumerate(doc.blocks):
        parsed: dict[str, Expr] = {}
        for name, text in expression_fields(block).items():
            expr = parse_at(text, join_path("blocks", i, name), "number")
            if expr is not None:
                parsed[name] = expr
        table = None
        if isinstance(block, Schedule):
            table = tables.get(block.table)
            if table is None:
                problems.append(
                    Problem(
                        join_path("blocks", i, "table"), f"There is no band table {block.table!r}"
                    )
                )
        known.update(derived_keys(block, table))
        if len(parsed) < len(expression_fields(block)) or (
            isinstance(block, Schedule) and table is None
        ):
            continue
        path = join_path("blocks", i)
        for draft in expand(block, parsed, table):
            try:
                # Re-parsed from its canonical text so positions in errors
                # point into the text that's shown.
                expr = parse(unparse(parse(draft.text)))
            except ExprError as error:
                problems.append(
                    Problem(
                        path,
                        f"Line {draft.key} that this block compiles to is too large ({error.message}); "
                        "move part of the expression into a line of its own",
                    )
                )
                continue
            add(
                CompiledLine(
                    draft.key, draft.label, expr, draft.source, draft.refundable, path, block.type
                )
            )

    for i, spec in enumerate(doc.lines):
        known.add(spec.key)
        path = join_path("lines", i, "expr")
        expr = parse_at(spec.expr, path, "number")
        if expr is not None:
            add(CompiledLine(spec.key, spec.label, expr, spec.source, None, path, None))

    net = parse_at(doc.result.net, "result.net", "number")
    forms: list[CompiledForm] = []
    for i, form in enumerate(doc.forms):
        fields: list[CompiledField] = []
        for j, field in enumerate(form.fields):
            expr = parse_at(field.value, join_path("forms", i, "fields", j, "value"), "value")
            if expr is not None:
                fields.append(CompiledField(field.id, field.label, expr))
        forms.append(CompiledForm(form.key, form.label, tuple(fields)))

    if len(known) > MAX_COMPILED_LINES:
        problems.append(
            Problem(
                "$",
                f"The rule set compiles to {len(known)} lines; at most {MAX_COMPILED_LINES} are allowed",
            )
        )

    env: dict[Ref, ExprType] = {Ref("role", r.key): ExprType.NUMBER for r in doc.roles}
    for q in doc.questions:
        env[Ref("answer", q.key)] = {
            "number": ExprType.NUMBER,
            "boolean": ExprType.BOOLEAN,
            "choice": ExprType.STRING,
        }[q.type]
    env.update({Ref("line", key): ExprType.NUMBER for key in known})

    for source in authored:
        problems.extend(_check(source, env, tables, doc))
    # A block's lines are its authored expressions put together, so they check
    # out when those do; checked again anyway, as the engine's own guard.
    for line in lines.values():
        if line.block is not None:
            problems.extend(_check(_Source(line.path, line.expr, "number"), env, tables, doc))

    problems.extend(_cycles(lines))

    if problems or net is None:
        raise RuleSetError(problems)

    return CompiledRuleSet(
        document=doc,
        lines=_order(lines),
        net=net,
        rounding=doc.result.round.to_rounding() if doc.result.round else None,
        tables=tables,
        forms=tuple(forms),
        content_hash=content_hash(doc),
    )


def _check(
    source: _Source, env: Mapping[Ref, ExprType], tables: Mapping[str, BandTable], doc: RuleSet
) -> list[Problem]:
    """Unknown references, band tables and choices in one expression, then its
    type (only once everything it names exists)."""
    found: list[Problem] = []
    expr = source.expr

    def at(node_pos: int, message: str) -> Problem:
        return _expr_problem(source.path, ExprError(message, expr.text, node_pos))

    for ref in reference_nodes(expr):
        if ref not in env:
            what = {"role": "role", "answer": "question", "line": "line"}[ref.namespace]
            found.append(at(ref.pos, f"Unknown {what}: {ref}"))
    questions = {q.key: q for q in doc.questions}
    for node in walk(expr):
        if not isinstance(node, Call):
            continue
        if node.name in ("bands", "band_amount"):
            name = node.args[1]
            assert isinstance(name, Str)
            table = tables.get(name.value)
            if table is None:
                found.append(at(name.pos, f"There is no band table {name.value!r}"))
            elif node.name == "band_amount":
                index = node.args[2]
                assert isinstance(index, Num)
                if index.value > len(table.bands):
                    found.append(
                        at(
                            index.pos,
                            f"Band table {name.value!r} has {len(table.bands)} bands, not {index.value}",
                        )
                    )
        elif node.name == "choice":
            answer = node.args[0]
            assert isinstance(answer, Ref)
            question = questions.get(answer.key)
            if question is None or question.type != "choice" or not question.choices:
                continue  # an unknown reference, or a type error, reported elsewhere
            listed = [o.value for o in node.args[1::2] if isinstance(o, Str)]
            for option in node.args[1::2]:
                if isinstance(option, Str) and option.value not in question.choices:
                    found.append(
                        at(option.pos, f"{option.value!r} is not one of {answer}'s choices")
                    )
            missing = [c for c in question.choices if c not in listed]
            if missing:
                found.append(
                    at(
                        node.pos,
                        f"choice() must cover every choice of {answer}; it leaves out {', '.join(missing)}",
                    )
                )
    if found:
        return found
    try:
        produced = type_of(expr, env)
    except ExprError as error:
        return [_expr_problem(source.path, error)]
    if source.want == "number" and produced is not ExprType.NUMBER:
        return [
            _expr_problem(
                source.path,
                ExprError(f"This must be a number, not a {produced.value}", expr.text, 0),
            )
        ]
    return []


def _cycles(lines: Mapping[str, CompiledLine]) -> list[Problem]:
    """A problem for every group of lines that depend on each other, naming
    the cycle (`a -> b -> a`). Tarjan's algorithm, iteratively, so a long chain
    of lines can't exhaust the stack."""
    graph = {
        key: [r.key for r in reference_nodes(line.expr) if r.namespace == "line" and r.key in lines]
        for key, line in lines.items()
    }
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[list[str]] = []
    counter = 0
    for root in graph:
        if root in index:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, i = work.pop()
            if i == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            successors = graph[node]
            if i < len(successors):
                work.append((node, i + 1))
                nxt = successors[i]
                if nxt not in index:
                    work.append((nxt, 0))
                elif nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
                continue
            if low[node] == index[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(component)
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

    order = {key: n for n, key in enumerate(lines)}
    problems: list[Problem] = []
    for component in components:
        members = set(component)
        start = min(component, key=order.__getitem__)
        if len(component) == 1 and start not in graph[start]:
            continue
        path = _cycle_path(graph, members, start)
        problems.append(
            Problem(
                lines[start].path,
                "These lines depend on each other in a cycle: " + " -> ".join(path),
            )
        )
    problems.sort(key=lambda p: p.path)
    return problems


def _cycle_path(graph: Mapping[str, list[str]], members: set[str], start: str) -> list[str]:
    """The shortest way from `start` back to itself within one cycle."""
    previous: dict[str, str] = {}
    frontier = [start]
    while frontier:
        following: list[str] = []
        for node in frontier:
            for nxt in graph[node]:
                if nxt not in members:
                    continue
                if nxt == start:
                    path = [node]
                    while path[-1] != start:
                        path.append(previous[path[-1]])
                    return [*reversed(path), start]
                if nxt not in previous:
                    previous[nxt] = node
                    following.append(nxt)
        frontier = following
    return [start, start]  # unreachable for a real cycle


def _order(lines: Mapping[str, CompiledLine]) -> tuple[CompiledLine, ...]:
    """Lines in declaration order, except that a line's dependencies come
    first: each line is placed when it, or a later line needing it, comes up.
    Deterministic, and it keeps an author's order wherever it can."""
    placed: dict[str, None] = {}
    for root in lines:
        work: list[tuple[str, bool]] = [(root, False)]
        while work:
            key, expanded = work.pop()
            if key in placed:
                continue
            if expanded:
                placed[key] = None
                continue
            work.append((key, True))
            deps = [r.key for r in reference_nodes(lines[key].expr) if r.namespace == "line"]
            work.extend((d, False) for d in reversed(deps) if d not in placed)
    return tuple(lines[key] for key in placed)


# ── evaluating ─────────────────────────────────────────────────────────────────


def evaluate(
    compiled: CompiledRuleSet,
    roles: Mapping[str, Decimal],
    answers: Mapping[str, Value] | None = None,
) -> RuleSetResult:
    """Apply `compiled` to one taxpayer's role totals and answers.

    A role with no total is zero. A question with no answer takes its default,
    and is an error without one. Anything not declared by the rule set is an
    error rather than quietly ignored.
    """
    doc = compiled.document
    answers = answers or {}
    problems: list[Problem] = []
    values: dict[Ref, Value] = {}

    declared_roles = {r.key for r in doc.roles}
    for key in roles:
        if key not in declared_roles:
            problems.append(
                Problem(join_path("roles", key), f"{key!r} is not a role of this rule set")
            )
    for key in sorted(declared_roles):
        raw: object = roles.get(key, Decimal(0))
        # Callers outside the type checker may pass a float: refuse it.
        if not isinstance(raw, Decimal):  # pyright: ignore[reportUnnecessaryIsInstance]
            problems.append(Problem(join_path("roles", key), "A role total must be a Decimal"))
            continue
        try:
            values[Ref("role", key)] = parse_decimal(raw)
        except ValueError as error:
            problems.append(Problem(join_path("roles", key), str(error)))

    questions = {q.key: q for q in doc.questions}
    for key in answers:
        if key not in questions:
            problems.append(
                Problem(join_path("answers", key), f"{key!r} is not a question of this rule set")
            )
    for key, question in questions.items():
        try:
            if key in answers:
                values[Ref("answer", key)] = answer_value(question, answers[key])
            elif question.default is not None:
                default = question.typed_default()
                assert default is not None
                values[Ref("answer", key)] = default
            else:
                problems.append(
                    Problem(
                        join_path("answers", key), f"{question.label}: no answer, and no default"
                    )
                )
        except ValueError as error:
            problems.append(Problem(join_path("answers", key), str(error)))
    if problems:
        raise RuleSetEvaluationError(problems)

    scope = Scope(values, compiled.tables)

    def run(expr: Expr, path: str, label: str) -> Decimal | bool:
        try:
            return evaluate_expr(expr, scope)
        except ExprEvaluationError as error:
            raise RuleSetEvaluationError(
                [Problem(path, f"{label}: {error}", error.snippet)]
            ) from None

    computed: list[ComputedLine] = []
    for line in compiled.lines:
        amount = run(line.expr, line.path, f"line {line.key}")
        assert isinstance(amount, Decimal), "lines are type-checked to be numbers"
        values[Ref("line", line.key)] = amount
        computed.append(
            ComputedLine(
                line.key,
                line.label,
                amount,
                unparse(line.expr),
                line.source,
                line.refundable,
                line.path,
            )
        )

    net = run(compiled.net, "result.net", "the result")
    assert isinstance(net, Decimal), "the result is type-checked to be a number"
    with decimal_context():
        if compiled.rounding is not None:
            net = compiled.rounding.apply(net)
        payable = net if net > 0 else Decimal(0)
        refund = -net if net < 0 else Decimal(0)

    forms: dict[str, dict[str, Decimal | bool]] = {}
    for i, form in enumerate(compiled.forms):
        forms[form.key] = {
            field.id: run(
                field.expr, join_path("forms", i, "fields", j, "value"), f"form field {field.id}"
            )
            for j, field in enumerate(form.fields)
        }

    return RuleSetResult(
        country=doc.jurisdiction.country,
        year=doc.year.label,
        currency=doc.currency,
        content_hash=compiled.content_hash,
        lines=tuple(computed),
        net=net,
        net_expr=unparse(compiled.net),
        tax_payable=payable,
        refund_due=refund,
        forms=forms,
    )
