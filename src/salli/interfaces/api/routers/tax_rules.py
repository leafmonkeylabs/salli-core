"""
`/v1/tax/schema` and `/v1/tax/rule-sets`: a user's own tax rules
(docs/taxrules.md), over HTTP.

A thin layer over TaxRuleService: the service decides everything, including
who may activate. The activate route also refuses early, with a 403 a client
can explain, when the caller's sign-in doesn't carry `tax:activate`; the
service would refuse it anyway.

Documents travel as JSON text or as JSON. Text is read strictly (a key twice
in one object is refused rather than one of them silently winning), so a
client holding a file should send its text.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from salli.application.permissions import TAX_ACTIVATE
from salli.application.services.tax_rule_service import MAX_NOTE_LENGTH
from salli.interfaces.api.contract import CountryCode, CurrencyCode, DecimalOut
from salli.interfaces.api.deps import (
    AppServices,
    CurrentActor,
    CurrentUser,
    require_permission,
)

router = APIRouter(prefix="/tax", tags=["tax"])

#: A JSON object whose shape GET /v1/tax/schema describes (or, for a draft
#: that doesn't match it yet, any JSON object).
JsonObject = dict[str, JsonValue]

RuleSetStatus = Literal["draft", "validated", "proposed", "active", "superseded", "invalid"]


# ── shapes ─────────────────────────────────────────────────────────────────────


class TaxRuleSetVersionSummary(BaseModel):
    id: str
    rule_set_id: str
    #: 1, 2, 3 …: the order versions were added in.
    version: int
    #: invalid (doesn't compile), draft (its examples don't all pass, or an
    #: import not yet validated), validated, proposed (awaiting the user's
    #: review), active (what Salli computes with), superseded (history).
    status: RuleSetStatus
    #: SHA-256 of the canonical document (docs/taxrules.md); null for a
    #: document that doesn't match the schema.
    content_hash: str | None
    #: "user" for the user's own sign-in; "agent" for an AI connector or other
    #: application (`author_name` says which).
    author_kind: Literal["user", "agent"]
    author_name: str | None
    change_note: str | None
    created_at: datetime
    proposed_at: datetime | None
    activated_at: datetime | None
    superseded_at: datetime | None


class TaxRuleSet(BaseModel):
    id: str
    country: CountryCode
    region: str | None
    #: What the authority calls the year: "2025/26".
    year_label: str
    name: str
    #: The version Salli computes with; null until one is activated.
    active_version_id: str | None
    created_at: datetime
    updated_at: datetime
    #: Every version, oldest first.
    versions: list[TaxRuleSetVersionSummary]


class TaxRuleProblem(BaseModel):
    #: Where in the document: `blocks[2].of`, or `$` for all of it.
    path: str
    message: str
    #: The expression with a caret under the mistake, when there is one.
    snippet: str | None = None


class TaxRuleMismatch(BaseModel):
    #: "payable", "refund", or a line's key.
    key: str
    expected: DecimalOut
    got: DecimalOut
    #: The expression behind the figure.
    expr: str
    #: All of it in a sentence: "payable: expected 2999, got 3000 (from line.balance)".
    message: str


class TaxRuleExampleResult(BaseModel):
    name: str
    passed: bool
    #: Why the example couldn't run at all, when it couldn't.
    error: str | None
    mismatches: list[TaxRuleMismatch]


class TaxRuleValidation(BaseModel):
    """The validator's report (docs/taxrules.md, "Validation"). `ok` only with
    no errors, at least one worked example, and every example passing."""

    ok: bool
    content_hash: str | None
    validated_at: datetime
    errors: list[TaxRuleProblem]
    warnings: list[TaxRuleProblem]
    examples: list[TaxRuleExampleResult]


class TaxRuleSetVersion(TaxRuleSetVersionSummary):
    #: The document, as it was submitted.
    document: JsonObject
    #: Its last validation.
    validation: TaxRuleValidation


class TaxRuleDocumentIn(BaseModel):
    #: The rule set: its JSON text (read strictly, so send a file's text), or
    #: the JSON itself. At most 1 MiB.
    document: str | JsonObject
    #: What changed and why, for the version history.
    note: Annotated[str | None, Field(max_length=MAX_NOTE_LENGTH)] = None


class TaxRuleImportIn(BaseModel):
    """A rule set to import, from a document or an https URL (one of them)."""

    document: str | JsonObject | None = None
    #: Fetched by the server: https only, public addresses only, at most 1 MiB.
    url: Annotated[str | None, Field(max_length=2_000)] = None
    note: Annotated[str | None, Field(max_length=MAX_NOTE_LENGTH)] = None

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.document is None) == (self.url is None):
            raise ValueError("send either a document or a url")
        return self


class TaxRuleChange(BaseModel):
    #: Where: `blocks[key=allowance].amount`. Named items are matched by name,
    #: so reordering isn't a change.
    path: str
    kind: Literal["added", "removed", "changed"]
    #: The value before (null when added) and after (null when removed).
    before: JsonValue = None
    after: JsonValue = None
    #: Whether this is a figure (an amount, rate or limit): figures are
    #: compared as numbers, so "0.150" for "0.15" is no change.
    figure: bool
    #: The id of the source the value cites (see `sources`).
    source: str | None


class TaxRuleDiff(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rule_set_id: str
    #: The version compared from: the one named, else the active one; null
    #: when there is none (everything is added).
    from_: Annotated[TaxRuleSetVersionSummary | None, Field(alias="from")]
    to: TaxRuleSetVersionSummary
    changes: list[TaxRuleChange]
    #: Each source a change cites, as the document declares it.
    sources: dict[str, JsonObject]
    #: The `to` version's worked examples, as last validated.
    examples: list[TaxRuleExampleResult]
    validation_ok: bool


class TaxRuleExport(BaseModel):
    #: A file name for it: "lk-2025-26-v3.salli-tax.json".
    filename: str
    content_hash: str | None
    #: True when `text` is the canonical JSON, whose SHA-256 is `content_hash`.
    canonical: bool
    text: str


class TaxRuleEvaluateIn(BaseModel):
    #: Answers to the rule set's questions, by key: a decimal string, a
    #: choice, or true/false. A question left out takes its default.
    answers: dict[str, str | bool] = Field(default_factory=dict[str, str | bool])
    #: The year these rules must be for; refused if they are another's.
    year: str | None = None


class TaxRuleRoleTotal(BaseModel):
    key: str
    kind: Literal["income", "deduction", "withholding", "other"]
    label: str
    #: In the rule set's currency.
    total: DecimalOut
    #: How many postings it was added up from.
    postings: int


class TaxRuleRate(BaseModel):
    #: The entry date the rate converted (YYYY-MM-DD).
    date: str
    #: Units of the rule set's currency per unit of the base currency.
    rate: DecimalOut
    source: str | None


class TaxRuleLine(BaseModel):
    key: str
    label: str
    amount: DecimalOut
    #: The expression the amount came from.
    expr: str
    source: str | None
    #: For a credit: whether it is refundable.
    refundable: bool | None


class TaxRuleFormField(BaseModel):
    id: str
    label: str
    #: The field's value: a decimal string, or true/false.
    value: DecimalOut | bool


class TaxRuleForm(BaseModel):
    """A return form the rules define, filled in from a result."""

    key: str
    label: str
    #: How to file it, as the rules say.
    instructions: str | None
    #: Where to file it.
    url: str | None
    fields: list[TaxRuleFormField]


class TaxRuleEvaluation(BaseModel):
    """A version's rules applied to the user's ledger. Nothing is stored."""

    version: TaxRuleSetVersionSummary
    #: Whether the version passed its worked examples when last validated.
    validated: bool
    country: CountryCode
    region: str | None
    year: str
    period_start: str
    period_end: str
    #: What every amount here is in.
    currency: CurrencyCode
    #: What the ledger is kept in.
    base_currency: CurrencyCode
    content_hash: str
    roles: list[TaxRuleRoleTotal]
    #: The exchange rates the ledger was converted at, when its currency
    #: isn't the rule set's.
    rates: list[TaxRuleRate]
    #: Every line, each after the lines it uses.
    lines: list[TaxRuleLine]
    #: Owed after every credit: positive to pay, negative to be refunded.
    net: DecimalOut
    net_expr: str
    tax_payable: DecimalOut
    refund_due: DecimalOut
    forms: list[TaxRuleForm]
    warnings: list[str]
    #: Where these figures' rules came from, to show with them.
    provenance: str


class TaxSuggestedAccount(BaseModel):
    code: str
    name: str
    type: Literal["asset", "liability", "equity", "income", "expense"]
    tax_role: str | None
    #: "missing" (you have no account with this code), "created" (just now),
    #: or "exists" (you have one with this code; it is left as it is).
    status: Literal["missing", "created", "exists"]
    #: Your account with this code, when there is one.
    account_id: str | None
    #: Why an existing account may not match the suggestion.
    note: str | None


class TaxSuggestedAccounts(BaseModel):
    rule_set_id: str
    #: The version whose suggestions these are.
    version_id: str
    version: int
    #: Whether missing accounts were created.
    applied: bool
    accounts: list[TaxSuggestedAccount]


class TaxSuggestedAccountsIn(BaseModel):
    #: Whose suggestions: the active version if omitted, else the newest.
    version_id: str | None = None


def _version(v: dict[str, Any]) -> TaxRuleSetVersion:
    return TaxRuleSetVersion.model_validate({**v, "document": v["content"]})


# ── routes ─────────────────────────────────────────────────────────────────────


@router.get("/schema")
async def get_schema(user_id: CurrentUser, svc: AppServices) -> JsonObject:
    """The rule-set document's JSON Schema (Draft 2020-12), to write one
    against. The validator checks more than the schema can say (unique keys,
    declared sources, expressions that compile, examples that pass)."""
    return svc.tax_rules.schema()


@router.get("/rule-sets")
async def list_rule_sets(user_id: CurrentUser, svc: AppServices) -> list[TaxRuleSet]:
    return [TaxRuleSet.model_validate(s) for s in await svc.tax_rules.list_rule_sets(user_id)]


@router.post("/rule-sets", status_code=status.HTTP_201_CREATED)
async def create_rule_set(
    body: TaxRuleDocumentIn, actor: CurrentActor, svc: AppServices
) -> TaxRuleSetVersion:
    """A new rule set with the document as version 1, stored whatever its
    validation finds (the report says what). 409 when the user already has
    one for that jurisdiction and year: add a version to it instead."""
    return _version(await svc.tax_rules.create(actor, body.document, note=body.note))


@router.post("/rule-sets/import", status_code=status.HTTP_201_CREATED)
async def import_rule_set(
    body: TaxRuleImportIn, actor: CurrentActor, svc: AppServices
) -> TaxRuleSetVersion:
    """A rule set from a document or a URL, as a new version of the user's
    rule set for its jurisdiction and year (created if there is none). It
    lands as a draft (or invalid), never further: validate it, review it,
    activate it."""
    if body.url is not None:
        return _version(await svc.tax_rules.import_url(actor, body.url))
    assert body.document is not None
    return _version(await svc.tax_rules.import_document(actor, body.document, note=body.note))


@router.get("/rule-sets/{rule_set_id}")
async def get_rule_set(rule_set_id: str, user_id: CurrentUser, svc: AppServices) -> TaxRuleSet:
    return TaxRuleSet.model_validate(await svc.tax_rules.get(user_id, rule_set_id))


@router.post("/rule-sets/{rule_set_id}/versions", status_code=status.HTTP_201_CREATED)
async def add_version(
    rule_set_id: str, body: TaxRuleDocumentIn, actor: CurrentActor, svc: AppServices
) -> TaxRuleSetVersion:
    """A new version: an edit never changes an existing one. Its jurisdiction
    and year must be the rule set's."""
    return _version(
        await svc.tax_rules.new_version(actor, rule_set_id, body.document, note=body.note)
    )


