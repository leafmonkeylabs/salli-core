"""
`/v1/tax`: the user's tax, computed by Salli's engine from the rule set they
activated (docs/taxrules.md), and returns prepared from the forms it defines.

A thin layer over TaxService and the return workflow. Each route takes the
jurisdiction and year as given (`country`, `region`, `year`) or derives them as
TaxService.resolve does: the user's tax residency, and their current tax year
(the active rule set whose dates contain today) or else the latest active year
that has begun. With nothing to compute with, a 422 `/problems/no-tax-rules`
says what to do.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from salli.interfaces.api.contract import Amount, CountryCode, CurrencyCode, DecimalOut
from salli.interfaces.api.deps import AppServices, CurrentUser
from salli.interfaces.api.routers.tax_rules import (
    TaxRuleForm,
    TaxRuleLine,
    TaxRuleRate,
    TaxRuleRoleTotal,
)

router = APIRouter(prefix="/tax", tags=["tax"])

#: Which rules: a country (ISO 3166-1 alpha-2, or a user-assigned code such as
#: XA for a fictional jurisdiction). Omitted: the user's tax residency.
CountryParam = Annotated[
    str | None, Query(pattern=r"^[A-Za-z]{2}$", examples=["XA"], description="Country code")
]
#: A region, for rules set per region. Omitted: the national rules, or the only ones.
RegionParam = Annotated[str | None, Query(max_length=200)]
#: A tax year as the rules name it. Omitted: the current tax year (see
#: GET /tax/current-year), else the latest active year that has begun.
YearParam = Annotated[str | None, Query(max_length=32, examples=["2031/32"])]

Answers = dict[str, str | bool]


# ── computations ───────────────────────────────────────────────────────────────


class TaxComputation(BaseModel):
    """The user's tax for one jurisdiction and year, as Salli's engine computed
    it from their active rule set version. Reproducible: it records that
    version, its content hash and the inputs the engine was given."""

    #: Null for a computation that wasn't stored.
    id: str | None
    created_at: datetime | None
    country: CountryCode
    region: str | None
    #: What the rules call the year.
    year: str
    period_start: str
    period_end: str
    #: The rules' currency: every amount here is in it.
    currency: CurrencyCode
    #: What the ledger is kept in.
    base_currency: CurrencyCode
    rule_set_id: str
    #: The version that computed it, its number and its content hash.
    rule_set_version_id: str
    version: int
    content_hash: str
    #: Each ledger total the rules take, from the accounts carrying its tax role.
    roles: list[TaxRuleRoleTotal]
    #: The answers to the rules' questions it was computed with.
    answers: Answers
    #: The exchange rates the ledger was converted at, when its currency isn't the rules'.
    rates: list[TaxRuleRate]
    #: Every line, each after the lines it uses, with the expression behind it.
    lines: list[TaxRuleLine]
    #: Owed after every credit: positive to pay, negative to be refunded.
    net: Amount
    tax_payable: Amount
    refund_due: Amount
    warnings: list[str]
    #: Where these figures' rules came from, to show with them.
    provenance: str


class LatestTaxComputation(BaseModel):
    #: Null until the year has been computed.
    result: TaxComputation | None


class TaxComputeIn(BaseModel):
    #: Answers to the rules' questions, by key: a decimal string, a choice, or
    #: true/false. A question left out takes its default.
    answers: Answers = Field(default_factory=Answers)


@router.post("/compute")
async def compute_tax(
    user_id: CurrentUser,
    svc: AppServices,
    body: TaxComputeIn | None = None,
    country: CountryParam = None,
    region: RegionParam = None,
    year: YearParam = None,
) -> TaxComputation:
    """Compute the user's tax with their active rule set, from their ledger, and
    store it. 422 (/problems/no-tax-rules) when they have no active rules for
    it: the detail says what to do."""
    body = body or TaxComputeIn()
    result = await svc.tax.compute_tax(
        user_id, country=country, region=region, year=year, answers=body.answers
    )
    return TaxComputation.model_validate(result)


@router.get("/latest")
async def get_latest(
    user_id: CurrentUser,
    svc: AppServices,
    country: CountryParam = None,
    region: RegionParam = None,
    year: YearParam = None,
) -> LatestTaxComputation:
    """The last computation stored for the jurisdiction and year."""
    result = await svc.tax.get_latest_computation(
        user_id, country=country, region=region, year=year
    )
    if result is None:
        return LatestTaxComputation(result=None)
    return LatestTaxComputation(result=TaxComputation.model_validate(result))


class TaxYearStatus(BaseModel):
    """The tax year the user is in today, and the one a computation uses when
    no year is named."""

    #: Whose rules: the country asked for, or the user's tax residency; null
    #: when there is neither.
    country: CountryCode | None
    #: "given" or "tax_residency"; null with neither.
    country_source: Literal["given", "tax_residency"] | None
    #: The current tax year: the year of the user's active rule set whose
    #: dates contain today ("2031/32"), with its first and last day; null when
    #: no active rule set covers today.
    year: str | None
    region: str | None
    start: str | None
    end: str | None
    #: The active version that covers today.
    rule_set_id: str | None
    rule_set_version_id: str | None
    version: int | None
    #: What /tax/compute uses with no year: the current year, else the latest
    #: active year that has begun. Null when there is none.
    latest_year: str | None
    latest_rule_set_version_id: str | None


@router.get("/current-year")
async def get_current_year(
    user_id: CurrentUser,
    svc: AppServices,
    country: CountryParam = None,
    region: RegionParam = None,
) -> TaxYearStatus:
    """The tax year the user is in today: the year of their active rule set
    whose dates contain today, or none."""
    status = await svc.tax.status(user_id, country=country, region=region)
    current, latest = status.current, status.latest
    return TaxYearStatus(
        country=status.jurisdiction.country,
        country_source=status.jurisdiction.source,
        year=current.year if current else None,
        region=current.region if current else None,
        start=current.start.isoformat() if current else None,
        end=current.end.isoformat() if current else None,
        rule_set_id=current.rule_set["id"] if current else None,
        rule_set_version_id=current.version["id"] if current else None,
        version=current.version["version"] if current else None,
        latest_year=latest.year if latest else None,
        latest_rule_set_version_id=latest.version["id"] if latest else None,
    )


# ── explanations ───────────────────────────────────────────────────────────────


class TaxSourceRef(BaseModel):
    id: str
    url: str
    title: str
    retrieved: str | None


class TaxExplainedLine(BaseModel):
    key: str
    label: str
    amount: DecimalOut
    expr: str
    #: Where in the rules it is written: `lines[2].expr`, or `blocks[1]`.
    path: str
    #: The building block it was compiled from, or null for a declared line.
    block: str | None
    refundable: bool | None
    source: TaxSourceRef | None


class TaxExplainedInput(BaseModel):
    """A ledger total the line used: the accounts carrying the tax role `key`."""

    key: str
    label: str
    kind: str
    total: DecimalOut


class TaxExplainedAnswer(BaseModel):
    key: str
    label: str
    value: str | bool
    #: True when the user gave no answer and the question's default was used.
    default: bool


class TaxExplainedLineRef(BaseModel):
    key: str
    label: str
    amount: DecimalOut
    expr: str


class TaxExplainedBand(BaseModel):
    #: The band's ceiling, counted from zero; null for the last band.
    upto: DecimalOut | None
    rate: DecimalOut


class TaxExplainedTable(BaseModel):
    key: str
    label: str | None
    bands: list[TaxExplainedBand]
    source: TaxSourceRef | None


class TaxLineExplanation(BaseModel):
    """Where one line of the user's tax came from, read off their rules and
    the result: never worked out."""

    country: CountryCode
    region: str | None
    year: str
    currency: CurrencyCode
    rule_set_id: str
    rule_set_version_id: str
    version: int
    content_hash: str
    line: TaxExplainedLine
    #: The ledger totals it used.
    inputs: list[TaxExplainedInput]
    #: The answers it used.
    answers: list[TaxExplainedAnswer]
    #: The other lines it used.
    lines: list[TaxExplainedLineRef]
    #: The band tables it applies.
    tables: list[TaxExplainedTable]
    #: The lines (and `result.net`) that use it.
    used_by: list[str]
    provenance: str


class TaxExplainIn(BaseModel):
    #: The line's key, as a computation lists it (dotted for a block's lines).
    line_key: Annotated[str, Field(min_length=1, max_length=200)]
    answers: Answers = Field(default_factory=Answers)


@router.post("/explain")
async def explain_line(
    body: TaxExplainIn,
    user_id: CurrentUser,
    svc: AppServices,
    country: CountryParam = None,
    region: RegionParam = None,
    year: YearParam = None,
) -> TaxLineExplanation:
    """Where one line of the user's tax came from: its expression, the inputs
    and lines it used with their values, any band table, and the source the
    rules cite. Computed now with the active rules; nothing is stored. 404 for
    a line the rules don't have."""
    return TaxLineExplanation.model_validate(
        await svc.tax.explain(
            user_id, body.line_key, country=country, region=region, year=year, answers=body.answers
        )
    )


