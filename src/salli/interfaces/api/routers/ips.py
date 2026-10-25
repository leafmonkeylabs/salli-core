"""
Investment policy router — the person's investment policy statement (stored
as versions), the drift report against it, and the risk profile shown beside
it (tolerance, capacity, and the lower of the two).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, ValidationError

from salli.domain.portfolio.policy import AssetClass
from salli.interfaces.api.contract import Amount, CurrencyCode, DecimalIn, DecimalOut
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/ips", tags=["portfolio"])


class PolicyTargetIn(BaseModel):
    #: One of the controlled taxonomy's classes or sub-classes ("equity",
    #: "equity.international"); a class or its sub-classes, not both.
    asset_class: AssetClass
    #: Its target share of the portfolio, a fraction ("0.6").
    target: DecimalIn
    #: How far either side of the target its share may move ("0.05").
    band: DecimalIn = Decimal("0.05")


class RebalancingRule(BaseModel):
    #: bands: when a class leaves its band; calendar: every `every_months`;
    #: both: whichever comes first.
    rule: Literal["bands", "calendar", "both"] = "bands"
    every_months: int | None = Field(default=None, ge=1, le=120)


class InvestmentPolicyRequest(BaseModel):
    #: The targets add up to 1.
    targets: list[PolicyTargetIn] = Field(min_length=1, max_length=40)
    rebalancing: RebalancingRule = RebalancingRule()
    horizon_years: int | None = Field(default=None, ge=0, le=100)
    objectives: str = Field(default="", max_length=2000)
    constraints: str = Field(default="", max_length=2000)
    review_on: dt.date | None = None
    #: Needed when the equity target is above your risk profile's band:
    #: why, in your words. Stored with the version.
    override_reason: str | None = Field(default=None, min_length=1, max_length=1000)


class PolicyTargetOut(BaseModel):
    asset_class: str
    target: DecimalOut
    band: DecimalOut


class InvestmentPolicyContent(BaseModel):
    schema_: Literal["salli.ips/1"] = Field(alias="schema")
    targets: list[PolicyTargetOut]
    rebalancing: RebalancingRule
    horizon_years: int | None
    objectives: str
    constraints: str
    review_on: dt.date | None
    override_reason: str | None = None


class InvestmentPolicyVersion(BaseModel):
    id: str
    version: int
    content: InvestmentPolicyContent
    created_at: str


class InvestmentPolicyVersions(BaseModel):
    #: Oldest first; the last is the one in force.
    versions: list[InvestmentPolicyVersion]


class RiskTolerance(BaseModel):
    #: 0-100, from the questionnaire; None until it is answered.
    score: int | None
    category: Literal["conservative", "balanced", "aggressive"] | None


class RiskCapacityFigures(BaseModel):
    #: 0-100, over the measures present.
    score: int
    category: Literal["conservative", "balanced", "aggressive"]
    #: Points per measure (0-25 each).
    breakdown: dict[str, int]
    #: Measures left out for want of figures.
    missing: list[str]
    emergency_months: DecimalOut | None
    #: Monthly income's standard deviation ÷ its mean.
    income_variation: DecimalOut | None
    horizon_years: int | None
    #: Scheduled debt payments ÷ monthly income.
    debt_service_ratio: DecimalOut | None


class RiskNeed(BaseModel):
    """The return the plan requires, beside the profile, never folded in."""

    #: The yearly real return your asset base and monthly saving need to
    #: reach your FI number within the horizon; null without a horizon, or
    #: when none up to 0.20 does.
    required_return: DecimalOut | None
    #: The least profile whose band covers it; null without a horizon.
    category: Literal["conservative", "balanced", "aggressive"] | None
    #: The need asks more than the profile takes.
    above_profile: bool
    says: str


class RiskMethod(BaseModel):
    """The method's cut-offs, disclosed beside every read (docs/risk.md)."""

    doc: str
    #: Category → the score range (0-100) it covers, for tolerance and capacity.
    score_buckets: dict[str, str]
    #: Category → the most equity it is described as suited to.
    equity_max: dict[str, DecimalOut]
    #: Category → the most real return a year it is described as reaching for.
    need_max: dict[str, DecimalOut]
    says: str


