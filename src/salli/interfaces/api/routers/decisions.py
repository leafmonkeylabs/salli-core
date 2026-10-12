"""
Decisions — `/v1/decisions`: the decision journal and its reviews.

When a person decides, Salli records it (docs/decisions.md): the question,
the options as scenario snapshots (Salli runs each `salli.scenario/1`
document itself; the client never supplies a figure), the principles'
checks, the option chosen, the person's reasons in their words, their
agent's summary if any (marked as the agent's), and a review date. An entry
is a self-describing document (`salli.decision/1`) with a content hash.

The journal is append-only: there is no route that edits or deletes an
entry, a note or a review. Notes (`POST .../notes`) and reviews
(`POST .../review`) are appended beside the entry, each naming its hash.
Every read hashes the documents again (`verified`), and the documents come
back exactly as recorded, so anyone can recompute the hash.

From the review date on, `GET /v1/decisions/reviews` lists what is due,
each with what the chosen option projected against what happened, and
`POST /v1/decisions/{id}/review` appends the person's reflection with that
comparison. The journal exports as JSON (every document and hash) or
Markdown.

Templates (`salli.template/1`, docs/templates.md) are common decisions as a
few typed questions: `GET /v1/decisions/templates` lists them, `GET
/v1/decisions/templates/{id}` gives one's questions (each default as it
stands for the caller) and the answers' JSON Schema, and `POST
/v1/decisions/start` builds the options from the answers and runs them:
the comparison, the principles' checks and what recording needs. It
records nothing, and ranks nothing. Answers Salli can't use are a 422
whose `detail` lists each problem with its path (`answers.price`).
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, RootModel, WithJsonSchema

from salli.domain.decisions.journal import MAX_QUESTION, MAX_TEXT
from salli.domain.scenarios.schema import Scenario
from salli.interfaces.api.contract import Amount, CurrencyCode, DecimalOut
from salli.interfaces.api.deps import AppServices, CurrentUser
from salli.interfaces.api.routers.fi import FiAssumptions
from salli.interfaces.api.routers.principles import (
    CheckedFigures,
    CheckedOption,
    FigureValue,
    PrincipleCheckResult,
    PrincipleRef,
)
from salli.interfaces.api.routers.scenarios import ScenarioComparison, ScenarioVersions

router = APIRouter(prefix="/decisions", tags=["decisions"])

_NOT_FOUND = {
    404: {"description": "Not one of your decisions, or an account or debt that isn't yours"}
}
_TEXT: dict[int | str, dict[str, Any]] = {
    200: {"content": {"text/markdown": {}}, "description": "The journal, as Markdown."}
}

Day = str  # "YYYY-MM-DD"
Status = Literal["awaiting_review", "review_due", "reviewed"]


# ── The documents, as recorded ───────────────────────────────────────────────
#
# Entries, notes and reviews are returned exactly as recorded, so that their
# hashes can be recomputed: these models describe them for the API document
# and the SDK, and the responses carry the stored JSON untouched.


class _Via(BaseModel):
    #: "api", or "mcp" for an agent, with the person's confirmation.
    channel: Literal["api", "mcp"]
    client: str | None = None
    confirmed_by_user: bool | None = None


class _Basis(BaseModel):
    """What every option rests on."""

    baseline_fingerprint: str
    versions: ScenarioVersions
    assumptions: FiAssumptions
    placeholders: list[str]
    data_as_of: Day | None
    is_stale: bool


class _Checked(BaseModel):
    figures: dict[str, FigureValue]
    unavailable: dict[str, str]
    principles: list[PrincipleCheckResult]


class _ProjectionPoint(BaseModel):
    """A month's end (the first point is the as-of date), in its own money."""

    month: str
    date: Day
    cash: str
    investments: str
    #: Debts with terms and liabilities without.
    owed: str
    net_worth: str
    #: What the option expected to be spent that month; null for the as-of
    #: date and the as-of month.
    spending: str | None


class _Option(_Checked):
    label: str
    #: The scenario as run, its as-of date filled in.
    scenario: Scenario
    scenario_hash: str
    #: Month by month from the as-of date to a year past the review date.
    projection: list[_ProjectionPoint]
    notes: list[str]


