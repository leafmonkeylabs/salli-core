"""
Portfolio router — investment holdings, their transactions, lots and prices,
allocation and rebalancing, and gains, income and returns.

A holding's figures come from its transactions, valued at the latest price the
user recorded; a holding without transactions keeps the figures the user
declared. Nothing here fetches a price: Salli has no market feed.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from salli.interfaces.api.contract import (
    Amount,
    AmountIn,
    CurrencyCode,
    DecimalIn,
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


# ── Transactions ──────────────────────────────────────────────────────────────

TransactionKind = Literal["buy", "sell", "dividend", "interest", "split", "transfer_in"]

_RATIO = r"^\d+(\.\d+)?(:\d+(\.\d+)?)?$"


class LotPickRequest(BaseModel):
    #: A lot's id: the id of the buy or transfer in that opened it.
    lot_id: str
    quantity: DecimalIn


class HoldingTransactionRequest(BaseModel):
    """One event in a holding's history. What it takes depends on `kind`:

    - buy, sell: `quantity`, `price` per unit, `fees`; a sale may name the
      `lots` it sells (otherwise the oldest go first);
    - transfer_in: `quantity` and `amount`, the total cost of units brought in
      from elsewhere (date it with their purchase);
    - dividend, interest: `amount`, gross, and any `withholding_tax`;
    - split: `ratio`, new units to old ("2:1", or "1:10" for a reverse split).

    A field the kind does not take is refused (422). Money is in the
    holding's currency.
    """

    kind: TransactionKind
    date: dt.date
    quantity: DecimalIn | None = None
    price: DecimalIn | None = None
    fees: AmountIn | None = None
    amount: AmountIn | None = None
    withholding_tax: AmountIn | None = None
    ratio: str | None = Field(None, pattern=_RATIO, examples=["2:1"])
    lots: list[LotPickRequest] | None = None
    #: Units of the base currency per unit of the holding's, on `date`: the
    #: rate the broker used. Omitted: 1 for a holding in the base currency,
    #: else the published rate for the date (422 if there is none: give it).
    fx_rate: DecimalIn | None = None
    #: Where `fx_rate` came from ("broker", say). Default "user".
    fx_rate_source: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=500)


class HoldingTransactionUpdateRequest(BaseModel):
    """The fields to change; the rest stay. A transaction's kind cannot
    change. A new `date` takes that day's published rate unless `fx_rate` is
    given with it."""

    kind: TransactionKind | None = None
    date: dt.date | None = None
    quantity: DecimalIn | None = None
    price: DecimalIn | None = None
    fees: AmountIn | None = None
    amount: AmountIn | None = None
    withholding_tax: AmountIn | None = None
    ratio: str | None = Field(None, pattern=_RATIO, examples=["2:1"])
    lots: list[LotPickRequest] | None = None
    fx_rate: DecimalIn | None = None
    fx_rate_source: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=500)


class LotPick(BaseModel):
    lot_id: str
    quantity: DecimalOut


class HoldingTransaction(BaseModel):
    id: str
    holding_id: str
    kind: TransactionKind
    date: str
    #: The holding's currency: `fees`, `amount`, `withholding_tax` and
    #: `total` are in it.
    currency: CurrencyCode
    #: Units, for a buy, sale or transfer in.
    quantity: DecimalOut | None
    #: Per unit, for a buy or sale.
    price: DecimalOut | None
    fees: Amount
    #: Gross income, or a transfer's total cost.
    amount: Amount | None
    withholding_tax: Amount
    #: A split's new units to old, "2:1".
    ratio: str | None
    #: The lots a sale named; empty when it sold the oldest first.
    lots: list[LotPick]
    #: Base currency per unit of the holding's, on `date`; null for a split.
    fx_rate: DecimalOut | None
    #: "user" for a rate given with the transaction, else where it came from.
    fx_rate_source: str | None
    #: The money it moved: paid for a buy (with fees), received for a sale
    #: (less fees) or income (less tax), the cost of a transfer in; null for
    #: a split.
    total: Amount | None
    note: str | None
    created_at: str
    updated_at: str


class HoldingTransactionList(BaseModel):
    #: In the order they take effect: by date, and on one date splits, then
    #: acquisitions, sales and income.
    transactions: list[HoldingTransaction]


# ── Lots ──────────────────────────────────────────────────────────────────────


class HoldingLot(BaseModel):
    """Units acquired together, by a buy or a transfer in (whose id it has)."""

    id: str
    kind: Literal["buy", "transfer_in"]
    opened_on: str
    #: The units it opened with, scaled by any split since.
    opened_quantity: DecimalOut
    #: The units still held; 0 once sold.
    quantity: DecimalOut
    #: What the units still held cost, in the holding's currency.
    cost: Amount
    #: The same in the base currency, at the rate of the day it was opened.
    cost_base: Amount
    cost_per_unit: DecimalOut | None
    is_open: bool


class LotConsumption(BaseModel):
    """The part of one lot a sale used up."""

    lot_id: str
    opened_on: str
    quantity: DecimalOut
    cost: Amount
    cost_base: Amount


class HoldingSale(BaseModel):
    """A sale and the gain it realised: proceeds − fees − the cost of the
    lots it consumed; `*_base` in the base currency, the proceeds at the
    sale's rate and the cost at each lot's."""

    transaction_id: str
    date: str
    quantity: DecimalOut
    proceeds: Amount
    fees: Amount
    cost: Amount
    gain: Amount
    fx_rate: DecimalOut
    proceeds_base: Amount
    fees_base: Amount
    cost_base: Amount
    gain_base: Amount
    consumed: list[LotConsumption]


class HoldingLots(BaseModel):
    holding_id: str
    #: The holding's currency.
    currency: CurrencyCode
    base_currency: CurrencyCode
    #: Units held, and what they cost.
    quantity: DecimalOut
    cost: Amount
    cost_base: Amount
    #: Every lot ever opened, open and closed, in the order sales consume them.
    lots: list[HoldingLot]
    sales: list[HoldingSale]


# ── Prices ────────────────────────────────────────────────────────────────────


class PriceRequest(BaseModel):
    """A closing price, as quoted that day. Recording another for the same
    symbol and day replaces it."""

    symbol: str = Field(min_length=1, max_length=20)
    close: DecimalIn
    #: Omitted: today.
    date: dt.date | None = None
    #: Omitted: the currency of your holdings with this symbol.
    currency: str | None = None


class RecordedPrice(BaseModel):
    id: str
    symbol: str
    date: str
    close: DecimalOut
    currency: CurrencyCode
    #: "user" for a price recorded by hand.
    source: str
    created_at: str
    updated_at: str


class RecordedPriceList(BaseModel):
    #: Newest first.
    prices: list[RecordedPrice]


# ── Performance ───────────────────────────────────────────────────────────────


class PerformanceFigures(BaseModel):
    """A holding's or the portfolio's figures for the period, in one currency.

    Values are at the latest price on or before the day (carried at cost, and
    noted, without one). Money in: units bought or transferred in. Money out:
    sales' proceeds less fees, and income net of tax. Rates of return are
    decimal fractions of one ("0.073512" is 7.3512%), to six places.
    """

    currency: CurrencyCode
    #: What was held at the end of the day before the period, and its cost.
    opening_value: Amount
    opening_cost: Amount
    opening_unrealised_gain: Amount
    #: What was held at the end of the period, and its cost.
    closing_value: Amount
    closing_cost: Amount
    unrealised_gain: Amount
    #: The gains of the sales in the period.
    realised_gain: Amount
    #: Income in the period: gross, the tax withheld from it, and received.
    dividends: Amount
    interest: Amount
    withholding_tax: Amount
    net_income: Amount
    paid_in: Amount
    taken_out: Amount
    #: closing_value − opening_value − paid_in + taken_out; always realised
    #: + net income + the change in unrealised gain.
    total_return: Amount
    #: Time-weighted return over the period; null when nothing was at risk.
    twr: DecimalOut | None
    #: The same as a yearly rate; null for a period shorter than a year.
    twr_annualised: DecimalOut | None
    #: Money-weighted yearly return (XIRR); null without money both in and out
    #: (the closing value counts as out).
    xirr: DecimalOut | None


class HoldingPerformance(BaseModel):
    holding_id: str
    symbol: str
    name: str
    asset_class: str
    is_active: bool
    #: In the holding's own currency.
    native: PerformanceFigures
    #: In the base currency: each amount at the rate of its day.
    base: PerformanceFigures
    #: Any valuation carried at cost, and why.
    notes: list[str]


class PortfolioPerformance(BaseModel):
    #: The period's first day: `from_date`, or the first transaction's.
    start: str
    end: str
    days: int
    base_currency: CurrencyCode
    #: The holdings reported on, together, in the base currency.
    portfolio: PerformanceFigures
    #: Every holding with transactions, inactive ones included: a sale's gain
    #: belongs to its tax year.
    holdings: list[HoldingPerformance]
    #: What is left out (holdings declared by value have no history).
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


_FROM = Query(None, description="First day of the period, YYYY-MM-DD. Omitted: inception.")
_TO = Query(None, description="Last day of the period, YYYY-MM-DD. Omitted: today.")


@router.get("/performance")
async def get_performance(
    user_id: CurrentUser,
    svc: AppServices,
    from_date: dt.date | None = _FROM,
    to_date: dt.date | None = _TO,
) -> PortfolioPerformance:
    """Gains, income and returns over a period (a tax year, say), per holding
    in its own currency and the base one, and for the whole portfolio."""
    report = await svc.portfolio.get_performance(user_id, from_date, to_date)
    return PortfolioPerformance.model_validate(report)


@router.get("/prices")
async def list_prices(
    user_id: CurrentUser,
    svc: AppServices,
    symbol: str | None = None,
    from_date: dt.date | None = Query(None, description="YYYY-MM-DD"),
    to_date: dt.date | None = Query(None, description="YYYY-MM-DD"),
) -> RecordedPriceList:
    """The closing prices recorded, newest first: one symbol's, or every one."""
    prices = await svc.portfolio.list_prices(
        user_id,
        symbol,
        from_date.isoformat() if from_date else None,
        to_date.isoformat() if to_date else None,
    )
    return RecordedPriceList.model_validate({"prices": prices})


