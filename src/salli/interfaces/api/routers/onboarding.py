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

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

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


@router.post("/complete")
async def complete_onboarding(body: OnboardingRequest, user_id: CurrentUser, svc: AppServices):
    """
    Save profile as agent memories and create a starter chart of accounts.
    Idempotent — safe to call again if the user re-runs onboarding.
    """
    # Before any account exists, since accounts are opened in the base currency.
    if body.base_currency:
        await svc.profile.set_base_currency(user_id, body.base_currency)
    return await svc.onboarding.complete(user_id, body.model_dump(exclude={"base_currency"}))


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


@router.get("/profile")
async def get_profile(user_id: CurrentUser, svc: AppServices):
    """The structured fact-find profile — identity, risk profile, life stage."""
    return await svc.profile.get_profile(user_id)


@router.patch("/profile")
async def update_profile(body: ProfileIdentityRequest, user_id: CurrentUser, svc: AppServices):
    if body.base_currency:
        await svc.profile.set_base_currency(user_id, body.base_currency)
    await svc.profile.update_identity(
        user_id, body.model_dump(exclude_none=True, exclude={"base_currency"})
    )
    return {"updated": True}


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


@router.post("/balance-sheet")
async def declare_balance_sheet(body: BalanceSheetRequest, user_id: CurrentUser, svc: AppServices):
    """Post real opening-balance journal entries so net worth is non-zero immediately."""
    entry_ids = await svc.profile.declare_opening_balances(
        user_id, [b.model_dump(exclude_none=True) for b in body.balances]
    )
    return {"entries_created": entry_ids}


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
async def declare_income(body: IncomeDeclarationRequest, user_id: CurrentUser, svc: AppServices):
    """Post one representative monthly entry per declared income source."""
    entry_ids = await svc.profile.declare_income(
        user_id, [i.model_dump(exclude_none=True) for i in body.incomes]
    )
    return {"entries_created": entry_ids}


class RiskQuestionnaireRequest(BaseModel):
    time_horizon_years: int
    drawdown_reaction: str  # sell_all|sell_some|hold|buy_more
    income_stability: str  # unstable|moderate|stable
    investment_experience: str  # none|some|experienced
    dependents_count: int = 0


@router.post("/risk-questionnaire")
async def submit_risk_questionnaire(
    body: RiskQuestionnaireRequest, user_id: CurrentUser, svc: AppServices
):
    """Score the risk-tolerance questionnaire and persist score/category/life-stage."""
    return await svc.profile.submit_risk_questionnaire(user_id, body.model_dump())


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


@router.post("/goals", status_code=status.HTTP_201_CREATED)
async def declare_goals(body: GoalsRequest, user_id: CurrentUser, svc: AppServices):
    """Create one or more goals — repeatable, unlike the legacy single-goal flow."""
    goal_ids = [await svc.fi.create_goal(user_id, g.model_dump()) for g in body.goals]
    return {"goal_ids": goal_ids}


# ── Data portability ─────────────────────────────────────────────────────────


@router.get("/export")
async def export_my_data(user_id: CurrentUser, svc: AppServices):
    """Everything Salli has stored about this user, as one JSON document."""
    return await svc.data_portability.export_all(user_id)


class DeleteAccountRequest(BaseModel):
    confirm_email: str


@router.delete("/account")
async def delete_my_account(
    body: DeleteAccountRequest, user_id: CurrentUser, email: CurrentEmail, svc: AppServices
):
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
    return {"deleted": True, "counts": counts}
