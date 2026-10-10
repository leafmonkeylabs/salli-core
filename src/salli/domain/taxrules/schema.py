"""
The rule-set document, `salli.tax/1`: its models, the checks that span more
than one field, and its JSON Schema.

A document describes one jurisdiction's tax for one year: what the ledger and
the user supply (`roles`, `questions`), how the tax is worked out (`band_tables`,
`blocks`, `lines`, `result`), what else a return needs (`deadlines`, `forms`,
`suggested_accounts`), where each figure came from (`sources`), and worked
examples (`examples`) that must all come out right before Salli computes with
it. docs/taxrules.md describes it for authors.

The pydantic models check each field on its own. `check_document` then checks
what spans fields (keys are unique, a `source` names a declared source, an
example's inputs are declared and well typed), returning every problem with a
path rather than stopping at the first.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, ValidationError, model_validator

from salli.domain.taxrules.arith import Band, BandTable
from salli.domain.taxrules.blocks import Block
from salli.domain.taxrules.common import (
    CountryCode,
    CurrencyCode,
    ExprText,
    Figure,
    IsoDate,
    Key,
    Label,
    LineKey,
    Model,
    NonNegativeFigure,
    Problem,
    Rate,
    RoleKey,
    RoundingSpec,
    StringOrBoolean,
    Text,
    Url,
    join_path,
    parse_decimal,
)
from salli.domain.taxrules.expr import Value

SCHEMA_ID = "salli.tax/1"

#: A schedule's total line adds up every band, and an expression may nest at
#: most 50 deep, so a table is held well under that. Real tables have a dozen.
MAX_BANDS = 40


class Jurisdiction(Model):
    country: CountryCode
    region: Label | None = None


class TaxYear(Model):
    label: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    start: IsoDate
    end: IsoDate

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.start >= self.end:
            raise ValueError("the year must start before it ends")
        return self


class Source(Model):
    id: Key
    url: Url
    title: Label
    retrieved: IsoDate | None = None


class Role(Model):
    """A ledger total the rules read, by account `tax_role`."""

    key: RoleKey
    kind: Literal["income", "deduction", "withholding", "other"]
    label: Label
    description: Text | None = None


class Question(Model):
    """Something the user answers (their filing status, say)."""

    key: Key
    label: Label
    type: Literal["number", "boolean", "choice"]
    choices: Annotated[list[Key], Field(min_length=1, max_length=50)] | None = None
    #: A decimal string for a number, true/false for a boolean, one of the
    #: choices for a choice. Without one, the answer is required.
    default: StringOrBoolean | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.type == "choice":
            if not self.choices:
                raise ValueError("a choice question lists its choices")
            if len(set(self.choices)) != len(self.choices):
                raise ValueError("a choice is listed twice")
        elif self.choices is not None:
            raise ValueError("only a choice question has choices")
        if self.default is not None:
            self.typed_default()  # raises ValueError when it doesn't fit
        return self

    def typed_default(self) -> Value | None:
        if self.default is None:
            return None
        return answer_value(self, self.default)


def answer_value(question: Question, raw: object) -> Value:
    """`raw` as an answer to `question`, or ValueError saying what's expected."""
    if question.type == "boolean":
        if isinstance(raw, bool):
            return raw
        raise ValueError(f"{question.key} is a yes/no question: answer true or false")
    if question.type == "choice":
        if isinstance(raw, str) and question.choices and raw in question.choices:
            return raw
        raise ValueError(f"{question.key} is one of: {', '.join(question.choices or [])}")
    return parse_decimal(raw)


class BandSpec(Model):
    #: The band's ceiling, counted from zero; null for the last band.
    upto: Figure | None
    rate: Rate


class BandTableSpec(Model):
    label: Label | None = None
    bands: Annotated[list[BandSpec], Field(min_length=1, max_length=MAX_BANDS)]
    #: Rounds each band's tax on its own before the bands are added.
    round: RoundingSpec | None = None
    source: Key | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> Self:
        if self.bands[-1].upto is not None:
            raise ValueError(
                'the last band has no ceiling ("upto": null); give it a rate of "0" to '
                "stop taxing above the one before"
            )
        previous = Decimal(0)
        for n, band in enumerate(self.bands[:-1], start=1):
            if band.upto is None:
                raise ValueError(f"only the last band may have no ceiling, but band {n} has none")
            if band.upto <= previous:
                raise ValueError(
                    f"band ceilings must be positive and ascend; band {n}'s ({band.upto}) "
                    f"isn't above {previous}"
                )
            previous = band.upto
        return self

    def to_table(self) -> BandTable:
        return BandTable(
            tuple(Band(b.upto, b.rate) for b in self.bands),
            self.round.to_rounding() if self.round else None,
        )


class LineSpec(Model):
    key: Key
    label: Label
    expr: ExprText
    source: Key | None = None