class _AgentSummary(BaseModel):
    text: str
    author: Literal["agent"]
    #: The agent's name, when known.
    agent: str | None


class DecisionEntryDocument(BaseModel):
    """`salli.decision/1`: a decision as recorded. Its hash is the SHA-256 of
    its canonical JSON (sorted keys, no whitespace, ASCII)."""

    model_config = ConfigDict(title="DecisionEntryDocument")

    schema_: Literal["salli.decision/1"] = Field(alias="schema")
    id: str
    recorded_at: str
    recorded_via: _Via
    question: str
    as_of: Day
    currency: str
    basis: _Basis
    #: The principles in use when it was recorded, as they stood.
    principles: list[PrincipleRef]
    #: The baseline's figures and the principles' checks against it.
    baseline: _Checked
    options: list[_Option]
    chosen: str
    #: The person's reasons, in their words.
    reasons: str
    #: The agent's summary, marked as the agent's; null when there is none.
    agent_summary: _AgentSummary | None
    review_on: Day


class DecisionNoteDocument(BaseModel):
    """`salli.decision-note/1`: a note appended to an entry."""

    schema_: Literal["salli.decision-note/1"] = Field(alias="schema")
    id: str
    decision_id: str
    entry_hash: str
    at: str
    text: str
    author: Literal["user", "agent"]
    agent: str | None


class ComparisonRow(BaseModel):
    """A figure the chosen option projected, what happened, and actual less
    projected, in the day's own money."""

    figure: Literal["cash", "investments", "owed", "net_worth"]
    projected: str
    actual: str
    difference: str


class ComparisonSpending(BaseModel):
    """Spending a month, on average over the full months since the decision."""

    months: list[str]
    projected: str | None
    actual: str | None
    difference: str | None


class ComparisonOther(BaseModel):
    """What another option projected for the same month's end: what it
    expected, never what would have happened."""

    option: str
    cash: str
    investments: str
    owed: str
    net_worth: str


class ReviewComparison(BaseModel):
    """What the chosen option projected at a month's end, against the
    baseline as of that day."""

    option: str
    #: The month's end compared at.
    at: Day
    month: str
    currency: str
    terms: Literal["nominal"]
    figures: list[ComparisonRow]
    spending: ComparisonSpending
    others: list[ComparisonOther]
    baseline_fingerprint: str
    #: The newest ledger entry on or before `at`.
    data_as_of: Day | None
    #: Older than 45 days: what happened is only what the ledger shows.
    is_stale: bool
    notes: list[str]


class DecisionReviewDocument(BaseModel):
    """`salli.decision-review/1`: a review appended to an entry."""

    schema_: Literal["salli.decision-review/1"] = Field(alias="schema")
    id: str
    decision_id: str
    entry_hash: str
    at: str
    #: The day the review was as of.
    as_of: Day
    #: The person's reflection, in their words.
    reflection: str
    author: Literal["user", "agent"]
    agent: str | None
    comparison: ReviewComparison


#: Shapes the documents share with other responses: referred to, not repeated.
_COMPONENTS = frozenset(
    {
        "Scenario",
        "FiAssumptions",
        "ScenarioVersions",
        "PrincipleRef",
        "PrincipleCheckResult",
        "ReviewComparison",
    }
)


