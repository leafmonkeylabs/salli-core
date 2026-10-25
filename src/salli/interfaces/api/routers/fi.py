"""
Financial Independence router — FI score, goals, assumptions, projections, surplus.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from salli.application.ports import Surface
from salli.domain.currency import quantize
from salli.domain.fi.montecarlo import Guardrails
from salli.interfaces.api.contract import Amount, AmountIn, CurrencyCode, DecimalIn, Ref
from salli.interfaces.api.deps import AppServices, CurrentEmail, CurrentUser

router = APIRouter(prefix="/fi", tags=["financial-independence"])


# ── Money on the way out ──────────────────────────────────────────────────────


def money(value: Decimal | str, currency: str) -> str:
    """`value` as an `Amount`: a plain decimal string with exactly the currency's decimals.

    The FI service writes its figures with `str(Decimal)`: cents whatever the
    currency, and raw quotients, which Decimal renders in exponent form when
    they divide exactly (1800000.0 / 0.04 is "4.500000E+7"). Stored scores carry
    the same strings, so they are normalised here, where they leave the API.
    """
    return str(quantize(Decimal(value), currency, strict=False))


def _priced(payload: dict[str, Any], keys: Iterable[str], currency: str) -> dict[str, Any]:
    """A copy of `payload` with the amounts under `keys` normalised by `money`."""
    priced = {k: money(payload[k], currency) for k in keys if payload.get(k) is not None}
    return {**payload, **priced}


# ── Assumptions ───────────────────────────────────────────────────────────────
#
# Projections run in real terms (today's money). Where the user has not set a
# figure, a neutral placeholder stands in, always labelled as one: projections
# never wait for assumptions, and every FI response says which it used.


class FiAssumption(BaseModel):
    """One planning assumption a figure was computed with, and where it came from."""

    #: A yearly fraction, in a decimal string: "0.04" is 4%.
    value: str
    #: "user" when the user (or their agent) set it (or their pack gives it),
    #: "placeholder" when it is the neutral stand-in, "derived" for a
    #: withdrawal rate the odds' returns sustain (`source` says how).
    origin: Literal["user", "placeholder", "derived"]
    #: Where the figure comes from, in words: the source the user cited, or
    #: the placeholder's label.
    source: str
    #: The user's note on it, if any.
    note: str | None = None


class FiScenarioReturns(BaseModel):
    """Yearly returns per scenario, as fractions in decimal strings."""

    model_config = ConfigDict(extra="allow")

    conservative: str | None = None
    base: str | None = None
    growth: str | None = None


class CmaSummary(BaseModel):
    """A capital-market assumptions pack's figures, as projections use them."""

    #: The stored pack's id; null for the placeholder.
    id: str | None = None
    name: str
    version: str
    #: True for the code's neutral pack: every figure a placeholder.
    placeholder: bool
    #: The mix's expected yearly return after inflation.
    expected_real_return: str
    #: The mix's yearly volatility, √(wᵀΣw).
    volatility: str
    #: What cash earns a year after inflation (the placeholder's is never used).
    cash_yield: str
    inflation: str | None = None
    #: The Student-t degrees of freedom the odds draw returns with (the
    #: lower, the fatter the tails); a placeholder when the pack gives none.
    degrees_of_freedom: str


HeadlineStatus = Literal["placeholder", "pack", "own"]


class DrawdownHorizon(BaseModel):
    """The years a derived withdrawal rate must last: from the FI month to
    the planning age (a labelled placeholder of 95 when unset; 30 years,
    labelled, without a date of birth)."""

    years: int
    origin: Literal["user", "placeholder"]
    source: str