@router.post("/prices", status_code=status.HTTP_201_CREATED)
async def set_price(body: PriceRequest, user_id: CurrentUser, svc: AppServices) -> Ref:
    """Record a closing price. Nothing fetches prices: holdings are valued at
    the ones recorded here."""
    quote_id = await svc.portfolio.set_price(user_id, body.model_dump(exclude_none=True))
    return Ref(id=quote_id)


@router.delete("/prices/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_price(quote_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    if not await svc.portfolio.delete_price(user_id, quote_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such price")


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


_NO_HOLDING = "No such holding"
_NO_TRANSACTION = "No such transaction"


@router.get("/{holding_id}/transactions")
async def list_transactions(
    holding_id: str, user_id: CurrentUser, svc: AppServices
) -> HoldingTransactionList:
    transactions = await svc.portfolio.list_transactions(user_id, holding_id)
    if transactions is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_HOLDING)
    return HoldingTransactionList.model_validate({"transactions": transactions})


@router.post("/{holding_id}/transactions", status_code=status.HTTP_201_CREATED)
async def add_transaction(
    holding_id: str, body: HoldingTransactionRequest, user_id: CurrentUser, svc: AppServices
) -> Ref:
    """Record a transaction. The whole history is checked first: a sale of
    more than was held then, or of a lot that was not, is a 422."""
    transaction_id = await svc.portfolio.add_transaction(
        user_id, holding_id, body.model_dump(exclude_none=True)
    )
    if transaction_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_HOLDING)
    return Ref(id=transaction_id)