def _document_schema(model: type[BaseModel]) -> dict[str, Any]:
    """`model`'s JSON Schema for a field whose value is passed through as
    stored: its own shapes written out, the ones the API document already
    has as components referred to there."""
    schema = model.model_json_schema(by_alias=True, mode="serialization")
    defs: dict[str, Any] = schema.pop("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            mapping = cast("dict[str, Any]", node)
            ref = mapping.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                name = ref.removeprefix("#/$defs/")
                rest = {k: walk(v) for k, v in mapping.items() if k != "$ref"}
                if name in _COMPONENTS:
                    return {**rest, "$ref": f"#/components/schemas/{name}"}
                return {**walk(defs[name]), **rest}
            return {k: walk(v) for k, v in mapping.items() if k not in ("$schema", "discriminator")}
        if isinstance(node, list):
            return [walk(v) for v in cast("list[Any]", node)]
        return node

    return walk(schema)


class DecisionEntry(
    RootModel[Annotated[dict[str, Any], WithJsonSchema(_document_schema(DecisionEntryDocument))]]
):
    """`salli.decision/1`, exactly as recorded."""


class DecisionNoteEntry(
    RootModel[Annotated[dict[str, Any], WithJsonSchema(_document_schema(DecisionNoteDocument))]]
):
    """`salli.decision-note/1`, exactly as recorded."""


class DecisionReviewEntry(
    RootModel[Annotated[dict[str, Any], WithJsonSchema(_document_schema(DecisionReviewDocument))]]
):
    """`salli.decision-review/1`, exactly as recorded."""


# ── Requests and responses ───────────────────────────────────────────────────


class DecisionIn(BaseModel):
    """A decision to record. Salli runs every option itself."""

    model_config = ConfigDict(extra="forbid")

    question: Annotated[str, Field(min_length=1, max_length=MAX_QUESTION)]
    #: One to five scenarios, each with its own label, sharing one as-of date.
    options: Annotated[list[Scenario], Field(min_length=1, max_length=5)]
    #: The label of the option chosen.
    chosen: Annotated[str, Field(min_length=1, max_length=200)]
    #: The person's reasons, in their words.
    reasons: Annotated[str, Field(min_length=1, max_length=MAX_TEXT)]
    #: A summary by the person's agent, recorded as the agent's.
    agent_summary: Annotated[str | None, Field(max_length=MAX_TEXT)] = None
    #: The agent's name, for its summary.
    agent: Annotated[str | None, Field(max_length=200)] = None
    #: When to look back: from the end of the as-of month on.
    review_on: dt.date


class NoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=MAX_TEXT)]


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: The person's reflection, in their words.
    reflection: Annotated[str, Field(min_length=1, max_length=MAX_TEXT)]
    #: The day the review is as of: today when left out; from the review
    #: date on, never after today.
    as_of: dt.date | None = None


class DecisionNote(BaseModel):
    note: DecisionNoteEntry
    hash: str
    #: Hashed again on reading, and the same.
    verified: bool


class DecisionReview(BaseModel):
    review: DecisionReviewEntry
    hash: str
    verified: bool


class Decision(BaseModel):
    """An entry as recorded, with what was appended to it."""

    id: str
    hash: str
    #: Hashed again on reading, and the same: the entry is unchanged.
    verified: bool
    status: Status
    entry: DecisionEntry
    notes: list[DecisionNote]
    reviews: list[DecisionReview]


class DecisionSummary(BaseModel):
    id: str
    question: str
    chosen: str
    currency: str
    as_of: Day
    review_on: Day
    recorded_at: str
    hash: str
    #: How many notes and reviews were appended.
    notes: int
    reviews: int
    last_reviewed_at: str | None
    status: Status


class DecisionList(BaseModel):
    #: Newest first.
    decisions: list[DecisionSummary]


class DueReview(DecisionSummary):
    #: The person's reasons when they decided.
    reasons: str
    comparison: ReviewComparison


class DueReviews(BaseModel):
    as_of: Day
    #: Soonest due first.
    reviews: list[DueReview]


class JournalExportEntry(BaseModel):
    entry: DecisionEntry
    hash: str
    notes: list[DecisionNote]
    reviews: list[DecisionReview]


class DecisionJournal(BaseModel):
    """`salli.decision-journal/1`: every entry, note and review as recorded."""

    schema_: Literal["salli.decision-journal/1"] = Field(alias="schema")
    exported_at: str
    #: How to check a hash.
    verify: str
    entries: list[JournalExportEntry]


def _export_view(data: dict[str, Any]) -> dict[str, Any]:
    """The export with each appended document marked verified (they were
    hashed when written and come back as stored)."""
    from salli.domain.decisions import journal

    return {
        **data,
        "entries": [
            {
                **e,
                "notes": [
                    {**n, "verified": journal.verify(n["note"], n["hash"])} for n in e["notes"]
                ],
                "reviews": [
                    {**v, "verified": journal.verify(v["review"], v["hash"])} for v in e["reviews"]
                ],
            }
            for e in data["entries"]
        ],
    }


# ── Templates and starting a decision ────────────────────────────────────────

