"""
Financial Independence router — FI score, goals, AI FIRE strategy, projections, surplus.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from salli.application.ports import PayloadView, Surface
from salli.domain.currency import quantize
from salli.domain.usage import AIAction
from salli.interfaces.api.contract import Amount, AmountIn, CurrencyCode, DecimalIn, Ref
from salli.interfaces.api.deps import AppServices, Credentials, CurrentEmail, CurrentUser

router = APIRouter(prefix="/fi", tags=["financial-independence"])

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


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


class FiAssumption(BaseModel):
    """One planning assumption, and where it came from."""

    #: A yearly fraction, in a decimal string: "0.05" is 5%.
    value: str
    #: "user" when set on the profile, "strategy" when the user's FIRE strategy
    #: chose it, "default" when it is the default for `region`.
    origin: Literal["user", "strategy", "default"]
    #: Where the figure comes from, in words: the published figure a default
    #: rests on, or how it was arrived at.
    source: str


class FiAssumptions(BaseModel):
    """The assumptions these figures were computed with. Defaults are round,
    conservative starting points to adjust, never forecasts."""

    #: Whose defaults: the base currency ("LKR"), or "other" for a currency
    #: Salli has no figures of its own for.
    region: str
    #: Yearly inflation, which turns the nominal returns into real ones.
    inflation: FiAssumption
    #: The base scenario's yearly return after inflation.
    real_return: FiAssumption
    #: What the FI number is built on: annual expenses / this.
    safe_withdrawal_rate: FiAssumption


class FiAssumptionOverrides(BaseModel):
    """The planning assumptions the user set themselves; null where they use
    the default for their currency. Yearly fractions in decimal strings."""

    inflation: str | None = None
    #: The base scenario's yearly return after inflation.
    real_return: str | None = None
    safe_withdrawal_rate: str | None = None


class FiAssumptionOverridesIn(BaseModel):
    """Set the user's own planning assumptions, as yearly fractions ("0.03" is
    3%). Only the fields sent change; an explicit null returns one to the
    default for their currency."""

    inflation: DecimalIn | None = None
    real_return: DecimalIn | None = None
    safe_withdrawal_rate: DecimalIn | None = None


class FiAssumptionsReport(BaseModel):
    """The assumptions the user's FI figures use, the defaults for their
    currency, and what they set themselves."""

    applied: FiAssumptions
    #: Whatever applies: what the user would have without their own figures
    #: and their strategy's.
    defaults: FiAssumptions
    overrides: FiAssumptionOverrides


@router.get("/assumptions")
async def get_assumptions(user_id: CurrentUser, svc: AppServices) -> FiAssumptionsReport:
    """The planning assumptions behind the user's FI figures, and where each came from."""
    return FiAssumptionsReport.model_validate(await svc.fi.assumptions(user_id))


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
    #: Years to FI at the current pace; null when it cannot be reached or known.
    projected_fi_years: str | None = None
    #: The ISO date that is.
    projected_fi_date: str | None = None
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


async def _gate_strategy_stream(
    upstream: AsyncGenerator[str, None], view: PayloadView
) -> AsyncGenerator[str, None]:
    """Pass status/error SSE events straight through; shape only the final
    `done` event's `strategy` payload for the caller."""
    async for chunk in upstream:
        payload = chunk.removeprefix("data: ").rstrip("\n")
        try:
            event: dict[str, Any] = json.loads(payload)
        except json.JSONDecodeError:
            yield chunk
            continue
        if event.get("type") == "done" and "strategy" in event:
            event["strategy"] = view.shape(Surface.FIRE_STRATEGY, event["strategy"])
        yield f"data: {json.dumps(event, default=str)}\n\n"


# A stored score can lack fields a fresh one has; leaving them out of the
# response, rather than sending them as null, is how it has always read.
@router.get("/score", response_model_exclude_unset=True)
async def get_score(user_id: CurrentUser, svc: AppServices) -> FiScore:
    """Latest FI score, computing one on first access."""
    score = await svc.fi.get_or_compute_score(user_id)
    # A score stored before scores recorded their currency is in the base
    # currency, which cannot change once anything is stored in it.
    return _fi_score(score, score.get("currency") or await svc.ledger.base_currency(user_id))


@router.post("/score/recompute", response_model_exclude_unset=True)
async def recompute_score(user_id: CurrentUser, svc: AppServices) -> FiScore:
    """Recompute the FI score from the current ledger and store a snapshot."""
    score = await svc.fi.compute_score(user_id)
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
    # Decimal, not float — this is money, and the project's own invariant says
    # so. `current_amount` is gone: progress is derived from allocations against
    # real accounts, never typed in.
    target_amount: Decimal = Decimal(0)
    target_date: str | None = None
    # 1 high … 3 low. Decides which goal stays funded when one account is
    # claimed by several.
    priority: int = 2


class GoalUpdateRequest(BaseModel):
    name: str | None = None
    kind: str | None = None
    target_amount: Decimal | None = None
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


# ── FIRE Strategy ──────────────────────────────────────────────────────────────