class FiAssumptions(BaseModel):
    """The assumptions these figures were computed with, in real terms.

    Check `status`: "placeholder" means at least one figure (`placeholders`
    says which) is a neutral stand-in, not a forecast and not any country's
    figure; set your own with `PATCH /v1/fi/assumptions`.
    """

    #: "placeholder" while any figure used is one; "user" once every one was
    #: set by the user or their agent.
    status: Literal["placeholder", "user"]
    #: The placeholders in use: "real_return", "safe_withdrawal_rate",
    #: "surplus_invested".
    placeholders: list[
        Literal["real_return", "safe_withdrawal_rate", "surplus_invested", "drawdown_horizon"]
    ]
    #: What the FI number and the odds rest on: "placeholder" while any of
    #: their inputs is one, else "pack" while the active pack gives any,
    #: else "own"; `headline` says it in a sentence, to show beside them.
    headline_status: HeadlineStatus | None = None
    headline: str | None = None
    #: What to tell a person about these assumptions, in a sentence or two.
    message: str
    #: The base scenario's yearly return after inflation.
    real_return: FiAssumption
    #: What the FI number is built on: annual expenses / this.
    safe_withdrawal_rate: FiAssumption
    #: The share (0 to 1) of each month's regular surplus that goes into
    #: investments and grows at the real return; the rest stays in cash,
    #: which earns an active CMA pack's cash yield or nothing. Not a rate: "0.8" is 80% of the surplus.
    surplus_invested: FiAssumption
    #: The user's inflation; null when they have not set one, and then every
    #: figure is in today's money only.
    inflation: FiAssumption | None = None
    #: The user's return before inflation, when the real return came from it.
    nominal_return: FiAssumption | None = None
    #: What cash earns a year after inflation: the active pack's, else a
    #: labelled placeholder of nothing.
    cash_yield: FiAssumption | None = None
    #: The years a derived withdrawal rate must last.
    drawdown_horizon: DrawdownHorizon | None = None
    #: Each scenario's real return.
    real_returns: FiScenarioReturns
    #: Each scenario's return before inflation; only with the user's inflation.
    nominal_returns: FiScenarioReturns | None = None
    #: The capital-market assumptions in use: the user's active pack, or
    #: the labelled placeholder pack.
    cma: CmaSummary | None = None


AssumptionName = Literal[
    "real_return",
    "nominal_return",
    "inflation",
    "volatility",
    "safe_withdrawal_rate",
    "surplus_invested",
]


class FiOwnAssumption(BaseModel):
    """A planning assumption the user (or their agent) set."""

    #: A yearly fraction in a decimal string (a share from 0 to 1, for
    #: surplus_invested).
    value: str
    #: Where it comes from: a URL or a citation.
    source: str | None = None
    note: str | None = None
    #: When it was set (ISO 8601).
    set_at: str | None = None


class FiOwnAssumptions(BaseModel):
    """What the user set themselves; null where they have not."""

    #: The base scenario's yearly return after inflation.
    real_return: FiOwnAssumption | None = None
    #: Or the return before inflation; it needs `inflation` to become a real one.
    nominal_return: FiOwnAssumption | None = None
    inflation: FiOwnAssumption | None = None
    #: The yearly volatility of your return: with your own return, the odds
    #: draw with this pair.
    volatility: FiOwnAssumption | None = None
    safe_withdrawal_rate: FiOwnAssumption | None = None
    #: The share of the monthly surplus invested.
    surplus_invested: FiOwnAssumption | None = None


class FiPlaceholder(BaseModel):
    """The neutral stand-in used where the user has set nothing."""

    value: str
    #: Says it is a placeholder, and why it is this figure.
    source: str


class FiPlaceholderValues(BaseModel):
    real_return: FiPlaceholder
    safe_withdrawal_rate: FiPlaceholder
    surplus_invested: FiPlaceholder


class FiAssumptionsReport(BaseModel):
    """The assumptions the user's FI figures use, what they set themselves,
    and the placeholders that stand in for the rest."""

    applied: FiAssumptions
    own: FiOwnAssumptions
    placeholder_values: FiPlaceholderValues
    #: How far the conservative and growth scenarios sit below and above the
    #: base real return.
    scenario_spread: str


class FiOwnAssumptionIn(BaseModel):
    """One planning assumption to set."""

    #: A yearly fraction: "0.03" is 3%. Plausible ranges are enforced
    #: (a real return from -0.05 to 0.15, a withdrawal rate from 0.01 to 0.10,
    #: inflation and a nominal return from -0.05 to 1). For surplus_invested,
    #: a share from 0 to 1: "0.8" is 80% of the monthly surplus.
    value: DecimalIn
    #: Where the figure comes from: a URL, or a publication and its date.
    source: Annotated[str | None, Field(max_length=500)] = None
    #: Anything else worth knowing about it.
    note: Annotated[str | None, Field(max_length=1000)] = None