QuestionType = Literal[
    "amount",
    "amount_or_zero",
    "signed_amount",
    "months",
    "years",
    "number",
    "rate",
    "growth",
    "date",
    "choice",
    "debt",
    "account",
    "recurring",
    "tax_role",
    "text",
    "amounts",
    "loans",
    "splits",
]
DefaultSource = Literal[
    "as_of", "next_month", "your_debts", "your_principles", "salli", "placeholder"
]


class TemplateDefault(BaseModel):
    """What an answer is when it isn't given, and where that comes from."""

    #: As the answer would be written.
    value: str | int
    #: "your_debts" and "your_principles" are your own data; "as_of" and
    #: "next_month" are dates; "salli" a plain default of Salli's;
    #: "placeholder" a labelled placeholder, not a forecast (rent-or-buy's
    #: growths beyond inflation, 0).
    source: DefaultSource
    note: str


class TemplateChoice(BaseModel):
    value: str
    label: str


class TemplateWhen(BaseModel):
    """A question asked only when another is answered (`equals` null), or
    answered so."""

    question: str
    equals: str | None


class TemplateQuestion(BaseModel):
    id: str
    #: amount (above zero, in your base currency), amount_or_zero (0 is an
    #: answer), signed_amount, months and years (whole numbers), number,
    #: rate and growth (decimal strings; a rate is a yearly fraction, a
    #: growth a signed yearly fraction beyond inflation), date, choice, debt
    #: and account (your own, by id), recurring (one of your recurring
    #: payments out, by key), tax_role (an income or deduction role in your
    #: active tax rules, by key), text, and the lists amounts, loans and
    #: splits.
    type: QuestionType
    prompt: str
    help: str
    #: Whether it must be answered when it has no default.
    required: bool
    when: TemplateWhen | None
    #: Your default, from your own data or the date; null when none applies
    #: yet (`default_rule` says when one would).
    default: TemplateDefault | None
    default_rule: str | None
    choices: list[TemplateChoice]
    minimum: int | None
    maximum: int | None
    min_items: int | None
    max_items: int | None


class DecisionTemplateSummary(BaseModel):
    """A common decision, packaged: a convenience, not advice."""

    schema_: Literal["salli.template/1"] = Field(alias="schema")
    id: str
    title: str
    summary: str
    #: The options it builds.
    builds: list[str]


class DecisionTemplateList(BaseModel):
    templates: list[DecisionTemplateSummary]


class DecisionTemplate(DecisionTemplateSummary):
    """A template's questions, each with its default as it stands for you,
    and the answers' JSON Schema."""

    questions: list[TemplateQuestion]
    #: JSON Schema (Draft 2020-12) of the answers object.
    answers_schema: dict[str, Any]
    notes: list[str]


class DecisionStartIn(BaseModel):
    """A template, and the answers to its questions (by id)."""

    model_config = ConfigDict(extra="forbid")

    template: Annotated[str, Field(min_length=1, max_length=64)]
    #: By question id: amounts and rates as decimal strings, months and
    #: years as whole numbers, dates YYYY-MM-DD.
    answers: dict[str, Any] = Field(default_factory=dict[str, Any])
    #: The day your baseline is as of: today when left out, never after today.
    as_of: dt.date | None = None
    #: Answers to your active tax rules' questions (a filing status, say), by
    #: key, put in every option (`tax.answers`): for changes a template tags
    #: with a tax role.
    tax_answers: Annotated[dict[str, str | bool], Field(max_length=100)] = Field(
        default_factory=dict[str, str | bool]
    )


class StartTemplate(BaseModel):
    id: str
    title: str


class StartAnswer(BaseModel):
    id: str
    value: Any
    #: "given", or where its default came from.
    source: Literal[
        "given", "as_of", "next_month", "your_debts", "your_principles", "salli", "placeholder"
    ]
    note: str | None


class StartOption(BaseModel):
    label: str
    #: What the option is, in a sentence.
    describes: str
    #: The scenario Salli ran, its as-of date filled in.
    scenario: Scenario
    scenario_hash: str


class StartPrinciples(BaseModel):
    """Your principles against the baseline and each option. Not a ranking."""

    principles: list[PrincipleRef]
    baseline: CheckedFigures
    options: list[CheckedOption]