class FireStrategyBucket(BaseModel):
    """One allocation bucket of a FIRE strategy."""

    model_config = ConfigDict(extra="allow")

    key: str | None = None
    name: str | None = None
    #: The share of savings it gets, a fraction (0.25 is 25%).
    target_pct: float | None = None
    description: str | None = None
    #: A display colour name: emerald, blue, amber, …
    color: str | None = None


class FireStrategy(BaseModel):
    """A version of the user's AI-generated FIRE strategy.

    Rates are fractions (0.04 is 4%), and the returns are nominal and yearly.
    Every field is optional: a strategy stored by an earlier version can lack
    some, and a deployment's entitlement policy may withhold parts of it and
    add fields of its own.
    """

    model_config = ConfigDict(extra="allow")

    version: int | None = None
    created_at: str | None = None
    #: lean | standard | fat | coast
    fire_style: str | None = None
    swr: float | None = None
    return_conservative: float | None = None
    return_base: float | None = None
    return_growth: float | None = None
    #: Monthly spending to plan retirement around, in the base currency; null
    #: means what the ledger shows. A JSON number, unlike other amounts.
    target_monthly_expenses: float | None = None
    target_age: int | None = None
    buckets: list[FireStrategyBucket] | None = None
    #: Markdown.
    ai_rationale: str | None = None
    theories_applied: list[str] | None = None
    #: True for the first strategy, false for a regenerated one.
    is_initial: bool | None = None


class FireStrategySummary(BaseModel):
    """A version in the strategy history. Optional throughout, as `FireStrategy` is."""

    model_config = ConfigDict(extra="allow")

    version: int | None = None
    created_at: str | None = None
    fire_style: str | None = None
    theories_applied: list[str] | None = None


class FireStrategyHistory(BaseModel):
    #: Newest first.
    history: list[FireStrategySummary]


