"""
Subscriptions router — declared recurring-expense expectations and their
missed-charge/price-change reports.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class SubscriptionRequest(BaseModel):
    name: str
    amount: float
    frequency: str
    next_due_date: str
    account_id: str | None = None
    grace_days: int = 5
    amount_tolerance_pct: float = 0.05


class SubscriptionUpdateRequest(BaseModel):
    name: str | None = None
    amount: float | None = None
    frequency: str | None = None
    next_due_date: str | None = None
    account_id: str | None = None
    grace_days: int | None = None
    amount_tolerance_pct: float | None = None
    is_active: bool | None = None


@router.get("/")
async def list_subscriptions(user_id: CurrentUser, svc: AppServices, active_only: bool = True):
    return {"subscriptions": await svc.subscription.list_subscriptions(user_id, active_only)}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_subscription(body: SubscriptionRequest, user_id: CurrentUser, svc: AppServices):
    subscription_id = await svc.subscription.add_subscription(user_id, body.model_dump())
    return {"id": subscription_id}


@router.get("/reports")
async def get_all_reports(user_id: CurrentUser, svc: AppServices):
    """Missed-charge/price-change reports for every active subscription."""
    today = datetime.date.today().isoformat()
    return {"reports": await svc.subscription.get_all_reports(user_id, today)}


@router.get("/{subscription_id}")
async def get_subscription(subscription_id: str, user_id: CurrentUser, svc: AppServices):
    subscription = await svc.subscription.get_subscription(user_id, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return subscription


@router.patch("/{subscription_id}")
async def update_subscription(
    subscription_id: str, body: SubscriptionUpdateRequest, user_id: CurrentUser, svc: AppServices
):
    await svc.subscription.update_subscription(
        user_id, subscription_id, body.model_dump(exclude_none=True)
    )
    return {"updated": True}


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(subscription_id: str, user_id: CurrentUser, svc: AppServices):
    await svc.subscription.delete_subscription(user_id, subscription_id)


@router.get("/{subscription_id}/report")
async def get_subscription_report(subscription_id: str, user_id: CurrentUser, svc: AppServices):
    """Missed-charge/price-change report for a single subscription."""
    today = datetime.date.today().isoformat()
    report = await svc.subscription.get_report(user_id, subscription_id, today)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return report