class CoverMonth(BaseModel):
    #: The first month at whose end cash covers the target; null when not
    #: within 50 years.
    month: str | None
    #: Months from the as-of month (0: already).
    months: int | None


class CoverOption(CoverMonth):
    option: str
    #: Months later (positive) or sooner than the baseline's.
    delta_months: int | None


class CoverReading(BaseModel):
    """When cash, in today's money, covers a number of months of spending:
    read from the monthly timeline under the baseline and each option."""

    target_months: DecimalOut
    #: "essential" when your spending carries need tags, "all" otherwise;
    #: null without spending to count.
    basis: Literal["essential", "all"] | None
    monthly_spending: Amount | None
    #: The target in cash, in today's money.
    target: Amount | None
    #: Months of spending your cash covers on the as-of date.
    now: DecimalOut | None
    baseline: CoverMonth
    options: list[CoverOption]
    says: str


class LevelOption(BaseModel):
    option: str
    #: The first month-end from the purchase on from which the option's net
    #: worth is at least the other's at every month-end to the horizon; null
    #: when it is behind at the horizon.
    month: str | None
    #: Months from the purchase's month.
    months: int | None
    #: The option's net worth less the other's at that month's end, and at
    #: the horizon, in today's money.
    net_worth_then: Amount | None
    net_worth_at_horizon: Amount


class LevelReading(BaseModel):
    """When each option draws level with one (rent or buy: each way of
    buying against keeping renting), read from the monthly timelines; not
    solved, and not a ranking."""

    #: The option the others are read against.
    against: str
    #: The months read: from the purchase's to the horizon's.
    from_: str = Field(alias="from")
    to: str
    options: list[LevelOption]
    says: str


class StartRecord(BaseModel):
    """What `POST /v1/decisions` needs besides the person's own: their
    choice (one of `labels`), their reasons and a review date."""

    #: A suggestion: the question is the person's to put in their words.
    question: str
    #: Each option as run, its as-of date filled in.
    options: list[Scenario]
    labels: list[str]
    #: The first day the review may be set for.
    earliest_review: Day


class DecisionStart(BaseModel):
    """A template's options compared on your baseline and checked against
    your principles. Never ranked; nothing is stored."""

    schema_: Literal["salli.decision-start/1"] = Field(alias="schema")
    template: StartTemplate
    as_of: Day
    currency: CurrencyCode
    horizon_years: int
    question: str
    #: The answers as used, defaults filled in, each with its source.
    answers: list[StartAnswer]
    options: list[StartOption]
    comparison: ScenarioComparison
    principles: StartPrinciples
    #: For a template with a cash target (the emergency fund).
    cover: CoverReading | None
    #: For rent or buy: when each way of buying draws level with renting.
    level: LevelReading | None
    #: What any option's figures rest on: FI's assumptions, inflation, tax,
    #: an asset's growth ("asset_growth"), and a template's own placeholder
    #: answers ("rent_growth").
    placeholders: list[str]
    data_as_of: Day | None
    #: Older than 45 days: bring the ledger up to date before deciding.
    is_stale: bool
    notes: list[str]
    record: StartRecord
    says: str


# ── Routes ───────────────────────────────────────────────────────────────────

_NO_TEMPLATE = {404: {"description": "No template has this id"}}


@router.get("/templates")
async def list_decision_templates(svc: AppServices) -> DecisionTemplateList:
    """The decision templates: common decisions as a few questions and the
    options they build. Conveniences, not advice."""
    return DecisionTemplateList.model_validate(svc.templates.list())


@router.get("/templates/{template_id}", responses=_NO_TEMPLATE)  # type: ignore[arg-type]
async def get_decision_template(
    template_id: str, user_id: CurrentUser, svc: AppServices
) -> DecisionTemplate:
    """A template's questions, each default as it stands for you (from your
    debts, cash accounts and principles, or the date), and the answers'
    JSON Schema."""
    return DecisionTemplate.model_validate(await svc.templates.get(user_id, template_id))