class FiAssumptionsUpdate(BaseModel):
    """Set the user's own planning assumptions. Only the fields sent change;
    an explicit null clears one (its placeholder stands in again). Set a real return or a nominal one, not both; a nominal
    return needs inflation."""

    real_return: FiOwnAssumptionIn | None = None
    nominal_return: FiOwnAssumptionIn | None = None
    inflation: FiOwnAssumptionIn | None = None
    #: The yearly volatility of your return, from 0 to 0.80.
    volatility: FiOwnAssumptionIn | None = None
    safe_withdrawal_rate: FiOwnAssumptionIn | None = None
    #: The share (0 to 1) of each month's regular surplus you invest.
    surplus_invested: FiOwnAssumptionIn | None = None


@router.get("/assumptions")
async def get_assumptions(user_id: CurrentUser, svc: AppServices) -> FiAssumptionsReport:
    """The planning assumptions behind the user's FI figures: which apply and
    where each came from, what the user set, and the placeholders."""
    return FiAssumptionsReport.model_validate(await svc.fi.assumptions(user_id))


@router.patch("/assumptions")
async def set_assumptions(
    body: FiAssumptionsUpdate, user_id: CurrentUser, svc: AppServices
) -> FiAssumptionsReport:
    """Set or clear the user's own planning assumptions, each with its source.
    A figure out of range, or a set that can't be used together, is a 422 and
    changes nothing."""
    changes: dict[str, dict[str, Any] | None] = {
        name: (None if given is None else given.model_dump())
        for name, given in body
        if name in body.model_fields_set
    }
    return FiAssumptionsReport.model_validate(await svc.fi.set_assumptions(user_id, changes))


# ── Score ─────────────────────────────────────────────────────────────────────


class FiScoreComponent(BaseModel):
    """One of the parts the Freedom Score is a weighted blend of."""

    #: savings_rate | emergency_fund | fi_progress | debt | goals
    key: str
    label: str
    #: 0..100, a decimal string.
    score: str
    #: The share of the overall score it carried (0..1), after the weight of a
    #: missing component (no goals) was shared out.
    weight: str
    detail: str


class FiScore(BaseModel):
    """The Freedom Score (0..100) and every figure it was computed from.

    Ratios are fractions in decimal strings ("0.25" is 25%), never percentages.
    A score stored by an earlier version may lack the optional fields.
    """

    pack_version: str
    #: 0..100, a decimal string.
    overall_score: str
    grade: str
    #: The user's base currency, which every amount here is in.
    currency: CurrencyCode
    monthly_income: Amount
    monthly_expenses: Amount
    monthly_surplus: Amount
    savings_rate: str
    #: The safe withdrawal rate the FI number was derived from.
    swr: str | None = None
    #: The yearly spending the FI number is built on.
    annual_expenses: Amount | None = None
    #: What financial independence takes: annual_expenses / swr.
    fi_number: Amount
    net_worth: Amount
    #: Investable assets net of debt, which progress to FI is measured with.
    fi_asset_base: Amount | None = None
    #: fi_asset_base / fi_number. Not capped at 1, so being past the number shows.
    progress_to_fi: str
    emergency_fund_months: str
    debt_to_asset: str
    #: Months from the as-of month until FI, on the baseline's monthly timeline;
    #: null when it isn't reached within 50 years, or can't be known.
    projected_fi_months: int | None = None
    #: The calendar month that is ("YYYY-MM").
    projected_fi_month: str | None = None
    #: The day the score is as of (ISO 8601).
    as_of: str | None = None
    #: "not_enough_data" while fewer than two full months of income and
    #: spending are observed: the score and grade are then not worth showing.
    status: Literal["ok", "not_enough_data"] | None = None
    #: The full calendar months of income and spending observed (at most 12).
    months_observed: int | None = None
    #: As `assumptions.headline_status` and `assumptions.headline`.
    headline_status: HeadlineStatus | None = None
    headline: str | None = None
    components: list[FiScoreComponent]
    #: The assumptions it was computed with, and where each came from.
    assumptions: FiAssumptions | None = None
    #: Fingerprint of the inputs the score was computed from.
    inputs_hash: str | None = None


class FiScoreSnapshot(BaseModel):
    """A stored Freedom Score, for a trend line."""

    #: 0..100.
    score: float
    #: Null for a score stored without one.
    net_worth: Amount | None
    created_at: str


class FiScoreHistory(BaseModel):
    #: The user's base currency, which every amount here is in.
    currency: CurrencyCode
    #: Newest first.
    history: list[FiScoreSnapshot]


_SCORE_MONEY = (
    "monthly_income",
    "monthly_expenses",
    "monthly_surplus",
    "annual_expenses",
    "fi_number",
    "net_worth",
    "fi_asset_base",
)


