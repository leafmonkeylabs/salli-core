"""
Onboarding router — first-time user setup.

`GET /status` and `POST /complete` are the legacy all-in-one flow (still served
unchanged for the current frontend wizard — saves profile facts as agent memories
and creates a starter chart of accounts from declared income sources).

The rest are the focused fact-find steps (Phase 1 redo) backed by
`UserProfileService`/`LedgerService`/`FiService`: identity, opening balance sheet,
income declaration, a scored risk questionnaire, and repeatable goal creation. These
post real journal entries and structured profile columns instead of memory blobs —
a new frontend wizard is a follow-up once these are in place.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from salli.domain.accounting.models import AccountType, Source
from salli.domain.jurisdiction import MAX_TAX_ID_LENGTH
from salli.domain.risk.models import RiskCategory
from salli.interfaces.api.contract import Amount, AmountIn, CountryCode, CurrencyCode, DecimalIn
from salli.interfaces.api.deps import (
    AppServices,
    CurrentEmail,
    CurrentUser,
    require_recent_password,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class TaxId(BaseModel):
    """A number a tax authority knows the user by."""

    #: The country's ISO 3166-1 alpha-2 code, a hyphen, then the kind of
    #: number in capitals or digits ("XX-TIN"). Salli knows no country's
    #: schemes: the user, or a rule set's suggestion, names them.
    scheme: Annotated[str, Field(pattern=r"^[A-Z]{2}-[A-Z0-9]+$", examples=["XX-TIN"])]
    value: Annotated[str, Field(min_length=1, max_length=MAX_TAX_ID_LENGTH)]


class OnboardingRequest(BaseModel):
    name: str
    #: ISO 4217 code the ledger is kept in. Only settable while the ledger is
    #: empty — which it is, the first time onboarding runs. Omitted: unchanged.
    base_currency: str | None = None
    #: Where the user is taxed, saved on the profile. Omitted: unchanged. It
    #: decides which of their tax rule sets compute their tax; the starter
    #: accounts are the same for everyone, and tax accounts come later from a
    #: rule set's suggestions (`tax.ruleSets.suggestedAccounts.apply`).
    #: Never inferred: not from the currency, nor from a tax id.
    tax_residency: CountryCode | None = None
    #: The numbers the user's tax authorities know them by, saved on the
    #: profile; one per scheme. Omitted or empty: unchanged.
    tax_ids: list[TaxId] = Field(default_factory=list[TaxId])
    residency: str = "resident"  # "resident" | "non_resident"
    employer: str = ""
    employment_type: str = ""  # "permanent" | "contract" | "self_employed" | "other"
    income_sources: list[
        str
    ] = []  # ["employment","freelance","rental","interest","foreign","dividends"]
    # Goals & motivation
    primary_goal: str = ""  # financial_independence | retirement | home | emergency_fund | debt_free | wealth_growth
    #: An optional total target, in the base currency.
    goal_target_amount: AmountIn = Decimal(0)
    goal_target_year: str = ""  # optional YYYY
    risk_appetite: str = ""  # conservative | balanced | aggressive
    motivation: str = ""  # free text — why this matters to them


class OnboardingStatusResponse(BaseModel):
    complete: bool


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_status(user_id: CurrentUser, svc: AppServices):
    """Check whether the user has completed onboarding."""
    return {"complete": await svc.onboarding.is_complete(user_id)}


class OnboardingResult(BaseModel):
    """What the all-in-one onboarding saved and opened. Running it again skips
    what already exists rather than duplicating it."""

    #: Slugs of the profile facts saved as agent memories.
    memories_saved: list[str]
    #: "<code> <name>" of each starter account opened.
    accounts_created: list[str]
    #: Codes of the starter accounts that already existed or could not be opened.
    accounts_skipped: list[str]


@router.post("/complete")
async def complete_onboarding(
    body: OnboardingRequest, user_id: CurrentUser, svc: AppServices
) -> OnboardingResult:
    """
    Save profile as agent memories and create a starter chart of accounts.
    Idempotent — safe to call again if the user re-runs onboarding.
    """
    # Before any account exists, since accounts are opened in the base currency.
    if body.base_currency:
        await svc.profile.set_base_currency(user_id, body.base_currency)
    result = await svc.onboarding.complete(user_id, body.model_dump(exclude={"base_currency"}))
    return OnboardingResult.model_validate(result)


# ── Focused fact-find steps (Phase 1 redo) ─────────────────────────────────────


class ProfileIdentityRequest(BaseModel):
    display_name: str | None = None
    date_of_birth: str | None = None  # YYYY-MM-DD
    dependents_count: int | None = None
    employment_status: str | None = None  # employed|self_employed|unemployed|student|retired
    employment_type: str | None = None  # permanent|contract|self_employed|other
    residency_status: str | None = None  # resident|non_resident
    employer: str | None = None
    #: Where the user is taxed. An explicit null clears it.
    tax_residency: CountryCode | None = None
    #: Replaces every tax id; one number per scheme. An empty list removes them.
    tax_ids: list[TaxId] | None = None
    #: ISO 4217. Changes only while the ledger is empty (409 otherwise).
    base_currency: str | None = None
    #: The day the books start (opening balances are posted on it); no
    #: later than the first entry already booked (422 otherwise).
    books_start: dt.date | None = None
    #: How many years each document saved from now on is kept (1 to 100).
    document_retention_years: int | None = Field(default=None, ge=1, le=100)


class Profile(BaseModel):
    """The structured fact-find profile: identity, risk profile, life stage.

    A fact the user has not given yet is null.
    """

    id: str
    email: str | None
    display_name: str | None
    #: The currency the ledger is kept in; fixed once anything is stored in it.
    base_currency: CurrencyCode
    #: YYYY-MM-DD.
    date_of_birth: str | None
    dependents_count: int | None
    #: employed | self_employed | unemployed | student | retired
    employment_status: str | None
    #: resident | non_resident
    residency_status: str | None
    employer: str | None
    #: permanent | contract | self_employed | other
    employment_type: str | None
    #: 0-100, from the risk questionnaire.
    risk_score: int | None
    #: conservative | balanced | aggressive
    risk_category: str | None
    #: student | early_career | family | pre_retirement | retired
    life_stage: str | None
    mcp_enabled: bool
    daily_briefing_enabled: bool
    preferred_model: str | None
    #: Where the user is taxed; null until they say. It decides which of their
    #: tax rule sets compute their tax.
    tax_residency: CountryCode | None = None
    #: The numbers their tax authorities know them by.
    tax_ids: list[TaxId] = Field(default_factory=list[TaxId])
    #: Their IANA time zone ("Europe/Lisbon"), null until they set it with
    #: their digest preferences (`notifications.preferences.update`).
    time_zone: str | None = None
    #: The books are closed up to and including this day (YYYY-MM-DD):
    #: nothing is posted or reversed on or before it. Null: none are closed.
    #: Set with `ledger.lockDate.set`.
    lock_date: str | None = None
    #: The day the books start (YYYY-MM-DD): opening balances are posted on
    #: it, and a report for a time before it says the books don't cover it.
    #: Null until opening balances are declared or it is set.
    books_start: str | None = None
    #: Years a document saved now is kept before it may be deleted; null: none.
    document_retention_years: int | None = None


class ProfileUpdated(BaseModel):
    updated: bool


@router.get("/profile")
async def get_profile(user_id: CurrentUser, svc: AppServices) -> Profile:
    """The structured fact-find profile — identity, risk profile, life stage."""
    profile = await svc.profile.get_profile(user_id)
    # Every profile row has a base currency. Without one there is no row: the
    # service answers a bare {"id": ...} then, and that is not a profile. It
    # happens when the account was deleted through another worker, whose
    # membership cache this one does not share.
    if profile.get("base_currency") is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return Profile.model_validate(profile)


@router.patch("/profile")
async def update_profile(
    body: ProfileIdentityRequest, user_id: CurrentUser, svc: AppServices
) -> ProfileUpdated:
    if body.base_currency:
        await svc.profile.set_base_currency(user_id, body.base_currency)
    data = body.model_dump(exclude_none=True, exclude={"base_currency"})
    # A null leaves every other field as it is; for the residency it is how a
    # client clears it.
    if "tax_residency" in body.model_fields_set and body.tax_residency is None:
        data["tax_residency"] = None
    await svc.profile.update_identity(user_id, data)
    return ProfileUpdated(updated=True)


class OpeningBalanceItem(BaseModel):
    code: str
    name: str
    type: str  # asset|liability
    #: For an asset: "cash" (money you spend from: a bank account, cash, a
    #: card), "savings" (cash you keep: a savings account, an emergency fund),
    #: "investment" (funds, shares, a pension) or "other" (a home, a car).
    #: Left out, an asset is "other": never counted as cash.
    asset_role: Literal["cash", "savings", "investment", "other"] | None = None
    #: A decimal string: these post straight into the ledger, the tax base.
    amount: AmountIn
    #: Defaults to the base currency. Another currency is converted at
    #: `fx_rate` (units of base per unit), or the rate on the day the books
    #: start when omitted.
    currency: str | None = None
    fx_rate: DecimalIn | None = None
    #: Something owed: its yearly rate as a fraction ("0.18" is 18%). Given,
    #: the line is also declared as a debt linked to its account (in the base
    #: currency only), so the payoff plan has its rate.
    rate: DecimalIn | None = None
    #: Something owed: the minimum payment a month (0 when not given; needs
    #: `rate`).
    minimum_payment: AmountIn | None = None


class BalanceSheetRequest(BaseModel):
    balances: list[OpeningBalanceItem]


class DeclaredEntries(BaseModel):
    #: Ids of the journal entries posted: one per item, skipping zero amounts.
    entries_created: list[str]


@router.post("/balance-sheet")
async def declare_balance_sheet(
    body: BalanceSheetRequest, user_id: CurrentUser, svc: AppServices
) -> DeclaredEntries:
    """Post real opening-balance journal entries so net worth is non-zero immediately,
    on the day the books start (the profile's `books_start`; today, and set so, when
    none is set)."""
    entry_ids = await svc.profile.declare_opening_balances(
        user_id, [b.model_dump(exclude_none=True) for b in body.balances]
    )
    return DeclaredEntries(entries_created=entry_ids)


class IncomeItem(BaseModel):
    """A source of income, opened as an income account so the first real pay
    is booked to it. Nothing is posted: an amount sent is not booked."""

    code: str
    name: str
    #: The account it is paid into (default: the starter bank account, opened
    #: as cash when it has to be).
    deposit_account_code: str | None = None
    deposit_account_name: str | None = None


class IncomeDeclarationRequest(BaseModel):
    incomes: list[IncomeItem]


class IncomeAccounts(BaseModel):
    #: The income accounts, one per item, opened or found by code.
    income_accounts: list[str]


@router.post("/income")
async def declare_income(
    body: IncomeDeclarationRequest, user_id: CurrentUser, svc: AppServices
) -> IncomeAccounts:
    """Open an income account per source, and the account it is paid into.
    Nothing is posted: income enters the books when it is paid."""
    ids = await svc.profile.open_income_accounts(
        user_id, [i.model_dump(exclude_none=True) for i in body.incomes]
    )
    return IncomeAccounts(income_accounts=ids)


_Item = Annotated[int, Field(ge=1, le=5)] | None


class RiskQuestionnaireRequest(BaseModel):
    """Tolerance (attitude, scored), capacity (horizon, income stability,
    dependents: measured with your baseline, `GET /v1/ips/risk-profile`)
    and experience (recorded, never scored)."""

    #: Capacity: years until the money is needed.
    time_horizon_years: int
    #: Tolerance: sell_all | sell_some | hold | buy_more.
    drawdown_reaction: str
    #: Capacity: unstable | moderate | stable.
    income_stability: str
    #: Recorded, not scored: none | some | experienced.
    investment_experience: str
    #: Capacity.
    dependents_count: int = 0
    #: Tolerance, 1-5: the largest fall in a year you could accept (1 none,
    #: 5 forty per cent or more).
    loss_tolerance: _Item = None
    #: Tolerance, 1-5: a sure gain or an uncertain larger one (1 always sure).
    certainty: _Item = None
    #: Tolerance, 1-5: values swinging month to month (1 very uncomfortable).
    volatility_comfort: _Item = None
    #: Tolerance, 1-5: how you see yourself with money (1 very cautious).
    self_rating: _Item = None
    #: Tolerance, 1-5: what you dwell on after a decision (1 the loss).
    loss_focus: _Item = None
    #: Tolerance, 1-5: in a fall you lived through (1 sold everything).
    past_behaviour: _Item = None


class RiskProfile(BaseModel):
    """The scored tolerance, as saved to the profile."""

    #: 0-100, over the tolerance items answered.
    score: int
    category: RiskCategory
    #: Each tolerance item's points, 0-4.
    breakdown: dict[str, int]
    items_answered: int
    #: As answered; never part of the score.
    experience: str
    experience_scored: bool


@router.post("/risk-questionnaire")
async def submit_risk_questionnaire(
    body: RiskQuestionnaireRequest, user_id: CurrentUser, svc: AppServices
) -> RiskProfile:
    """Score the risk-tolerance questionnaire and persist score/category/life-stage."""
    result = await svc.profile.submit_risk_questionnaire(user_id, body.model_dump())
    return RiskProfile.model_validate(result)


class OnboardingGoalItem(BaseModel):
    name: str
    kind: str = "custom"
    # `current_amount` is gone: goal progress is derived from allocations
    # against real accounts, never declared up front.
    target_amount: AmountIn = Decimal(0)
    target_date: str | None = None
    priority: int = 2


class GoalsRequest(BaseModel):
    goals: list[OnboardingGoalItem]


class DeclaredGoals(BaseModel):
    #: Ids of the goals created, in the order they were sent.
    goal_ids: list[str]


@router.post("/goals", status_code=status.HTTP_201_CREATED)
async def declare_goals(
    body: GoalsRequest, user_id: CurrentUser, svc: AppServices
) -> DeclaredGoals:
    """Create one or more goals — repeatable, unlike the legacy single-goal flow."""
    goal_ids = [await svc.fi.create_goal(user_id, g.model_dump()) for g in body.goals]
    return DeclaredGoals(goal_ids=goal_ids)


# ── Data portability ─────────────────────────────────────────────────────────


class ExportedAccount(BaseModel):
    id: str
    code: str
    name: str
    type: AccountType
    currency: CurrencyCode
    parent_id: str | None
    is_active: bool
    #: The tax role the account carries for the user's tax rules, if any.
    tax_role: str | None = None
    equity_role: Literal["retained_earnings"] | None = None


class ExportedPosting(BaseModel):
    account_id: str
    direction: Literal["DEBIT", "CREDIT"]
    #: In the posting's own currency.
    amount: Amount
    currency: CurrencyCode
    #: Base-currency units per unit of `currency`, as booked ("1" when they
    #: are the same), and where the rate came from.
    fx_rate: str = "1"
    fx_rate_source: str | None = None
    #: Classification tags by kind: {"category": "groceries", "need": "essential"}.
    tags: dict[str, str] = Field(default_factory=dict)


class ExportedJournalEntry(BaseModel):
    id: str
    entry_date: str
    description: str
    source: Source
    external_ref: str | None
    #: For a reversal, the entry it reverses.
    reverses: str | None = None
    #: For a corrected copy, the entry it corrects.
    corrects: str | None = None
    reversed_by: str | None
    #: Who posted it (a user id) and how they came in (console, cli,
    #: mobile, mcp:<client>, import, automation, ...).
    created_by: str | None = None
    created_via: str | None = None
    #: Its place in the ledger's hash chain, and its hash.
    seq: int | None = None
    hash: str | None = None
    postings: list[ExportedPosting]


class ExportedMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    #: The tools the assistant called, by name: never what they were given
    #: or what they returned.
    tools: list[str] = Field(default_factory=list)


class ExportedConversation(BaseModel):
    #: The id the conversation was started with.
    thread_id: str
    #: When it last changed (ISO 8601).
    updated_at: str
    #: In the order they were said.
    messages: list[ExportedMessage]


class DataExport(BaseModel):
    """Everything Salli has stored about the user, as one document.

    The profile, accounts and journal entries are typed here; each other
    section says where its records come from. An enabled extension may add
    sections of its own after these.
    """

    model_config = ConfigDict(extra="allow", use_attribute_docstrings=True)

    user_id: str
    profile: Profile
    accounts: list[ExportedAccount]
    """Every account, closed ones included: entries refer to them."""
    journal_entries: list[ExportedJournalEntry]
    tax_computations: list[dict[str, Any]] = Field(default_factory=list)
    """Every stored tax computation, newest first, as `tax.latest` shows one:
    the rule set version that computed it, its inputs and every line."""
    tax_returns: list[dict[str, Any]] = Field(default_factory=list)
    """Every version of every return, as `tax.returnRecords.list` shows one:
    its status, filing, snapshot and payments."""
    budgets: list[dict[str, Any]]
    """Each as in `budgets.list`."""
    debts: list[dict[str, Any]]
    """Each as in `debts.list`, inactive ones included."""
    holdings: list[dict[str, Any]]
    """Each as in `holdings.list`, inactive ones included."""
    holding_transactions: list[dict[str, Any]] = Field(default_factory=list)
    """Every holding's transactions (buys, sales, income, splits, transfers
    in), inactive holdings' included, in the order they were recorded."""
    holding_prices: list[dict[str, Any]] = Field(default_factory=list)
    """Every closing price recorded, newest first."""
    recurring_subscriptions: list[dict[str, Any]]
    """Each as in `subscriptions.list`, inactive ones included."""
    insurance_policies: list[dict[str, Any]]
    """Each as in `insurance.policies.list`, inactive ones included."""
    insurance_targets: list[dict[str, Any]]
    """Each as in `insurance.targets.list`."""
    goals: list[dict[str, Any]]
    """Each as in `goals.list`: active goals."""
    fi_score_history: list[dict[str, Any]]
    """Each as in `fi.score.history`."""
    fire_strategies: list[dict[str, Any]] = Field(default_factory=list)
    """The FIRE strategies an earlier Salli drafted with a model, newest
    first, as stored. Salli no longer makes them."""
    advisor_reports: list[dict[str, Any]]
    """Every report as stored: monthly briefings, and the advisor's earlier
    reports with their recommendations."""
    reminders_and_alerts: list[dict[str, Any]]
    """Each as in `reminders.list`."""
    documents: list[dict[str, Any]]
    """Each as in `documents.list`: the record, not the file it may point to."""
    statements: list[dict[str, Any]] = Field(default_factory=list)
    """Each imported statement as in `statements.list`, with its parsed
    `transactions` (as statement transactions are shown), whatever their state."""
    bank_connections: list[dict[str, Any]] = Field(default_factory=list)
    """Each bank connection as in `bank-connections.list`: its accounts, where
    each is imported, and the bank's last balances. Never its credential."""
    principles: list[dict[str, Any]] = Field(default_factory=list)
    """Every principle as in `principles.list`, archived ones included."""
    decision_journal: dict[str, Any] = Field(default_factory=dict)
    """The decision journal as `decisions.export` gives it: every entry,
    note and review exactly as recorded, with its hash."""
    conversations: list[ExportedConversation] = Field(default_factory=list)
    """Every conversation with Salli's AI, newest first: the person's and
    the assistant's messages in order. Empty where the server keeps none
    (no Postgres checkpointer). A briefing or return awaiting review is
    working state made from the data above, not a conversation."""
    notification_preferences: dict[str, Any] | None = None
    """The digest's preferences as stored (null while never set); the time
    zone is in `profile`."""
    notification_deliveries: list[dict[str, Any]] = Field(default_factory=list)
    """The digest's delivery log as `notifications.deliveries.list` shows
    it: each period's status, items (kinds, counts, dates) and hash."""