@router.get("/{holding_id}/transactions/{transaction_id}")
async def get_transaction(
    holding_id: str, transaction_id: str, user_id: CurrentUser, svc: AppServices
) -> HoldingTransaction:
    transaction = await svc.portfolio.get_transaction(user_id, holding_id, transaction_id)
    if transaction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_TRANSACTION)
    return HoldingTransaction.model_validate(transaction)


@router.patch("/{holding_id}/transactions/{transaction_id}")
async def update_transaction(
    holding_id: str,
    transaction_id: str,
    body: HoldingTransactionUpdateRequest,
    user_id: CurrentUser,
    svc: AppServices,
) -> Ref:
    """Change a transaction, if the history still stands with the change."""
    if not await svc.portfolio.update_transaction(
        user_id, holding_id, transaction_id, body.model_dump(exclude_none=True)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_TRANSACTION)
    return Ref(id=transaction_id)


@router.delete(
    "/{holding_id}/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_transaction(
    holding_id: str, transaction_id: str, user_id: CurrentUser, svc: AppServices
) -> None:
    """Delete a transaction, unless a later sale needs it (422)."""
    if not await svc.portfolio.delete_transaction(user_id, holding_id, transaction_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_TRANSACTION)


@router.get("/{holding_id}/lots")
async def get_lots(holding_id: str, user_id: CurrentUser, svc: AppServices) -> HoldingLots:
    """The holding's lots and each sale with the lots it consumed."""
    lots = await svc.portfolio.get_lots(user_id, holding_id)
    if lots is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_HOLDING)
    return HoldingLots.model_validate(lots)


@router.get("/{holding_id}/performance")
async def get_holding_performance(
    holding_id: str,
    user_id: CurrentUser,
    svc: AppServices,
    from_date: dt.date | None = _FROM,
    to_date: dt.date | None = _TO,
) -> PortfolioPerformance:
    """One holding's gains, income and returns over a period."""
    report = await svc.portfolio.get_performance(user_id, from_date, to_date, holding_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_NO_HOLDING)
    return PortfolioPerformance.model_validate(report)