class ResultSpec(Model):
    """`net` is what the taxpayer owes after every credit, negative when they
    are owed a refund. It is rounded with `round`, then split into a payable
    amount and a refund."""

    net: ExprText
    round: RoundingSpec | None = None


class Deadline(Model):
    key: Key
    label: Label
    date: IsoDate
    source: Key | None = None


class SuggestedAccount(Model):
    code: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$", max_length=20)]
    name: Label
    type: Literal["asset", "liability", "equity", "income", "expense"]
    tax_role: RoleKey | None = None


class FormField(Model):
    id: Key
    label: Label
    value: ExprText


class Form(Model):
    key: Key
    label: Label
    fields: Annotated[list[FormField], Field(min_length=1, max_length=500)]
    instructions: Text | None = None
    url: Url | None = None


class ExampleExpected(Model):
    payable: NonNegativeFigure | None = None
    refund: NonNegativeFigure | None = None
    lines: Annotated[dict[LineKey, Figure], Field(max_length=2_000)] | None = None

    @model_validator(mode="after")
    def _says_something(self) -> Self:
        if self.payable is None and self.refund is None and not self.lines:
            raise ValueError("an example expects a payable amount, a refund or some lines")
        return self


class Example(Model):
    name: Label
    source: Key | None = None
    #: Role totals (decimal strings) and answers, by role or question key.
    inputs: Annotated[dict[Key, StringOrBoolean], Field(max_length=500)] = Field(
        default_factory=dict[str, str | bool]
    )
    expected: ExampleExpected


class RuleSet(Model):
    schema_: Literal["salli.tax/1"] = Field(alias="schema")
    jurisdiction: Jurisdiction
    year: TaxYear
    currency: CurrencyCode
    sources: Annotated[list[Source], Field(max_length=200)] = Field(default_factory=list[Source])
    roles: Annotated[list[Role], Field(max_length=200)] = Field(default_factory=list[Role])
    questions: Annotated[list[Question], Field(max_length=100)] = Field(
        default_factory=list[Question]
    )
    band_tables: Annotated[dict[Key, BandTableSpec], Field(max_length=50)] = Field(
        default_factory=dict[str, BandTableSpec]
    )
    blocks: Annotated[list[Block], Field(max_length=500)] = Field(default_factory=list[Block])
    lines: Annotated[list[LineSpec], Field(max_length=1_000)] = Field(
        default_factory=list[LineSpec]
    )
    result: ResultSpec
    deadlines: Annotated[list[Deadline], Field(max_length=100)] = Field(
        default_factory=list[Deadline]
    )
    suggested_accounts: Annotated[list[SuggestedAccount], Field(max_length=200)] = Field(
        default_factory=list[SuggestedAccount]
    )
    forms: Annotated[list[Form], Field(max_length=50)] = Field(default_factory=list[Form])
    examples: Annotated[list[Example], Field(max_length=200)] = Field(default_factory=list[Example])


# ── checks across fields ───────────────────────────────────────────────────────


def _duplicates(problems: list[Problem], items: list[tuple[str, str]], what: str) -> None:
    """`items` is (path, key); flag every key seen before."""
    seen: dict[str, str] = {}
    for path, key in items:
        if key in seen:
            problems.append(Problem(path, f"{what} {key!r} is already used at {seen[key]}"))
        else:
            seen[key] = path