# ── returns ────────────────────────────────────────────────────────────────────


class TaxReturnDraft(BaseModel):
    """A return, prepared for review: each form the rules define, filled in
    from a stored computation, with its filing instructions and URL."""

    country: CountryCode
    region: str | None
    year: str
    currency: CurrencyCode
    #: The stored computation the figures come from.
    computation_id: str
    rule_set_id: str
    rule_set_version_id: str
    version: int
    content_hash: str
    net: Amount
    tax_payable: Amount
    refund_due: Amount
    lines: list[TaxRuleLine]
    answers: Answers
    forms: list[TaxRuleForm]
    warnings: list[str]
    note: str
    provenance: str


class TaxReturnWorksheet(TaxReturnDraft):
    """An approved return: the draft, ready to file with the authority."""

    status: Literal["ready_to_file"]


class TaxReturnPrepareIn(BaseModel):
    #: Name the review thread; a new one is made if omitted.
    thread_id: Annotated[str | None, Field(max_length=200)] = None
    year: Annotated[str | None, Field(max_length=32)] = None
    country: Annotated[str | None, Field(pattern=r"^[A-Za-z]{2}$")] = None
    region: Annotated[str | None, Field(max_length=200)] = None
    answers: Answers = Field(default_factory=Answers)


class TaxReturnPrepared(BaseModel):
    """A return held for review under `thread_id`."""

    thread_id: str
    #: Why there is no draft (no active rules, no forms in them, an answer the
    #: rules need); empty when there is one.
    error: str
    draft: TaxReturnDraft | None


