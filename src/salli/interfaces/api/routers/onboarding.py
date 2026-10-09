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

from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from salli.domain.accounting.models import AccountType, Source
from salli.domain.risk.models import RiskCategory
from salli.interfaces.api.contract import Amount, CurrencyCode
from salli.interfaces.api.deps import AppServices, CurrentEmail, CurrentUser

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingRequest(BaseModel):
    name: str
    #: ISO 4217 code the ledger is kept in. Only settable while the ledger is
    #: empty — which it is, the first time onboarding runs. Omitted: unchanged.
    base_currency: str | None = None
    nic: str = ""
    residency: str = "resident"  # "resident" | "non_resident"
    employer: str = ""
    employment_type: str = ""  # "permanent" | "contract" | "self_employed" | "other"
    ird_number: str = ""
    income_sources: list[
        str
    ] = []  # ["employment","freelance","rental","interest","foreign","dividends"]
    # Goals & motivation (powers the Wealth Advisor)
    primary_goal: str = ""  # financial_independence | retirement | home | emergency_fund | debt_free | wealth_growth
    goal_target_amount: Decimal = Decimal(0)  # optional total target, in the base currency
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
    ird_number: str | None = None
    #: ISO 4217. Changes only while the ledger is empty (409 otherwise).
    base_currency: str | None = None


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
    ird_number: str | None
    #: 0-100, from the risk questionnaire.
    risk_score: int | None
    #: conservative | balanced | aggressive
    risk_category: str | None
    #: student | early_career | family | pre_retirement | retired
    life_stage: str | None
    mcp_enabled: bool
    daily_briefing_enabled: bool
    preferred_model: str | None


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
    await svc.profile.update_identity(
        user_id, body.model_dump(exclude_none=True, exclude={"base_currency"})
    )
    return ProfileUpdated(updated=True)


class OpeningBalanceItem(BaseModel):
    code: str
    name: str
    type: str  # asset|liability
    # Decimal, not float: these post straight into the ledger, and that ledger
    # is the tax base. The service already converts defensively via
    # Decimal(str(...)), so this is not a live bug — but a client that sends an
    # exact decimal string should have it stay exact, and the contract should
    # say what the project's own money invariant requires.
    amount: Decimal
    #: Defaults to the base currency. Another currency is converted at
    #: `fx_rate` (units of base per unit), or today's rate when omitted.
    currency: str | None = None
    fx_rate: Decimal | None = None


class BalanceSheetRequest(BaseModel):
    balances: list[OpeningBalanceItem]


class DeclaredEntries(BaseModel):
    #: Ids of the journal entries posted: one per item, skipping zero amounts.
    entries_created: list[str]


@router.post("/balance-sheet")
async def declare_balance_sheet(
    body: BalanceSheetRequest, user_id: CurrentUser, svc: AppServices
) -> DeclaredEntries:
    """Post real opening-balance journal entries so net worth is non-zero immediately."""
    entry_ids = await svc.profile.declare_opening_balances(
        user_id, [b.model_dump(exclude_none=True) for b in body.balances]
    )
    return DeclaredEntries(entries_created=entry_ids)


class IncomeItem(BaseModel):
    code: str
    name: str
    amount: Decimal
    #: What `amount` is denominated in; defaults to the base currency. Foreign
    #: income is the case that needs it: booking it at face value in the base
    #: currency misstates it by the exchange rate. Converted at `fx_rate`
    #: (units of base per unit), or today's rate when omitted.
    currency: str | None = None
    fx_rate: Decimal | None = None
    deposit_account_code: str | None = None
    deposit_account_name: str | None = None


class IncomeDeclarationRequest(BaseModel):
    incomes: list[IncomeItem]


@router.post("/income")
async def declare_income(
    body: IncomeDeclarationRequest, user_id: CurrentUser, svc: AppServices
) -> DeclaredEntries:
    """Post one representative monthly entry per declared income source."""
    entry_ids = await svc.profile.declare_income(
        user_id, [i.model_dump(exclude_none=True) for i in body.incomes]
    )
    return DeclaredEntries(entries_created=entry_ids)


class RiskQuestionnaireRequest(BaseModel):
    time_horizon_years: int
    drawdown_reaction: str  # sell_all|sell_some|hold|buy_more
    income_stability: str  # unstable|moderate|stable
    investment_experience: str  # none|some|experienced
    dependents_count: int = 0


class RiskBreakdown(BaseModel):
    """The points each answer contributed to the score."""

    #: 0-20
    time_horizon: int
    #: 0-25
    drawdown_reaction: int
    #: 0-20
    income_stability: int
    #: 0-20
    investment_experience: int
    #: 0-15: fewer dependents, more points.
    dependents: int


class RiskProfile(BaseModel):
    """The scored questionnaire, as saved to the profile."""

    #: 0-100
    score: int
    category: RiskCategory
    breakdown: RiskBreakdown


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
    # Decimal, not float — money. `current_amount` is gone: goal progress is
    # derived from allocations against real accounts, never declared up front.
    target_amount: Decimal = Decimal(0)
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
    #: What the tax pack treats the account as, if anything.
    tax_role: str | None = None


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
    reversed_by: str | None
    postings: list[ExportedPosting]


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
    tax_computation_2025_26: dict[str, Any] | None
    """The latest 2025/26 computation as the tax engine recorded it, or null.
    Kept for tools that read it; `tax_computations` has every year."""
    tax_computations: list[dict[str, Any]] = Field(default_factory=list)
    """The latest computation for each tax year a pack covers, as recorded."""
    budgets: list[dict[str, Any]]
    """Each as in `budgets.list`."""
    debts: list[dict[str, Any]]
    """Each as in `debts.list`, inactive ones included."""
    holdings: list[dict[str, Any]]
    """Each as in `holdings.list`, inactive ones included."""
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
    advisor_reports: list[dict[str, Any]]
    """The advisor's reports, as stored."""
    reminders_and_alerts: list[dict[str, Any]]
    """Each as in `reminders.list`."""
    documents: list[dict[str, Any]]
    """Each as in `documents.list`: the record, not the file it may point to."""


@router.get("/export")
async def export_my_data(user_id: CurrentUser, svc: AppServices) -> DataExport:
    """Everything Salli has stored about this user, as one JSON document."""
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
    #: Rows deleted, by table (an extension's tables included).
    counts: dict[str, int]


@router.delete("/account")
async def delete_my_account(
    body: DeleteAccountRequest, user_id: CurrentUser, email: CurrentEmail, svc: AppServices
) -> AccountDeletion:
    """
    Permanently delete every row belonging to this user. Irreversible.
    Requires confirm_email to match the authenticated account's email —
    a deliberate friction point against an accidental or spoofed call.
    """
    if not email or body.confirm_email.strip().lower() != email.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm_email does not match the account email",
        )
    counts = await svc.data_portability.delete_account(user_id)
    return AccountDeletion(deleted=True, counts=counts)
