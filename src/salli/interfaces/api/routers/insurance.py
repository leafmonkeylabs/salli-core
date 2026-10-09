"""
Insurance router — policy inventory, declared coverage targets, and the
coverage-gap report.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/insurance", tags=["insurance"])


class PolicyRequest(BaseModel):
    name: str
    policy_type: str
    provider: str
    coverage_amount: float
    premium_amount: float
    premium_frequency: str
    expiry_date: str


class PolicyUpdateRequest(BaseModel):
    name: str | None = None
    policy_type: str | None = None
    provider: str | None = None
    coverage_amount: float | None = None
    premium_amount: float | None = None
    premium_frequency: str | None = None
    expiry_date: str | None = None
    is_active: bool | None = None


class TargetRequest(BaseModel):
    policy_type: str
    target_amount: float


@router.get("/policies")
async def list_policies(user_id: CurrentUser, svc: AppServices, active_only: bool = True):
    return {"policies": await svc.insurance.list_policies(user_id, active_only)}


@router.post("/policies", status_code=status.HTTP_201_CREATED)
async def add_policy(body: PolicyRequest, user_id: CurrentUser, svc: AppServices):
    policy_id = await svc.insurance.add_policy(user_id, body.model_dump())
    return {"id": policy_id}


@router.get("/report")
async def get_coverage_report(user_id: CurrentUser, svc: AppServices):
    """Coverage-gap report: target vs. actual coverage per type, missing types,
    and policies expiring within the next 30 days."""
    today = datetime.date.today().isoformat()
    return await svc.insurance.get_report(user_id, today)


@router.get("/targets")
async def list_targets(user_id: CurrentUser, svc: AppServices):
    return {"targets": await svc.insurance.list_targets(user_id)}


@router.put("/targets")
async def set_target(body: TargetRequest, user_id: CurrentUser, svc: AppServices):
    from decimal import Decimal

    target_id = await svc.insurance.set_target(
        user_id, body.policy_type, Decimal(str(body.target_amount))
    )
    return {"id": target_id}


@router.delete("/targets/{policy_type}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(policy_type: str, user_id: CurrentUser, svc: AppServices):
    await svc.insurance.delete_target(user_id, policy_type)


@router.get("/policies/{policy_id}")
async def get_policy(policy_id: str, user_id: CurrentUser, svc: AppServices):
    policy = await svc.insurance.get_policy(user_id, policy_id)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return policy


@router.patch("/policies/{policy_id}")
async def update_policy(
    policy_id: str, body: PolicyUpdateRequest, user_id: CurrentUser, svc: AppServices
):
    await svc.insurance.update_policy(user_id, policy_id, body.model_dump(exclude_none=True))
    return {"updated": True}


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(policy_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.insurance.delete_policy(user_id, policy_id)