@router.get("/rule-sets/{rule_set_id}/versions/{version_id}")
async def get_version(
    rule_set_id: str, version_id: str, user_id: CurrentUser, svc: AppServices
) -> TaxRuleSetVersion:
    return _version(await svc.tax_rules.get_version(user_id, version_id, rule_set_id))


@router.post("/rule-sets/{rule_set_id}/versions/{version_id}/validate")
async def validate_version(
    rule_set_id: str, version_id: str, actor: CurrentActor, svc: AppServices
) -> TaxRuleSetVersion:
    return _version(await svc.tax_rules.validate(actor, version_id, rule_set_id))


@router.post("/rule-sets/{rule_set_id}/versions/{version_id}/propose")
async def propose_version(
    rule_set_id: str, version_id: str, actor: CurrentActor, svc: AppServices
) -> TaxRuleSetVersion:
    """Ask for the user's review. 409 unless it passes validation (run again)."""
    return _version(await svc.tax_rules.propose(actor, version_id, rule_set_id))


@router.post(
    "/rule-sets/{rule_set_id}/versions/{version_id}/activate",
    dependencies=[require_permission(TAX_ACTIVATE)],
)
async def activate_version(
    rule_set_id: str, version_id: str, actor: CurrentActor, svc: AppServices
) -> TaxRuleSetVersion:
    """Make this the version Salli computes with for its jurisdiction and
    year, superseding the active one. Needs `tax:activate`, which only the
    user's own sign-ins hold (the app, the salli CLI, and a personal access
    token made with it): 403 for an AI connector, any other application, or
    a token made without it. 409 unless it passes validation (run again)."""
    return _version(await svc.tax_rules.activate(actor, version_id, rule_set_id))


