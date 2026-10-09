"""
Subscriptions router — declared recurring-expense expectations and their
missed-charge/price-change reports.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from salli.domain.subscription.models import AlertKind
from salli.interfaces.api.contract import Amount, AmountIn, CurrencyCode, DecimalIn, Ref, Updated
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class SubscriptionRequest(BaseModel):
    name: str
    amount: AmountIn
    frequency: Literal["weekly", "monthly", "quarterly", "yearly"]
    next_due_date: str
    account_id: str | None = None
    grace_days: int = 5
    #: How far a charge may differ before it counts as a price change ("0.05" is 5%).
    amount_tolerance_pct: DecimalIn = Decimal("0.05")


class SubscriptionUpdateRequest(BaseModel):
    name: str | None = None
    amount: AmountIn | None = None
    frequency: Literal["weekly", "monthly", "quarterly", "yearly"] | None = None
    next_due_date: str | None = None
    account_id: str | None = None
    grace_days: int | None = None
    amount_tolerance_pct: DecimalIn | None = None
    is_active: bool | None = None


class Subscription(BaseModel):
    id: str
    name: str
    #: The charge expected each period.
    amount: Amount
    #: Kept in the base currency, like the ledger entries charges are matched in.
    currency: CurrencyCode
    #: "weekly", "monthly", "quarterly" or "yearly" — as stored, which nothing enforces.
    frequency: str
    next_due_date: str  # YYYY-MM-DD
    #: The expense account charges are matched in; null matches any expense near `amount`.
    account_id: str | None
    grace_days: int
    #: How far a charge may stray from `amount`, as a decimal-string fraction ("0.05" is 5%).
    amount_tolerance_pct: str
    is_active: bool
    created_at: str
    updated_at: str


class SubscriptionList(BaseModel):
    subscriptions: list[Subscription]


class SubscriptionMatch(BaseModel):
    """A posted charge taken to be this subscription's."""

    entry_id: str
    entry_date: str
    amount: Amount


class SubscriptionAlert(BaseModel):
    kind: AlertKind
    message: str
    #: Set for a price change; null for a missed charge.
    expected_amount: Amount | None
    actual_amount: Amount | None


class SubscriptionReport(BaseModel):
    subscription_id: str
    name: str
    currency: CurrencyCode
    matches: list[SubscriptionMatch]
    alerts: list[SubscriptionAlert]


class SubscriptionReportList(BaseModel):
    reports: list[SubscriptionReport]


@router.get("/")
async def list_subscriptions(
    user_id: CurrentUser, svc: AppServices, active_only: bool = True
) -> SubscriptionList:
    subscriptions = await svc.subscription.list_subscriptions(user_id, active_only)
    return SubscriptionList.model_validate({"subscriptions": subscriptions})


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_subscription(
    body: SubscriptionRequest, user_id: CurrentUser, svc: AppServices
) -> Ref:
    subscription_id = await svc.subscription.add_subscription(user_id, body.model_dump())
    return Ref(id=subscription_id)


@router.get("/reports")
async def get_all_reports(user_id: CurrentUser, svc: AppServices) -> SubscriptionReportList:
    """Missed-charge/price-change reports for every active subscription."""
    today = datetime.date.today().isoformat()
    reports = await svc.subscription.get_all_reports(user_id, today)
    return SubscriptionReportList.model_validate({"reports": reports})


@router.get("/{subscription_id}")
async def get_subscription(
    subscription_id: str, user_id: CurrentUser, svc: AppServices
) -> Subscription:
    subscription = await svc.subscription.get_subscription(user_id, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return Subscription.model_validate(subscription)


@router.patch("/{subscription_id}")
async def update_subscription(
    subscription_id: str, body: SubscriptionUpdateRequest, user_id: CurrentUser, svc: AppServices
) -> Updated:
    await svc.subscription.update_subscription(
        user_id, subscription_id, body.model_dump(exclude_none=True)
    )
    return Updated(updated=True)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(subscription_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    await svc.subscription.delete_subscription(user_id, subscription_id)


@router.get("/{subscription_id}/report")
async def get_subscription_report(
    subscription_id: str, user_id: CurrentUser, svc: AppServices
) -> SubscriptionReport:
    """Missed-charge/price-change report for a single subscription."""
    today = datetime.date.today().isoformat()
    report = await svc.subscription.get_report(user_id, subscription_id, today)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return SubscriptionReport.model_validate(report)