class InvestorRiskProfile(BaseModel):
    tolerance: RiskTolerance
    capacity: RiskCapacityFigures
    need: RiskNeed
    #: The lower of tolerance and capacity. A policy whose equity target is
    #: above its band needs an override with a reason.
    profile: Literal["conservative", "balanced", "aggressive"]
    #: The most of a portfolio in equity this profile is described as suited to.
    equity_max: DecimalOut
    method: RiskMethod


class DriftClass(BaseModel):
    asset_class: str
    value: Amount
    current_pct: DecimalOut
    target_pct: DecimalOut
    band: DecimalOut
    #: Current minus target: positive is above it.
    drift_pct: DecimalOut
    outside_band: bool
    #: What would bring the class to its target: positive in, negative out.
    to_target: Amount
    #: False for a class held that the policy has no target for.
    in_policy: bool


class EquityCheck(BaseModel):
    equity_target: DecimalOut
    profile: Literal["conservative", "balanced", "aggressive"]
    profile_equity_max: DecimalOut
    #: The policy's equity target is above the risk profile's band.
    above_profile: bool
    #: The reason stored with the version, when it overrode the band.
    override_reason: str | None = None


class LotToSell(BaseModel):
    holding_id: str
    symbol: str
    lot_id: str
    opened_on: str
    #: "short" or "long" by your tax rules' line; null without one.
    holding_period: Literal["short", "long"] | None = None
    quantity: DecimalOut
    proceeds: Amount
    realised_gain: Amount


class TaxAwareSale(BaseModel):
    """For a class above its target: the open lots that, sold, bring it to
    target with the least realised gain (losses first). Figures, not advice:
    whether to sell is yours."""

    asset_class: str
    to_sell: Amount
    lots: list[LotToSell]
    realised_gain: Amount


class DriftReport(BaseModel):
    version: int
    currency: CurrencyCode
    total_value: Amount
    classes: list[DriftClass]
    #: The policy's rebalancing rule says it is time.
    rebalance_due: bool
    #: The policy's review date has come.
    review_due: bool
    risk_profile: InvestorRiskProfile
    equity_check: EquityCheck
    tax_aware_sales: list[TaxAwareSale]
    notes: list[str]


@router.get("")
async def get_policy(user_id: CurrentUser, svc: AppServices) -> InvestmentPolicyVersion:
    """The investment policy statement in force (its latest version)."""
    current = await svc.investment_policy.current(user_id)
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No investment policy yet")
    return InvestmentPolicyVersion.model_validate(current)


@router.post("", status_code=status.HTTP_201_CREATED)
async def adopt_policy(
    body: InvestmentPolicyRequest, user_id: CurrentUser, svc: AppServices
) -> InvestmentPolicyVersion:
    """Adopt a new version of the investment policy statement. Earlier
    versions are kept, never changed."""
    try:
        stored = await svc.investment_policy.adopt(user_id, body.model_dump(mode="json"))
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "; ".join(str(e["msg"]).removeprefix("Value error, ") for e in exc.errors()),
        ) from exc
    return InvestmentPolicyVersion.model_validate(stored)


@router.get("/versions")
async def list_policy_versions(user_id: CurrentUser, svc: AppServices) -> InvestmentPolicyVersions:
    return InvestmentPolicyVersions(
        versions=[
            InvestmentPolicyVersion.model_validate(v)
            for v in await svc.investment_policy.versions(user_id)
        ]
    )


@router.get("/drift")
async def get_drift(user_id: CurrentUser, svc: AppServices) -> DriftReport:
    """The portfolio against the policy in force, class by class, with the
    risk profile beside it."""
    report = await svc.investment_policy.drift(user_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No investment policy yet")
    return DriftReport.model_validate(report)


@router.get("/risk-profile")
async def get_risk_profile(user_id: CurrentUser, svc: AppServices) -> InvestorRiskProfile:
    """Risk tolerance (the questionnaire), risk capacity (the baseline) and
    the profile, the lower of the two."""
    return InvestorRiskProfile.model_validate(await svc.investment_policy.risk_profile(user_id))