@router.get("/rule-sets/{rule_set_id}/diff")
async def diff_versions(
    rule_set_id: str,
    user_id: CurrentUser,
    svc: AppServices,
    to: Annotated[str, Query(description="The version to compare to")],
    from_: Annotated[
        str | None,
        Query(alias="from", description="The version to compare from; the active one if omitted"),
    ] = None,
) -> TaxRuleDiff:
    """What changed between two versions, with the source behind each change
    and the `to` version's example results: the review before activating."""
    return TaxRuleDiff.model_validate(await svc.tax_rules.diff(user_id, rule_set_id, to, from_))


@router.get("/rule-sets/{rule_set_id}/suggested-accounts")
async def list_suggested_accounts(
    rule_set_id: str,
    actor: CurrentActor,
    svc: AppServices,
    version_id: Annotated[
        str | None, Query(description="The version; the active one, else the newest, if omitted")
    ] = None,
) -> TaxSuggestedAccounts:
    """The accounts a rule set suggests (its `suggested_accounts`), each with
    whether you already have one with that code. Nothing is created."""
    return TaxSuggestedAccounts.model_validate(
        await svc.tax_rules.suggested_accounts(actor, rule_set_id, version_id=version_id)
    )


@router.post("/rule-sets/{rule_set_id}/suggested-accounts")
async def apply_suggested_accounts(
    rule_set_id: str,
    actor: CurrentActor,
    svc: AppServices,
    body: TaxSuggestedAccountsIn | None = None,
) -> TaxSuggestedAccounts:
    """Create the accounts a rule set suggests that you don't have yet, in your
    base currency, each with its suggested tax role. Idempotent: an account
    whose code you already use (open or closed) is left as it is. 409 for a
    superseded version."""
    body = body or TaxSuggestedAccountsIn()
    return TaxSuggestedAccounts.model_validate(
        await svc.tax_rules.suggested_accounts(
            actor, rule_set_id, version_id=body.version_id, apply=True
        )
    )


@router.get("/rule-sets/{rule_set_id}/versions/{version_id}/export")
async def export_version(
    rule_set_id: str, version_id: str, user_id: CurrentUser, svc: AppServices
) -> TaxRuleExport:
    return TaxRuleExport.model_validate(
        await svc.tax_rules.export(user_id, version_id, rule_set_id)
    )


@router.post("/rule-sets/{rule_set_id}/versions/{version_id}/evaluate")
async def evaluate_version(
    rule_set_id: str,
    version_id: str,
    user_id: CurrentUser,
    svc: AppServices,
    body: TaxRuleEvaluateIn | None = None,
) -> TaxRuleEvaluation:
    """Apply this version's rules to the user's own ledger, read-only: each
    role's total from the accounts carrying it, within the rules' year,
    converted into their currency where needed; then every line."""
    body = body or TaxRuleEvaluateIn()
    return TaxRuleEvaluation.model_validate(
        await svc.tax_rules.evaluate(
            user_id, version_id, body.answers, year_label=body.year, rule_set_id=rule_set_id
        )
    )