# Shaped surfaces: what the entitlement policy withholds stays out of the
# response rather than coming back as null.
@router.get("/strategy", response_model_exclude_unset=True)
async def get_strategy(user_id: CurrentUser, email: CurrentEmail, svc: AppServices) -> FireStrategy:
    """Return the user's active FIRE strategy, or 404 if none exists yet."""
    strategy = await svc.fi.get_strategy(user_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No FIRE strategy found")
    view = await svc.entitlements.for_user(user_id, email)
    return FireStrategy.model_validate(view.shape(Surface.FIRE_STRATEGY, strategy))


@router.get("/strategy/history", response_model_exclude_unset=True)
async def get_strategy_history(
    user_id: CurrentUser, email: CurrentEmail, svc: AppServices
) -> FireStrategyHistory:
    """List all strategy versions (summary only)."""
    history = await svc.fi.get_strategy_history(user_id)
    view = await svc.entitlements.for_user(user_id, email)
    return FireStrategyHistory.model_validate(
        {"history": [view.shape(Surface.FIRE_STRATEGY, h) for h in history]}
    )


@router.post(
    "/strategy/generate",
    # The handler builds its own streaming response; naming the plain class keeps
    # FastAPI from also documenting an application/json body it never sends.
    response_class=Response,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Server-sent events: `status` messages while it works, then "
            "`done` with the new strategy (a `FireStrategy`), or `error`.",
        }
    },
)
async def generate_strategy(
    user_id: CurrentUser, email: CurrentEmail, svc: AppServices, creds: Credentials
):
    """
    Trigger AI FIRE strategy generation. Returns an SSE stream.

    Stream events:
      {"type": "status",  "message": "..."} — progress updates
      {"type": "done",    "strategy": {...}} — final result
      {"type": "error",   "message": "..."}  — failure

    Passes the deployment's usage meter like /agent/chat — checked before the
    stream opens, same as chat, rather than mid-stream.
    """
    # As in agent chat: the pinned Claude model, or the user's own OpenAI or
    # ChatGPT model, and the meter is told the one that runs.
    model_id = (
        await svc.profile.get_preferred_model(user_id)
        if creds.provider == "anthropic"
        else creds.model_for("best")
    )
    await svc.usage.charge(user_id, AIAction.FIRE_STRATEGY, model_id=model_id, email=email)
    view = await svc.entitlements.for_user(user_id, email)
    strategy = svc.fi.generate_strategy(
        user_id, email, api_key=creds.llm or creds.anthropic, model=model_id
    )
    return StreamingResponse(
        _gate_strategy_stream(strategy, view),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# ── Projections & Surplus ──────────────────────────────────────────────────────


class FiProjectionPoint(BaseModel):
    """The FI asset base projected to the end of a year, per scenario, in today's money."""

    model_config = ConfigDict(extra="allow")

    #: Years from now; 0 is today.
    year: int | None = None
    conservative: Amount | None = None
    base: Amount | None = None
    growth: Amount | None = None


class FiScenarioReturns(BaseModel):
    """Real (after-inflation) yearly returns per scenario, as fractions in decimal strings."""

    model_config = ConfigDict(extra="allow")

    conservative: str | None = None
    base: str | None = None
    growth: str | None = None


class FiProjections(BaseModel):
    """The FI asset base projected forward under three return scenarios, in today's money.

    A deployment's entitlement policy may withhold parts of this and add fields
    of its own, so every field is optional.
    """

    model_config = ConfigDict(extra="allow")

    #: The user's base currency, which every amount here is in.
    currency: CurrencyCode | None = None
    points: list[FiProjectionPoint] | None = None
    #: The FI number the score reports.
    fi_number: Amount | None = None
    swr: str | None = None
    #: Years to FI in each scenario; null when it is not reached.
    fire_year_conservative: int | None = None
    fire_year_base: int | None = None
    fire_year_growth: int | None = None
    current_portfolio: Amount | None = None
    real_returns: FiScenarioReturns | None = None
    expected_inflation: str | None = None
    #: The assumptions these projections use, and where each came from.
    assumptions: FiAssumptions | None = None


class SurplusBreakdown(BaseModel):
    """Monthly averages over the trailing 12 months."""

    currency: CurrencyCode
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
    """15-year portfolio projections across conservative/base/growth scenarios."""
    data = await svc.fi.get_projections(user_id)
    currency = data["currency"]
    priced = {
        **_priced(data, ("fi_number", "current_portfolio"), currency),
        "points": [_priced(p, _SCENARIOS, currency) for p in data["points"]],
    }
    view = await svc.entitlements.for_user(user_id, email)
    return FiProjections.model_validate(view.shape(Surface.FI_PROJECTIONS, priced))


@router.get("/surplus")
async def get_surplus_breakdown(user_id: CurrentUser, svc: AppServices) -> SurplusBreakdown:
    """Income-by-source and expense-by-category breakdown from the trailing 12 months."""
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


# ── "Can I afford this?" ──────────────────────────────────────────────────────


class PurchaseRequest(BaseModel):
    """
    Money arrives as a STRING and is parsed to Decimal, never float — a float in
    the money path is a bug (CLAUDE.md). `annual_interest_rate` is a fraction
    (0.18 = 18%), bounded so a caller passing 18 is rejected rather than
    silently costing the plan ~100x too dearly.
    """

    #: In the base currency, at its own precision (no decimals for JPY, three for KWD).
    amount: Annotated[AmountIn, Field(ge=0, max_digits=18)]
    term_months: Annotated[int | None, Field(default=None, ge=1, le=600)] = None
    annual_interest_rate: Annotated[Decimal, Field(default=Decimal(0), ge=0, le=1)] = Decimal(0)


PurchaseOptionKey = Literal["cash", "installments"]


class PurchaseOption(BaseModel):
    """One way of paying, costed in months of freedom."""

    key: PurchaseOptionKey
    label: str
    #: Everything handed over across the term.
    total_cost: Amount
    interest_cost: Amount
    #: Null for cash.
    monthly_payment: Amount | None
    #: Null for cash.
    term_months: int | None
    #: Null when FI is not reached within the horizon.
    months_to_fi: int | None
    #: Months of freedom it costs against not buying; null when unknowable.
    months_delay: int | None
    #: The payment is more than the monthly surplus: not just slower, cash-flow negative.
    exceeds_monthly_surplus: bool


class PurchaseImpact(BaseModel):
    """What a purchase does to the balance sheet and the FI date. Every figure is the engine's."""

    amount: Amount
    currency: CurrencyCode
    fi_number: Amount
    fi_asset_base_before: Amount
    monthly_surplus: Amount
    #: Months to FI without the purchase; null when not reached within the horizon.
    baseline_months_to_fi: int | None
    payable_from_liquid: bool
    #: Months of expenses liquid savings cover, before and after paying cash.
    emergency_months_before: str
    emergency_months_after_cash: str
    emergency_fund_target_months: int
    options: list[PurchaseOption]
    #: The option costing the fewest months of freedom; null when none compares.
    cheapest_option_key: PurchaseOptionKey | None
    #: Date of the newest entry the answer rests on, and whether that is too old.
    data_as_of: str | None
    is_stale: bool
    stale_after_days: int
    #: The base scenario's real return the costing used, a fraction.
    real_return_used: str
    swr: str
    #: The assumptions behind the costing, and where each came from.
    assumptions: FiAssumptions


@router.post("/simulate-purchase")
async def simulate_purchase(
    body: PurchaseRequest, user_id: CurrentUser, svc: AppServices
) -> PurchaseImpact:
    """
    Cost a prospective purchase in months of freedom, comparing cash against
    instalments.

    Deliberately NOT metered: it is pure deterministic engine math with no LLM
    call, and it is the loop the product exists for — throttling it would teach
    users not to ask.
    """
    impact = await svc.fi.simulate_purchase(
        user_id,
        body.amount,
        term_months=body.term_months,
        annual_interest_rate=body.annual_interest_rate,
    )
    currency = impact["currency"]
    option_money = ("total_cost", "interest_cost", "monthly_payment")
    return PurchaseImpact.model_validate(
        {
            **_priced(
                impact, ("amount", "fi_number", "fi_asset_base_before", "monthly_surplus"), currency
            ),
            "options": [_priced(o, option_money, currency) for o in impact["options"]],
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
    allocated_amount: Decimal


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