class TaxReturnResumeIn(BaseModel):
    thread_id: Annotated[str, Field(min_length=1, max_length=200)]
    #: approve (the worksheet, ready to file), reject, or edit: compute again
    #: (after fixing the ledger, or with new `answers`) and review again.
    decision: Literal["approve", "edit", "reject"]
    #: With edit: answers to change, merged into the return's.
    answers: Answers = Field(default_factory=Answers)


class TaxReturnResumed(BaseModel):
    """The outcome of a review."""

    #: The approved worksheet; null otherwise.
    worksheet: TaxReturnWorksheet | None
    #: After an edit: the new draft, waiting for review on the same thread.
    draft: TaxReturnDraft | None
    #: Why there is neither (rejected, nothing waiting for review on the thread,
    #: or the recomputation failed); empty otherwise.
    error: str


def _draft(raw: dict[str, Any]) -> TaxReturnDraft | None:
    return TaxReturnDraft.model_validate(raw) if raw else None


@router.post("/returns/prepare")
async def prepare_return(
    body: TaxReturnPrepareIn, user_id: CurrentUser, svc: AppServices
) -> TaxReturnPrepared:
    """Prepare a return from the user's active rules up to the review gate:
    compute (and store) their tax, fill in each form the rules define, and
    hold the draft for review under a thread of the user's own. Resume it with
    `tax.returns.resume`."""
    prepared = await svc.agent.prepare_return(
        user_id,
        year=body.year,
        country=body.country,
        region=body.region,
        answers=body.answers,
        thread_id=body.thread_id,
    )
    return TaxReturnPrepared(
        thread_id=prepared["thread_id"],
        error=prepared["error"],
        draft=_draft(prepared["draft_return"]),
    )


class TaxReturnPending(BaseModel):
    thread_id: str
    #: Whether a return of the caller's is waiting for review on this thread.
    waiting: bool
    #: The draft waiting for review; null when there is none.
    draft: TaxReturnDraft | None


@router.get("/returns/{thread_id}")
async def get_return(thread_id: str, user_id: CurrentUser, svc: AppServices) -> TaxReturnPending:
    """The caller's return waiting for review on a thread, to show before
    deciding. Another user's thread reads as nothing waiting."""
    pending = await svc.agent.get_return(user_id, thread_id)
    return TaxReturnPending(
        thread_id=thread_id, waiting=pending["waiting"], draft=_draft(pending["draft_return"])
    )


@router.post("/returns/resume")
async def resume_return(
    body: TaxReturnResumeIn, user_id: CurrentUser, svc: AppServices
) -> TaxReturnResumed:
    """Resume the caller's return after review: approve, edit (compute again
    and review again) or reject. Only a thread of the caller's own that is
    waiting for review can be resumed."""
    resumed = await svc.agent.resume_return(
        user_id=user_id, thread_id=body.thread_id, decision=body.decision, answers=body.answers
    )
    worksheet = resumed["worksheet"]
    return TaxReturnResumed(
        worksheet=TaxReturnWorksheet.model_validate(worksheet) if worksheet else None,
        draft=_draft(resumed["draft_return"]),
        error=resumed["error"],
    )