#: Ratios, to four places ("0.5500"); months of expenses saved, to two. The
#: stored score keeps every digit the engine computed; nothing reads 28 of them.
_SCORE_PLACES = {
    "savings_rate": Decimal("0.0001"),
    "progress_to_fi": Decimal("0.0001"),
    "debt_to_asset": Decimal("0.0001"),
    "emergency_fund_months": Decimal("0.01"),
}


def _fi_score(score: dict[str, Any], currency: str) -> FiScore:
    shown = _priced(score, _SCORE_MONEY, currency)
    for key, places in _SCORE_PLACES.items():
        if shown.get(key) is not None:
            shown[key] = str(Decimal(str(shown[key])).quantize(places, rounding=ROUND_HALF_UP))
    return FiScore.model_validate({**shown, "currency": currency})


# A stored score can lack fields a fresh one has; leaving them out of the
# response, rather than sending them as null, is how it has always read.
@router.get("/score", response_model_exclude_unset=True)
async def get_score(user_id: CurrentUser, svc: AppServices) -> FiScore:
    """The FI score as of today, computed from the ledger as it is. Reading
    it stores nothing: `POST /v1/fi/score/recompute` records one in the
    history."""
    score = await svc.fi.compute_score(user_id)
    return _fi_score(score, score["currency"])


@router.post("/score/recompute", response_model_exclude_unset=True)
async def recompute_score(user_id: CurrentUser, svc: AppServices) -> FiScore:
    """Compute today's FI score and record it in the score history (unless
    the latest recorded one was computed from the same inputs)."""
    score = await svc.fi.record_score(user_id)
    return _fi_score(score, score["currency"])


@router.get("/score/history")
async def score_history(user_id: CurrentUser, svc: AppServices) -> FiScoreHistory:
    history = await svc.fi.get_score_history(user_id)
    currency = await svc.ledger.base_currency(user_id)
    return FiScoreHistory.model_validate(
        {"currency": currency, "history": [_priced(h, ("net_worth",), currency) for h in history]}
    )


# ── Goals ─────────────────────────────────────────────────────────────────────


class GoalRequest(BaseModel):
    name: str
    kind: str = "custom"
    # `current_amount` is gone: progress is derived from allocations against
    # real accounts, never typed in.
    target_amount: AmountIn = Decimal(0)
    target_date: str | None = None
    # 1 high … 3 low. Decides which goal stays funded when one account is
    # claimed by several.
    priority: int = 2


class GoalUpdateRequest(BaseModel):
    name: str | None = None
    kind: str | None = None
    target_amount: AmountIn | None = None
    target_date: str | None = None
    priority: int | None = None
    is_active: bool | None = None


class Goal(BaseModel):
    """A savings goal, its progress measured from what its accounts actually hold."""

    id: str
    name: str
    #: fi | retirement | home | emergency_fund | debt_free | wealth_growth | custom,
    #: or whatever else a client named it.
    kind: str
    currency: CurrencyCode
    target_amount: Amount
    #: What the accounts earmarked for it hold, shared out by priority where an
    #: account backs more than one goal.
    current_amount: Amount
    #: What was earmarked for it.
    allocated_amount: Amount
    #: The part of what was earmarked that the accounts do not hold.
    shortfall: Amount
    #: YYYY-MM-DD.
    target_date: str | None
    #: 1 high … 3 low.
    priority: int
    #: current_amount / target_amount, 0..1.
    progress: float
    created_at: str | None


class GoalList(BaseModel):
    goals: list[Goal]


class GoalUpdated(BaseModel):
    updated: bool


@router.get("/goals")
async def list_goals(user_id: CurrentUser, svc: AppServices) -> GoalList:
    return GoalList.model_validate({"goals": await svc.fi.list_goals(user_id)})


@router.post("/goals", status_code=status.HTTP_201_CREATED)
async def create_goal(body: GoalRequest, user_id: CurrentUser, svc: AppServices) -> Ref:
    goal_id = await svc.fi.create_goal(user_id, body.model_dump())
    return Ref(id=goal_id)