def check_document(doc: RuleSet) -> list[Problem]:
    """Every cross-field problem in `doc`: duplicate keys, a `source` that names
    no declared source, an account role that isn't declared, an example input
    that isn't a role or a question or doesn't fit it."""
    problems: list[Problem] = []

    _duplicates(
        problems,
        [(join_path("sources", i, "id"), s.id) for i, s in enumerate(doc.sources)],
        "Source id",
    )
    _duplicates(
        problems, [(join_path("roles", i, "key"), r.key) for i, r in enumerate(doc.roles)], "Role"
    )
    _duplicates(
        problems,
        [(join_path("questions", i, "key"), q.key) for i, q in enumerate(doc.questions)],
        "Question",
    )
    # An example's inputs name roles and questions by key alone, so the two
    # can't share one.
    roles = {r.key for r in doc.roles}
    for i, q in enumerate(doc.questions):
        if q.key in roles:
            problems.append(
                Problem(
                    join_path("questions", i, "key"),
                    f"{q.key!r} is also a role's key; keep them apart",
                )
            )
    # Blocks and lines share one namespace: each block's key is a line too.
    _duplicates(
        problems,
        [(join_path("blocks", i, "key"), b.key) for i, b in enumerate(doc.blocks)]
        + [(join_path("lines", i, "key"), ln.key) for i, ln in enumerate(doc.lines)],
        "Line key",
    )
    _duplicates(
        problems,
        [(join_path("deadlines", i, "key"), d.key) for i, d in enumerate(doc.deadlines)],
        "Deadline",
    )
    _duplicates(
        problems,
        [
            (join_path("suggested_accounts", i, "code"), a.code)
            for i, a in enumerate(doc.suggested_accounts)
        ],
        "Account code",
    )
    _duplicates(
        problems, [(join_path("forms", i, "key"), f.key) for i, f in enumerate(doc.forms)], "Form"
    )
    for i, form in enumerate(doc.forms):
        _duplicates(
            problems,
            [
                (join_path("forms", i, "fields", j, "id"), fld.id)
                for j, fld in enumerate(form.fields)
            ],
            "Field id",
        )
    _duplicates(
        problems,
        [(join_path("examples", i, "name"), e.name) for i, e in enumerate(doc.examples)],
        "Example",
    )

    sources = {s.id for s in doc.sources}
    cited: list[tuple[str, str | None]] = [
        (join_path("band_tables", k, "source"), t.source) for k, t in doc.band_tables.items()
    ]
    cited += [(join_path("blocks", i, "source"), b.source) for i, b in enumerate(doc.blocks)]
    cited += [(join_path("lines", i, "source"), ln.source) for i, ln in enumerate(doc.lines)]
    cited += [(join_path("deadlines", i, "source"), d.source) for i, d in enumerate(doc.deadlines)]
    cited += [(join_path("examples", i, "source"), e.source) for i, e in enumerate(doc.examples)]
    for path, source in cited:
        if source is not None and source not in sources:
            problems.append(Problem(path, f"No source has the id {source!r}"))

    for i, account in enumerate(doc.suggested_accounts):
        if account.tax_role is not None and account.tax_role not in roles:
            problems.append(
                Problem(
                    join_path("suggested_accounts", i, "tax_role"),
                    f"{account.tax_role!r} is not one of the rule set's roles",
                )
            )

    for i, example in enumerate(doc.examples):
        problems.extend(example_inputs(doc, example, join_path("examples", i, "inputs"))[2])
    return problems


def example_inputs(
    doc: RuleSet, example: Example, path: str
) -> tuple[dict[str, Decimal], dict[str, Value], list[Problem]]:
    """An example's inputs split into role totals and answers, typed, with a
    problem for each one that isn't declared or doesn't fit."""
    questions = {q.key: q for q in doc.questions}
    roles = {r.key for r in doc.roles}
    totals: dict[str, Decimal] = {}
    answers: dict[str, Value] = {}
    problems: list[Problem] = []
    for key, raw in example.inputs.items():
        where = join_path(path, key)
        try:
            if key in roles:
                totals[key] = parse_decimal(raw)
            elif key in questions:
                answers[key] = answer_value(questions[key], raw)
            else:
                problems.append(Problem(where, f"{key!r} is neither a role nor a question"))
        except ValueError as error:
            problems.append(Problem(where, str(error)))
    return totals, answers, problems


# ── JSON Schema ────────────────────────────────────────────────────────────────


def rule_set_json_schema() -> dict[str, Any]:
    """The document's JSON Schema (Draft 2020-12), for agents writing one.

    It describes the shape. The checks that span fields (unique keys, declared
    sources, expressions that compile, examples that pass) are the validator's.
    """
    schema = RuleSet.model_json_schema(by_alias=True, mode="validation")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"Salli tax rule set ({SCHEMA_ID})",
        **schema,
    }


_BLOCK_TYPES = {"relief", "deduction", "capped_share", "schedule", "final_rate", "credit"}


def schema_problems(error: ValidationError) -> list[Problem]:
    """pydantic's errors as problems, with paths people can follow."""
    problems: list[Problem] = []
    for err in error.errors(include_url=False):
        loc = list(err["loc"])
        # pydantic names the block type it tried after a block's index, and
        # marks a bad dict key with "[key]"; neither is part of the document.
        if len(loc) > 2 and loc[0] == "blocks" and loc[2] in _BLOCK_TYPES:
            del loc[2]
        message = str(err["msg"]).removeprefix("Value error, ")
        if loc and loc[-1] == "[key]":
            loc.pop()
            message = f"is not a valid key ({message})"
        elif err["type"] == "missing":
            message = "is required"
        elif err["type"] == "extra_forbidden":
            message = "is not a field here"
        problems.append(Problem(join_path(*loc), message))
    return problems


def load(data: Mapping[str, Any] | RuleSet) -> RuleSet:
    """`data` as a validated document (pydantic's ValidationError otherwise;
    `validate.validate` reports those as problems with paths)."""
    if isinstance(data, RuleSet):
        return data
    return RuleSet.model_validate(data)


__all__ = [
    "SCHEMA_ID",
    "BandSpec",
    "BandTableSpec",
    "Block",
    "Deadline",
    "Example",
    "ExampleExpected",
    "ExprText",
    "Form",
    "FormField",
    "Jurisdiction",
    "LineSpec",
    "Question",
    "ResultSpec",
    "Role",
    "RuleSet",
    "Source",
    "SuggestedAccount",
    "TaxYear",
    "answer_value",
    "check_document",
    "example_inputs",
    "load",
    "rule_set_json_schema",
    "schema_problems",
]
