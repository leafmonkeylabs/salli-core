"""
Where one line of a computation came from.

An explanation is read off the compiled rules and the result, never worked
out: the line's amount and expression, every role, answer and other line the
expression refers to (each with the value it had), the band tables it applies,
the source the rule set cites for it, and the lines that use it in turn. That
is enough for anyone, an agent included, to say why a figure is what it is
("15% of the 20,000 left after the allowance") without doing arithmetic of
their own.

Pure: compiled rules, a result and its inputs in; an explanation out.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from salli.domain.taxrules.engine import CompiledRuleSet, RuleSetResult
from salli.domain.taxrules.expr import Call, Str, Value, reference_nodes, walk


class UnknownLine(LookupError):
    """No line with that key in this computation."""

    def __init__(self, key: str, available: list[str]) -> None:
        shown = ", ".join(available[:40]) + (" …" if len(available) > 40 else "")
        super().__init__(f"There is no line {key!r} in this computation. Lines: {shown}")
        self.key = key
        self.available = available


@dataclass(frozen=True)
class CitedSource:
    id: str
    url: str
    title: str
    retrieved: str | None


@dataclass(frozen=True)
class UsedRole:
    """A ledger total the line used: the accounts whose `tax_role` is `key`."""

    key: str
    label: str
    kind: str
    amount: Decimal


@dataclass(frozen=True)
class UsedAnswer:
    key: str
    label: str
    value: Value
    #: True when the user gave no answer and the question's default was used.
    default: bool


@dataclass(frozen=True)
class UsedLine:
    key: str
    label: str
    amount: Decimal
    expr: str


@dataclass(frozen=True)
class UsedTable:
    key: str
    label: str | None
    #: Each band's ceiling (None for the last) and rate, as the table lists them.
    bands: tuple[tuple[Decimal | None, Decimal], ...]
    source: CitedSource | None


@dataclass(frozen=True)
class LineExplanation:
    key: str
    label: str
    amount: Decimal
    expr: str
    #: Where in the document it was written: `lines[2].expr`, or `blocks[1]`.
    path: str
    #: The building block it was compiled from (`schedule`, `credit`, …), or
    #: None for a line the rule set declares itself.
    block: str | None
    #: For a credit: whether it is refundable.
    refundable: bool | None
    source: CitedSource | None
    roles: tuple[UsedRole, ...]
    answers: tuple[UsedAnswer, ...]
    lines: tuple[UsedLine, ...]
    tables: tuple[UsedTable, ...]
    #: The lines (and `result.net`) whose expressions use this one.
    used_by: tuple[str, ...]


def explain_line(
    compiled: CompiledRuleSet,
    result: RuleSetResult,
    key: str,
    *,
    roles: Mapping[str, Decimal],
    answers: Mapping[str, Value] | None = None,
) -> LineExplanation:
    """Explain line `key` of `result`, which `compiled` produced from `roles`
    and `answers` (the answers given; questions left out show their default).
    UnknownLine when the result has no such line."""
    doc = compiled.document
    answers = answers or {}
    try:
        line = compiled.line(key)
        computed = result.line(key)
    except KeyError:
        raise UnknownLine(key, [ln.key for ln in result.lines]) from None

    sources = {s.id: s for s in doc.sources}

    def cite(source_id: str | None) -> CitedSource | None:
        source = sources.get(source_id) if source_id else None
        if source is None:
            return None
        retrieved = source.retrieved.isoformat() if source.retrieved else None
        return CitedSource(source.id, str(source.url), source.title, retrieved)

    refs = list(dict.fromkeys(reference_nodes(line.expr)))  # each once, in order
    declared_roles = {r.key: r for r in doc.roles}
    questions = {q.key: q for q in doc.questions}

    used_roles = tuple(
        UsedRole(
            r.key,
            declared_roles[r.key].label,
            declared_roles[r.key].kind,
            roles.get(r.key, Decimal(0)),
        )
        for r in refs
        if r.namespace == "role" and r.key in declared_roles
    )
    used_answers: list[UsedAnswer] = []
    for r in refs:
        if r.namespace != "answer" or r.key not in questions:
            continue
        question = questions[r.key]
        if r.key in answers:
            used_answers.append(UsedAnswer(r.key, question.label, answers[r.key], False))
        else:
            default = question.typed_default()
            if default is not None:
                used_answers.append(UsedAnswer(r.key, question.label, default, True))
    used_lines = tuple(
        UsedLine(r.key, result.line(r.key).label, result.amount(r.key), result.line(r.key).expr)
        for r in refs
        if r.namespace == "line"
    )

    table_keys: list[str] = []
    for node in walk(line.expr):
        if isinstance(node, Call) and node.name in ("bands", "band_amount"):
            name = node.args[1]
            if isinstance(name, Str) and name.value not in table_keys:
                table_keys.append(name.value)
    tables = tuple(
        UsedTable(
            k,
            doc.band_tables[k].label,
            tuple((b.upto, b.rate) for b in compiled.tables[k].bands),
            cite(doc.band_tables[k].source),
        )
        for k in table_keys
        if k in doc.band_tables
    )

    used_by = [
        other.key
        for other in compiled.lines
        if any(r.namespace == "line" and r.key == key for r in reference_nodes(other.expr))
    ]
    if any(r.namespace == "line" and r.key == key for r in reference_nodes(compiled.net)):
        used_by.append("result.net")

    return LineExplanation(
        key=line.key,
        label=line.label,
        amount=computed.amount,
        expr=computed.expr,
        path=line.path,
        block=line.block,
        refundable=line.refundable,
        source=cite(line.source),
        roles=used_roles,
        answers=tuple(used_answers),
        lines=used_lines,
        tables=tables,
        used_by=tuple(used_by),
    )
