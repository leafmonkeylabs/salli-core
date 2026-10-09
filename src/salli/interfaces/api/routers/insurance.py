"""
Insurance router — policy inventory, declared coverage targets, and the
coverage-gap report.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from salli.interfaces.api.contract import Amount, AmountIn, CurrencyCode, Ref, Updated
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/insurance", tags=["insurance"])


class PolicyRequest(BaseModel):
    name: str
    policy_type: str
    provider: str
    coverage_amount: AmountIn
    premium_amount: AmountIn
    premium_frequency: str
    expiry_date: str


class PolicyUpdateRequest(BaseModel):
    name: str | None = None
    policy_type: str | None = None
    provider: str | None = None
    coverage_amount: AmountIn | None = None
    premium_amount: AmountIn | None = None
    premium_frequency: str | None = None
    expiry_date: str | None = None
    is_active: bool | None = None


class TargetRequest(BaseModel):
    policy_type: str
    target_amount: AmountIn


# Policy types ("life", "health", "motor", "property", "other") and premium
# frequencies ("monthly", "quarterly", "yearly") are plain strings: they are
# stored as given, and nothing refuses others.


class InsurancePolicy(BaseModel):
    id: str
    name: str
    policy_type: str
    provider: str
    #: Coverage and premiums are kept in the base currency.
    currency: CurrencyCode
    coverage_amount: Amount
    premium_amount: Amount
    premium_frequency: str
    expiry_date: str  # YYYY-MM-DD
    is_active: bool
    created_at: str
    updated_at: str


class InsurancePolicyList(BaseModel):
    policies: list[InsurancePolicy]


class CoverageTarget(BaseModel):
    """The coverage wanted for one policy type."""

    id: str
    policy_type: str
    currency: CurrencyCode
    target_amount: Amount


class CoverageTargetList(BaseModel):
    targets: list[CoverageTarget]


class CoverageGapLine(BaseModel):
    policy_type: str
    target_amount: Amount
    #: The coverage of the active policies of this type, summed.
    actual_coverage: Amount
    #: Target minus actual: positive means under-covered.
    gap: Amount


class ExpiringPolicy(BaseModel):
    policy_name: str
    policy_type: str
    expiry_date: str
    days_until_expiry: int


class CoverageReport(BaseModel):
    currency: CurrencyCode
    #: One for each policy type with a target.
    lines: list[CoverageGapLine]
    #: Policy types with a target and no active coverage at all.
    missing_types: list[str]
    #: Active policies that expire within the next 30 days.
    expiring_soon: list[ExpiringPolicy]


@router.get("/policies")
async def list_policies(
    user_id: CurrentUser, svc: AppServices, active_only: bool = True
) -> InsurancePolicyList:
    policies = await svc.insurance.list_policies(user_id, active_only)
    return InsurancePolicyList.model_validate({"policies": policies})


@router.post("/policies", status_code=status.HTTP_201_CREATED)
async def add_policy(body: PolicyRequest, user_id: CurrentUser, svc: AppServices) -> Ref:
    policy_id = await svc.insurance.add_policy(user_id, body.model_dump())
    return Ref(id=policy_id)


@router.get("/report")
async def get_coverage_report(user_id: CurrentUser, svc: AppServices) -> CoverageReport:
    """Coverage-gap report: target vs. actual coverage per type, missing types,
    and policies expiring within the next 30 days."""
    today = datetime.date.today().isoformat()
    return CoverageReport.model_validate(await svc.insurance.get_report(user_id, today))


@router.get("/targets")
async def list_targets(user_id: CurrentUser, svc: AppServices) -> CoverageTargetList:
    return CoverageTargetList.model_validate({"targets": await svc.insurance.list_targets(user_id)})


@router.put("/targets")
async def set_target(body: TargetRequest, user_id: CurrentUser, svc: AppServices) -> Ref:
    from decimal import Decimal

    target_id = await svc.insurance.set_target(
        user_id, body.policy_type, Decimal(str(body.target_amount))
    )
    return Ref(id=target_id)


@router.delete("/targets/{policy_type}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(policy_type: str, user_id: CurrentUser, svc: AppServices) -> None:
    await svc.insurance.delete_target(user_id, policy_type)


@router.get("/policies/{policy_id}")
async def get_policy(policy_id: str, user_id: CurrentUser, svc: AppServices) -> InsurancePolicy:
    policy = await svc.insurance.get_policy(user_id, policy_id)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return InsurancePolicy.model_validate(policy)


@router.patch("/policies/{policy_id}")
async def update_policy(
    policy_id: str, body: PolicyUpdateRequest, user_id: CurrentUser, svc: AppServices
) -> Updated:
    await svc.insurance.update_policy(user_id, policy_id, body.model_dump(exclude_none=True))
    return Updated(updated=True)


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(policy_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    await svc.insurance.delete_policy(user_id, policy_id)