@router.post("/start", responses={**_NOT_FOUND, **_NO_TEMPLATE})  # type: ignore[arg-type]
async def start_decision(
    body: DecisionStartIn, user_id: CurrentUser, svc: AppServices
) -> DecisionStart:
    """Start a decision from a template: the options your answers build,
    compared on your baseline (the trade, sensitivity and break-evens),
    checked against your principles, and what recording needs. Never a
    ranking. Stores nothing: record with `POST /v1/decisions` once you
    have chosen."""
    return DecisionStart.model_validate(await svc.templates.start(user_id, body.model_dump()))


@router.get("")
async def list_decisions(user_id: CurrentUser, svc: AppServices) -> DecisionList:
    """Your decision journal, newest first."""
    return DecisionList.model_validate(await svc.decisions.list(user_id))


@router.post("", status_code=status.HTTP_201_CREATED, responses=_NOT_FOUND)  # type: ignore[arg-type]
async def record_decision(body: DecisionIn, user_id: CurrentUser, svc: AppServices) -> Decision:
    """Record a decision: Salli runs every option on your baseline, checks
    your principles, and keeps the entry, its projection and its hash, with
    your reasons. A review reminder is set for the review date. Entries
    can't be edited or deleted: append notes and reviews."""
    data = body.model_dump(exclude={"options"})
    data["options"] = body.options
    return Decision.model_validate(
        await svc.decisions.record(user_id, data, via={"channel": "api"})
    )


@router.get("/reviews")
async def due_reviews(user_id: CurrentUser, svc: AppServices) -> DueReviews:
    """Decisions whose review date has come and that have no review yet,
    each with what the chosen option projected against what happened.
    Stores nothing."""
    return DueReviews.model_validate(await svc.decisions.due(user_id))


@router.get("/export")
async def export_decisions(user_id: CurrentUser, svc: AppServices) -> DecisionJournal:
    """The whole journal as JSON: every entry, note and review exactly as
    recorded, with its hash."""
    data = cast("dict[str, Any]", await svc.decisions.export(user_id, "json"))
    return DecisionJournal.model_validate(_export_view(data))


@router.get("/export/markdown", response_class=PlainTextResponse, responses=_TEXT)  # type: ignore[arg-type]
async def export_decisions_markdown(user_id: CurrentUser, svc: AppServices) -> Response:
    """The whole journal as Markdown, to read or keep."""
    text = cast("str", await svc.decisions.export(user_id, "markdown"))
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")


@router.get("/{decision_id}", responses=_NOT_FOUND)  # type: ignore[arg-type]
async def get_decision(decision_id: str, user_id: CurrentUser, svc: AppServices) -> Decision:
    """An entry with its notes and reviews, each hashed again (`verified`)."""
    return Decision.model_validate(await svc.decisions.get(user_id, decision_id))


@router.get(
    "/{decision_id}/markdown",
    response_class=PlainTextResponse,
    responses={**_TEXT, **_NOT_FOUND},  # type: ignore[arg-type]
)
async def decision_markdown(decision_id: str, user_id: CurrentUser, svc: AppServices) -> Response:
    """One entry, with its notes and reviews, as Markdown."""
    text = cast("str", await svc.decisions.export(user_id, "markdown", decision_id))
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")


@router.post(
    "/{decision_id}/notes",
    status_code=status.HTTP_201_CREATED,
    responses=_NOT_FOUND,  # type: ignore[arg-type]
)
async def add_decision_note(
    decision_id: str, body: NoteIn, user_id: CurrentUser, svc: AppServices
) -> DecisionNote:
    """Append a note to an entry. The entry doesn't change."""
    return DecisionNote.model_validate(
        await svc.decisions.add_note(user_id, decision_id, body.text)
    )


@router.post(
    "/{decision_id}/review",
    status_code=status.HTTP_201_CREATED,
    responses=_NOT_FOUND,  # type: ignore[arg-type]
)
async def review_decision(
    decision_id: str, body: ReviewIn, user_id: CurrentUser, svc: AppServices
) -> DecisionReview:
    """Review a decision, from its review date on: Salli compares what the
    chosen option projected with what happened, and appends it with your
    reflection. The entry doesn't change."""
    return DecisionReview.model_validate(
        await svc.decisions.review(user_id, decision_id, body.reflection, as_of=body.as_of)
    )