#: Export and erasure each hand over or end everything: behind the step-up.
_STEP_UP = {
    403: {
        "description": "`/problems/step-up-required`: sign in again on Salli's page first "
        "(the console or the app, more than five minutes after the password)"
    }
}


@router.get(
    "/export",
    dependencies=[require_recent_password("Exporting all your data")],
    responses=_STEP_UP,
)
async def export_my_data(user_id: CurrentUser, svc: AppServices) -> DataExport:
    """Everything Salli has stored about this user, as one JSON document. A
    sign-in whose client wants a recent password (the console's and the
    app's) needs one entered in the last five minutes."""
    data = await svc.data_portability.export_all(user_id)
    # Encoded the way FastAPI encoded this document before it had a model, so
    # every value reaches clients as it always has — including the sections
    # extensions add, which this model cannot see (a Decimal there is a JSON
    # number, a datetime keeps its "+00:00").
    return DataExport.model_validate(jsonable_encoder(data))


class DeleteAccountRequest(BaseModel):
    confirm_email: str


class AccountDeletion(BaseModel):
    deleted: bool
    #: Rows deleted, by table (an extension's tables included), then
    #: `stored_files` and `conversations` deleted. `stored_files_failed` or
    #: `conversations_failed` (1) says some were left, for the operator to
    #: remove.
    counts: dict[str, int]


@router.delete(
    "/account",
    dependencies=[require_recent_password("Deleting your account")],
    responses=_STEP_UP,
)
async def delete_my_account(
    body: DeleteAccountRequest, user_id: CurrentUser, email: CurrentEmail, svc: AppServices
) -> AccountDeletion:
    """
    Permanently delete every row belonging to this user. Irreversible.
    Requires confirm_email to match the authenticated account's email —
    a deliberate friction point against an accidental or spoofed call —
    and, where the client wants one (the console's and the app's), a
    password entered in the last five minutes.
    """
    if not email or body.confirm_email.strip().lower() != email.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm_email does not match the account email",
        )
    counts = await svc.data_portability.delete_account(user_id)
    return AccountDeletion(deleted=True, counts=counts)