@router.patch("/goals/{goal_id}")
async def update_goal(
    goal_id: str, body: GoalUpdateRequest, user_id: CurrentUser, svc: AppServices
) -> GoalUpdated:
    if not any(g["id"] == goal_id for g in await svc.fi.list_goals(user_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such goal")
    await svc.fi.update_goal(user_id, goal_id, body.model_dump(exclude_none=True))
    return GoalUpdated(updated=True)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(goal_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    await svc.fi.delete_goal(user_id, goal_id)


# ── Projections & Surplus ──────────────────────────────────────────────────────


class FiNominalPoint(BaseModel):
    """A year's projected values in that year's own money, from the user's inflation."""

    model_config = ConfigDict(extra="allow")

    conservative: Amount | None = None
    base: Amount | None = None
    growth: Amount | None = None
    #: The FI number in that year's money.
    fi_number: Amount | None = None


class FiProjectionPoint(BaseModel):
    """The FI asset base projected to the end of a year, per scenario, in today's money."""

    model_config = ConfigDict(extra="allow")

    #: Years from now; 0 is today.
    year: int | None = None
    conservative: Amount | None = None
    base: Amount | None = None
    growth: Amount | None = None
    #: The same in that year's money; only when the user set their inflation.
    nominal: FiNominalPoint | None = None


class FiDate(BaseModel):
    """When FI is reached in one scenario."""

    #: Months from the as-of month; null when it is not reached within 50 years.
    months: int | None
    #: The calendar month ("YYYY-MM"); null alike.
    month: str | None


class FiDates(BaseModel):
    conservative: FiDate
    base: FiDate
    growth: FiDate


class FiProjections(BaseModel):
    """The FI asset base projected forward under three real-return scenarios,
    in today's money, and in each year's own money when the user set their
    inflation. Never waits for assumptions: `assumptions.status` says when a
    placeholder stands in.

    A deployment's entitlement policy may withhold parts of this and add fields
    of its own, so every field is optional.
    """

    model_config = ConfigDict(extra="allow")

    #: The user's base currency, which every amount here is in.
    currency: CurrencyCode | None = None
    #: As `assumptions.headline_status` and `assumptions.headline`.
    headline_status: HeadlineStatus | None = None
    headline: str | None = None
    #: "real": amounts in today's money only; "real_and_nominal": each point
    #: also carries its year's own money.
    terms: Literal["real", "real_and_nominal"] | None = None
    points: list[FiProjectionPoint] | None = None
    #: The FI number the score reports.
    fi_number: Amount | None = None
    swr: str | None = None
    #: When FI is reached in each scenario: the month, and the months from
    #: the as-of date; both null when it is not reached.
    fi_by: FiDates | None = None
    #: The day the projections are as of (ISO 8601).
    as_of: str | None = None
    current_portfolio: Amount | None = None
    #: The real (after-inflation) yearly returns the scenarios use.
    real_returns: FiScenarioReturns | None = None
    #: The user's inflation; null when they have not set one.
    inflation: str | None = None
    #: The scenarios' returns before inflation; only with the user's inflation.
    nominal_returns: FiScenarioReturns | None = None
    #: The assumptions these projections use, where each came from, and
    #: whether any is a placeholder.
    assumptions: FiAssumptions | None = None


class SurplusBreakdown(BaseModel):
    """Monthly averages over the full months observed (the baseline's: at
    most twelve, before this one, from the first with income or expenses).
    The totals are the baseline's monthly income and expenses."""

    currency: CurrencyCode
    #: The day these are as of (ISO 8601).
    as_of: str
    #: The months averaged over ("YYYY-MM"), oldest first.
    months_observed: list[str]
    #: Income account name → monthly average.
    income_by_source: dict[str, Amount]
    #: Category tag (or account name) → monthly average, for the six largest.
    expense_by_category: dict[str, Amount]
    #: `need` tag → monthly average. Empty until spending is tagged on that axis,
    #: which means "not classified yet", not "nothing spent".
    expense_by_need: dict[str, Amount]
    gross_monthly_income: Amount
    gross_monthly_expenses: Amount
    monthly_surplus: Amount
    #: monthly_surplus / gross_monthly_income, a fraction in a decimal string.
    savings_rate: str


_SCENARIOS = ("conservative", "base", "growth")


@router.get("/projections", response_model_exclude_unset=True)
async def get_projections(
    user_id: CurrentUser, email: CurrentEmail, svc: AppServices
) -> FiProjections:
    """Projections across conservative/base/growth real-return scenarios
    (15 years, or as far as FI is reached, up to 40), with placeholders
    standing in for assumptions the user has not set."""
    data = await svc.fi.get_projections(user_id)
    currency = data["currency"]

    def point(p: dict[str, Any]) -> dict[str, Any]:
        priced = _priced(p, _SCENARIOS, currency)
        if p.get("nominal") is not None:
            priced["nominal"] = _priced(p["nominal"], (*_SCENARIOS, "fi_number"), currency)
        return priced

    priced = {
        **_priced(data, ("fi_number", "current_portfolio"), currency),
        "points": [point(p) for p in data["points"]],
    }
    view = await svc.entitlements.for_user(user_id, email)
    return FiProjections.model_validate(view.shape(Surface.FI_PROJECTIONS, priced))


@router.get("/surplus")
async def get_surplus_breakdown(user_id: CurrentUser, svc: AppServices) -> SurplusBreakdown:
    """Income by source and spending by category, monthly, over the full months observed."""
    data = await svc.fi.get_surplus_breakdown(user_id)
    currency = data["currency"]
    by_name = ("income_by_source", "expense_by_category", "expense_by_need")
    totals = ("gross_monthly_income", "gross_monthly_expenses", "monthly_surplus")
    return SurplusBreakdown.model_validate(
        {
            **_priced(data, totals, currency),
            **{k: {name: money(v, currency) for name, v in data[k].items()} for k in by_name},
        }
    )


# ── goal allocations ──────────────────────────────────────────────────────────
#
# An allocation earmarks part of a real account for a goal. Progress is derived
# from what that account actually holds, so it moves when money moves — unlike
# the old `current_amount`, which was a number the user typed and then had to
# maintain by hand.
#
# One account can back several goals. When their claims exceed the balance the
# shortfall is reported rather than rejected, and the balance is apportioned by
# the goals' `priority`.


class AllocationRequest(BaseModel):
    account_id: str
    allocated_amount: AmountIn


class GoalAllocation(BaseModel):
    """Part of an account earmarked for a goal."""

    goal_id: str
    account_id: str
    currency: CurrencyCode
    allocated_amount: Amount


class GoalAllocationList(BaseModel):
    allocations: list[GoalAllocation]


@router.get("/goals/{goal_id}/allocations")
async def list_goal_allocations(
    goal_id: str, user_id: CurrentUser, svc: AppServices
) -> GoalAllocationList:
    return GoalAllocationList.model_validate(
        {"allocations": await svc.fi.list_allocations(user_id, goal_id)}
    )


@router.put("/goals/{goal_id}/allocations")
async def set_goal_allocation(
    goal_id: str, body: AllocationRequest, user_id: CurrentUser, svc: AppServices
) -> GoalUpdated:
    """Earmark part of an account for this goal. An amount of 0 clears it."""
    try:
        await svc.fi.set_allocation(user_id, goal_id, body.account_id, body.allocated_amount)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return GoalUpdated(updated=True)


# ── The odds (a seeded Monte Carlo) ────────────────────────────────────────────


class OddsQuery(BaseModel):
    """How to run the odds: every field optional."""

    #: "YYYY-MM": when withdrawals start; the FI month when left out.
    retire_month: Annotated[str | None, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None
    horizon_years: Annotated[int, Field(ge=1, le=50)] = 50
    paths: Annotated[int, Field(ge=1, le=5000)] = 1000
    #: The same seed gives the same figures.
    seed: Annotated[int, Field(ge=0, le=2**31)] = 1
    #: The share of paths the horizon-derived withdrawal rate must last on.
    success_level: Annotated[str, Field(pattern=r"^0?\.\d+$")] = "0.9"
    #: A spending band, as a fraction of the starting withdrawal rate: with
    #: it, guardrails cut or raise spending by `guardrail_adjust`.
    guardrail_band: Annotated[str | None, Field(pattern=r"^0?\.\d+$")] = None
    guardrail_adjust: Annotated[str, Field(pattern=r"^0?\.\d+$")] = "0.1"

    def options(self) -> dict[str, Any]:
        return {
            "retire_month": self.retire_month,
            "horizon_years": self.horizon_years,
            "paths": self.paths,
            "seed": self.seed,
            "success_level": Decimal(self.success_level),
            "guardrails": None
            if self.guardrail_band is None
            else Guardrails(Decimal(self.guardrail_band), Decimal(self.guardrail_adjust)),
        }


class OddsReturns(BaseModel):
    """Where the paths' returns come from: one source for mean and volatility."""

    #: "user": your own return and volatility; "pack": your pack's mix;
    #: "placeholder": the placeholder pack's.
    origin: Literal["user", "pack", "placeholder"]
    #: "bootstrap" when the pack's monthly history is resampled; else
    #: "student_t".
    method: Literal["student_t", "bootstrap"]
    #: Your holdings' weighted yearly expense ratio, taken off the mean.
    expense_ratio: str
    says: str


class OddsWithdrawalRate(BaseModel):
    #: The rate the FI number uses: yours ("user"), or the one the odds'
    #: returns sustain over `applied_years` ("derived"; "placeholder" while
    #: those returns are the placeholder pack's).
    applied: str
    origin: Literal["user", "placeholder", "derived"]
    #: The years the applied rate must last; null for yours.
    applied_years: int | None = None
    #: Where those years come from (the planning age, or a placeholder).
    applied_horizon: str | None = None
    #: The rate `success_level` of paths sustain over `years` drawn down.
    horizon_derived: str
    years: int
    success_level: str


class OddsGuardrails(BaseModel):
    band: str
    adjust: str
    #: The share of paths that last to the horizon with guardrails.
    success: str
    #: The share of paths that cut spending at least once.
    cut: str
    #: The 10th percentile of the lowest spending reached, a share of planned.
    low_spending_p10: str


class OddsYear(BaseModel):
    """The asset base across paths at a whole year, in today's money."""

    year: int
    p10: Amount
    p50: Amount
    p90: Amount


class WithdrawalTaxRules(BaseModel):
    rule_set_id: str
    version: int
    year: str


class WithdrawalTax(BaseModel):
    """Whether the FI number is grossed up for tax on withdrawals."""

    status: Literal["computed", "not_computed"]
    rules: WithdrawalTaxRules | None = None
    message: str


class FiOdds(BaseModel):
    """The odds of the plan, from a seeded Monte Carlo on the baseline's
    monthly timeline, in today's money. Shares are fractions. Not a forecast."""

    currency: CurrencyCode
    as_of: str
    #: As `FiAssumptions.headline_status` and `headline`.
    headline_status: HeadlineStatus
    headline: str
    paths: int
    seed: int
    horizon_years: int
    #: The mean yearly real return and volatility the paths are drawn with.
    real_return: str
    volatility: str
    returns: OddsReturns
    cma: CmaSummary
    fi_number: Amount
    fi_month: str | None = None
    #: When withdrawals start; null when FI isn't reached and none was given.
    retire_month: str | None = None
    #: The share of paths that never run out by the horizon; null without
    #: a retirement month.
    success: str | None = None
    #: The share of paths that reach the FI number within the horizon.
    reach: str
    withdrawal_rate: OddsWithdrawalRate
    guardrails: OddsGuardrails | None = None
    percentiles: list[OddsYear]
    withdrawal_tax: WithdrawalTax
    placeholders: list[str]
    message: str


@router.get("/odds")
async def get_odds(
    user_id: CurrentUser, svc: AppServices, query: Annotated[OddsQuery, Query()]
) -> FiOdds:
    """The odds of reaching and sustaining FI: a seeded, reproducible Monte
    Carlo of returns from your capital-market assumptions (or the labelled
    placeholder), with 10/50/90 percentile wealth paths, a horizon-derived
    withdrawal rate beside yours, and optional guardrails. Reads only."""
    return FiOdds.model_validate(await svc.fi.odds(user_id, **query.options()))


# ── The FI plan: guaranteed income and spending phases ─────────────────────────


class IncomeStream(BaseModel):
    """A guaranteed income: a pension, an annuity, a provident fund's payout."""

    name: Annotated[str, Field(min_length=1, max_length=500)]
    #: "YYYY-MM": the first month it pays.
    start: Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
    #: A month's payment, in today's money (`real`) or the start month's own (`nominal`).
    monthly: AmountIn
    terms: Literal["real", "nominal"] = "real"
    #: Keeps its value against inflation from its start.
    indexed: bool = True
    #: Paid once in its start month, in the same terms.
    lump_sum: AmountIn = Decimal(0)
    source: Annotated[str | None, Field(max_length=500)] = None
    #: The income role of your tax rules it is taxed under: withdrawals in
    #: retirement are taxed beside it.
    tax_role: Annotated[str | None, Field(max_length=500)] = None


class SpendingPhase(BaseModel):
    """The monthly spending to live on, in today's money, from an age on."""

    from_age: Annotated[int, Field(ge=0, le=120)]
    monthly: AmountIn
    source: Annotated[str | None, Field(max_length=500)] = None
    #: Category (a lowercase key such as housing) → the part of `monthly` in
    #: it; a category with its own inflation grows apart from the general.
    categories: Annotated[dict[str, AmountIn], Field(max_length=20)] = {}


class CategoryInflationIn(BaseModel):
    #: A yearly fraction from -0.05 to 1: "0.06" is 6%.
    value: DecimalIn
    source: Annotated[str | None, Field(max_length=500)] = None


class FiPlanIn(BaseModel):
    income_streams: Annotated[list[IncomeStream], Field(max_length=20)] = []
    spending_phases: Annotated[list[SpendingPhase], Field(max_length=20)] = []
    #: Your own inflation by category of spending, over your pack's.
    category_inflation: Annotated[dict[str, CategoryInflationIn], Field(max_length=20)] = {}
    #: The age the money must last to: a derived withdrawal rate is tested
    #: from the FI month to it. Unset, a labelled placeholder of 95.
    planning_age: Annotated[int, Field(ge=50, le=120)] | None = None


class IncomeStreamOut(BaseModel):
    name: str
    start: str
    monthly: str
    terms: Literal["real", "nominal"]
    indexed: bool
    lump_sum: str
    source: str | None = None
    tax_role: str | None = None


class SpendingPhaseOut(BaseModel):
    from_age: int
    monthly: str
    source: str | None = None
    categories: dict[str, str] = {}


class CategoryInflationOut(BaseModel):
    value: str
    source: str | None = None


class FiPlan(BaseModel):
    """Guaranteed income and spending phases: they reduce, and step, the FI
    number, and the income enters the monthly timeline."""

    income_streams: list[IncomeStreamOut]
    spending_phases: list[SpendingPhaseOut]
    category_inflation: dict[str, CategoryInflationOut] = {}
    planning_age: int | None = None
    #: From the profile; the phases go by it, and apply only with it.
    date_of_birth: str | None = None


@router.get("/plan")
async def get_plan(user_id: CurrentUser, svc: AppServices) -> FiPlan:
    """Your guaranteed income streams and spending phases."""
    return FiPlan.model_validate(await svc.fi.plan(user_id))


@router.put("/plan")
async def set_plan(body: FiPlanIn, user_id: CurrentUser, svc: AppServices) -> FiPlan:
    """Replace your guaranteed income streams and spending phases."""
    return FiPlan.model_validate(await svc.fi.set_plan(user_id, body.model_dump(mode="json")))


# ── Capital-market assumptions (`salli.cma/1`) ─────────────────────────────────


class CmaPackRow(BaseModel):
    id: str
    name: str
    version: str
    content_hash: str
    is_active: bool
    created_at: str
    activated_at: str | None = None


class CmaPack(CmaPackRow):
    summary: CmaSummary
    #: The document as imported; it never changes.
    content: dict[str, Any]


class CmaPackList(BaseModel):
    packs: list[CmaPackRow]
    #: What stands in while no pack is active.
    placeholder: CmaSummary


class CmaActivate(BaseModel):
    #: One of your packs; null to use the placeholder again.
    pack_id: str | None


@router.get("/cma-packs")
async def list_cma_packs(user_id: CurrentUser, svc: AppServices) -> CmaPackList:
    """Your capital-market assumptions packs, and the placeholder."""
    return CmaPackList.model_validate(await svc.fi.cma_packs(user_id))


@router.post("/cma-packs", status_code=status.HTTP_201_CREATED)
async def import_cma_pack(body: dict[str, Any], user_id: CurrentUser, svc: AppServices) -> CmaPack:
    """Import a `salli.cma/1` pack (docs/baseline.md): stored inactive, and
    never changed. A document that isn't valid is a 422 saying why."""
    return CmaPack.model_validate(await svc.fi.import_cma_pack(user_id, body))


@router.get("/cma-packs/{pack_id}")
async def get_cma_pack(pack_id: str, user_id: CurrentUser, svc: AppServices) -> CmaPack:
    found = await svc.fi.cma_pack(user_id, pack_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such pack")
    return CmaPack.model_validate(found)


@router.put("/cma-packs/active")
async def activate_cma_pack(
    body: CmaActivate, user_id: CurrentUser, svc: AppServices
) -> CmaPackList:
    """Make one of your packs the one projections, the odds and debt or
    invest read; null for the placeholder."""
    try:
        return CmaPackList.model_validate(await svc.fi.activate_cma_pack(user_id, body.pack_id))
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such pack") from None
