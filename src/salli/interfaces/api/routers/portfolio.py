"""
Portfolio router — investment holdings, their transactions, lots and prices,
allocation and rebalancing, and gains, income and returns.

A holding's figures come from its transactions, valued at the latest price the
user recorded; a holding without transactions keeps the figures the user
declared. Nothing here fetches a price: Salli has no market feed.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from salli.interfaces.api.contract import (
    Amount,
    AmountIn,
    CurrencyCode,
    DecimalOut,
    Ref,
    Updated,
)
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class HoldingRequest(BaseModel):
    symbol: str
    name: str
    asset_class: str
    #: ISO 4217 code the holding trades in. Omitted: the base currency.
    currency: str | None = None
    #: Declared figures, in the base currency, for a holding tracked without
    #: transactions; one in another currency is tracked by its transactions.
    #: Omitted: 0 (record its transactions instead).
    cost_basis: AmountIn = Decimal(0)
    current_value: AmountIn = Decimal(0)


class HoldingUpdateRequest(BaseModel):
    symbol: str | None = None
    name: str | None = None
    asset_class: str | None = None
    #: Only while the holding has no transactions.
    currency: str | None = None
    #: Only for a holding without transactions (422 otherwise: its figures
    #: come from its transactions and prices).
    cost_basis: AmountIn | None = None
    current_value: AmountIn | None = None
    is_active: bool | None = None


class QuotedPrice(BaseModel):
    """The price a holding is valued at."""

    #: The day it was quoted.
    date: str
    #: As quoted that day.
    close: DecimalOut
    #: Per unit held now: the close adjusted for any split since.
    per_unit: DecimalOut
    #: "user" for a price the user recorded; "trade" for the price of the
    #: holding's own latest buy or sale.
    source: str


class NativeFigures(BaseModel):
    """A holding's figures in its own currency."""

    currency: CurrencyCode
    cost_basis: Amount
    current_value: Amount
    unrealised_gain: Amount


class Holding(BaseModel):
    id: str
    symbol: str
    name: str
    #: As the user named it: "equity", "bond", "cash", "real_estate", "crypto", …
    asset_class: str
    #: The base currency: `cost_basis`, `current_value` and `unrealised_gain`
    #: are in it. The holding's own currency is `native.currency`.
    currency: CurrencyCode
    #: What the units still held cost, each lot at the rate of the day it was
    #: bought; as declared, for a holding without transactions.
    cost_basis: Amount
    #: Quantity × the latest recorded price, at the rate of that price's day;
    #: as declared, for a holding without transactions. There is no market feed.
    current_value: Amount
    is_active: bool
    created_at: str
    updated_at: str
    #: "transactions" when the figures come from the holding's transactions,
    #: "declared" when they are the ones the user declared.
    tracking: Literal["declared", "transactions"]
    #: current_value − cost_basis.
    unrealised_gain: Amount
    native: NativeFigures
    #: Units held; null for a declared holding.
    quantity: DecimalOut | None
    #: Null for a declared holding, or one with no price yet.
    price: QuotedPrice | None
    #: Base currency per unit of the holding's, on the price's day.
    fx_rate: DecimalOut | None
    #: False when there is no price, so the holding is valued at what it cost.
    #: Null for a declared holding.
    priced: bool | None
    #: False when there is no rate for the price's day, so the base value is
    #: carried at cost. Null for a declared holding.
    converted: bool | None
    #: Anything carried at cost, and why.
    notes: list[str]


class HoldingList(BaseModel):
    holdings: list[Holding]


# The shares, gains and drifts below are decimal strings that are fractions of
# one ("0.6000" is 60%), not money.


class AllocationSlice(BaseModel):
    asset_class: str
    current_value: Amount
    #: Its share of the portfolio's value.
    pct_of_portfolio: str


class RebalancingAlert(BaseModel):
    """An asset class whose share has drifted from its target by the threshold or more."""

    asset_class: str
    current_pct: str
    #: The target as the request gave it.
    target_pct: str
    #: Current minus target: positive is overweight, negative underweight.
    drift_pct: str


class PortfolioSummary(BaseModel):
    """The active holdings, each valued as `holdings.list` values it."""

    currency: CurrencyCode
    total_value: Amount
    total_cost_basis: Amount
    #: Total value minus total cost basis.
    total_gain: Amount
    #: The gain over the cost basis; zero when nothing was invested.
    total_gain_pct: str
    allocation: list[AllocationSlice]
    #: Empty unless a target allocation was given.
    alerts: list[RebalancingAlert]
    #: Any holding carried at cost, and why.
    notes: list[str]


def _parse_target(target: list[str]) -> dict[str, Decimal] | None:
    if not target:
        return None
    parsed: dict[str, Decimal] = {}
    for pair in target:
        asset_class, _, pct = pair.partition(":")
        try:
            share = Decimal(pct)
        except InvalidOperation:
            share = None
        # A share is a fraction, 0 to 1. "abc" used to escape as a 500, and
        # "NaN" or "Infinity" read as numbers.
        if not asset_class or share is None or not share.is_finite() or not 0 <= share <= 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid target entry '{pair}'. Use asset_class:share, e.g. equity:0.6.",
            )
        parsed[asset_class] = share
    return parsed


@router.get("/")
async def list_holdings(
    user_id: CurrentUser, svc: AppServices, active_only: bool = True
) -> HoldingList:
    holdings = await svc.portfolio.list_holdings(user_id, active_only)
    return HoldingList.model_validate({"holdings": holdings})


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_holding(body: HoldingRequest, user_id: CurrentUser, svc: AppServices) -> Ref:
    holding_id = await svc.portfolio.add_holding(user_id, body.model_dump())
    return Ref(id=holding_id)


@router.get("/summary")
async def get_summary(
    user_id: CurrentUser,
    svc: AppServices,
    target: list[str] = Query([], description="Repeatable asset_class:pct, e.g. equity:0.6"),
) -> PortfolioSummary:
    """Allocation by asset class, total gain/ROI, and (if target given) rebalancing alerts."""
    summary = await svc.portfolio.get_summary(user_id, _parse_target(target))
    return PortfolioSummary.model_validate(summary)


@router.get("/{holding_id}")
async def get_holding(holding_id: str, user_id: CurrentUser, svc: AppServices) -> Holding:
    holding = await svc.portfolio.get_holding(user_id, holding_id)
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")
    return Holding.model_validate(holding)


@router.patch("/{holding_id}")
async def update_holding(
    holding_id: str, body: HoldingUpdateRequest, user_id: CurrentUser, svc: AppServices
) -> Updated:
    if await svc.portfolio.get_holding(user_id, holding_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such holding")
    await svc.portfolio.update_holding(user_id, holding_id, body.model_dump(exclude_none=True))
    return Updated(updated=True)


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(holding_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    await svc.portfolio.delete_holding(user_id, holding_id)
