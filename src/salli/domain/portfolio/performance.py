"""
Gains, income and returns over a period, for each holding and for the
portfolio. Pure: histories, prices and rates in; figures out.

The period runs from the start of `start` (the end of the day before) to the
end of `end`. With no `start` it runs from before the first transaction, when
nothing was held.

For each holding, in its own currency and in the base one, and for the
portfolio in the base one:

  realised          the gains of the sales dated in the period
  dividends,        income dated in the period, gross; `withholding_tax` the
  interest          tax withheld from it, `net_income` what was received
  unrealised        value − cost: at the period's opening and at its close
  paid_in,          money that went in (units bought at price × quantity +
  taken_out         fees, or transferred in at their stated cost) and came
                    out (sales' proceeds less fees, income net of tax)
  total_return      closing value − opening value − paid_in + taken_out, which
                    is always realised + net_income + the change in unrealised
  twr               the time-weighted return (returns.twr), from valuations
                    on every day money moved
  xirr              the money-weighted annual return (returns.xirr) of the
                    opening value, the money in and out, and the closing value

Valuations follow domain/portfolio/valuation.py: the latest price on or before
the day, adjusted for splits since; a holding with no price is carried at cost,
and its base value is carried at cost when there is no rate for its price's day.
Each valuation that had to be carried at cost is listed in `at_cost`, so the
figures never pass off cost as a price without saying so.

The portfolio's figures are the holdings' base-currency figures added up; its
time-weighted return is computed from the portfolio's own valuations on every
day money moved in any holding, and its money-weighted return from all their
money together.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext

from salli.domain.portfolio.lots import (
    EXACT,
    INCOME,
    ZERO,
    Kind,
    Position,
    Replay,
    Transaction,
    total,
)
from salli.domain.portfolio.returns import Day, Flow, twr, xirr
from salli.domain.portfolio.valuation import Pricing, Valuation

_EMPTY = Position(ZERO, ZERO, ZERO)
_DAY = timedelta(days=1)


@dataclass(frozen=True)
class History:
    """One holding: its transactions, its prices, and the rates into the base
    currency for the days of the closes its valuations use."""

    key: str
    transactions: Sequence[Transaction]
    pricing: Pricing
    rates: Mapping[date, Decimal]


@dataclass(frozen=True)
class Figures:
    """A holding's or the portfolio's figures for the period, in one currency."""

    opening_value: Decimal
    closing_value: Decimal
    opening_cost: Decimal
    closing_cost: Decimal
    realised: Decimal
    dividends: Decimal
    interest: Decimal
    withholding_tax: Decimal
    net_income: Decimal
    paid_in: Decimal
    taken_out: Decimal
    twr: Decimal | None
    xirr: Decimal | None

    @property
    def opening_unrealised(self) -> Decimal:
        with localcontext(EXACT):
            return self.opening_value - self.opening_cost

    @property
    def closing_unrealised(self) -> Decimal:
        with localcontext(EXACT):
            return self.closing_value - self.closing_cost

    @property
    def total_return(self) -> Decimal:
        with localcontext(EXACT):
            return self.closing_value - self.opening_value - self.paid_in + self.taken_out


@dataclass(frozen=True)
class AtCost:
    """A valuation that could not be marked to market."""

    on: date
    #: "price": there was no price; "rate": there was one, but no rate into
    #: the base currency for its day (so only the base value is at cost).
    missing: str
    #: The day of the price whose rate was missing.
    price_on: date | None = None


@dataclass(frozen=True)
class HoldingFigures:
    key: str
    native: Figures
    base: Figures
    #: The valuation at the period's close.
    closing: Valuation
    at_cost: tuple[AtCost, ...]


@dataclass(frozen=True)
class Report:
    #: The first day of the period (the first transaction's, with no `start`).
    start: date
    end: date
    holdings: tuple[HoldingFigures, ...]
    portfolio: Figures

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


def flow_days(histories: Sequence[History], start: date | None, end: date) -> list[date]:
    """The days in the period on which money moved in any of `histories`."""
    return sorted(
        {
            tx.on
            for h in histories
            for tx in h.transactions
            if tx.kind is not Kind.SPLIT and (start is None or tx.on >= start) and tx.on <= end
        }
    )


def valuation_days(histories: Sequence[History], start: date | None, end: date) -> list[date]:
    """Every day `report` values the holdings on: the eve of the period, each
    day money moved, and its last day. A caller finds the rates for these
    days' prices (`Pricing.rate_dates`) before calling `report`."""
    days = flow_days(histories, start, end)
    return ([start - _DAY] if start is not None else []) + days + [end]


@dataclass(frozen=True)
class _Moved:
    """Money in and out on one day, in the holding's currency and the base."""

    paid_in: Decimal
    taken_out: Decimal
    paid_in_base: Decimal
    taken_out_base: Decimal


def _money_moved(transactions: Sequence[Transaction]) -> dict[date, _Moved]:
    by_day: dict[date, list[Decimal]] = {}
    with localcontext(EXACT):
        for tx in transactions:
            if tx.kind is Kind.BUY:
                amount = tx.quantity * tx.price + tx.fees
            elif tx.kind is Kind.TRANSFER_IN:
                amount = tx.amount
            elif tx.kind is Kind.SELL:
                amount = -(tx.quantity * tx.price - tx.fees)
            elif tx.kind in INCOME:
                amount = -(tx.amount - tx.withholding_tax)
            else:
                continue
            sums = by_day.setdefault(tx.on, [ZERO, ZERO, ZERO, ZERO])
            # A sale whose fees exceed its proceeds puts money in.
            if amount >= 0:
                sums[0] += amount
                sums[2] += amount * tx.fx_rate
            else:
                sums[1] -= amount
                sums[3] -= amount * tx.fx_rate
    return {on: _Moved(*sums) for on, sums in by_day.items()}


@dataclass
class _Timeline:
    """One holding valued through the period."""

    opening: Valuation | None
    closing: Valuation
    # On each day money moved in the portfolio: valued before and after.
    days: dict[date, tuple[Valuation, Valuation]]
    moved: dict[date, _Moved]
    at_cost: list[AtCost]


def _timeline(h: History, start: date | None, days: Sequence[date], end: date) -> _Timeline:
    replay = Replay(h.transactions)
    at_cost: list[AtCost] = []

    def value(on: date, position: Position) -> Valuation:
        valuation = h.pricing.value(on, position, h.rates)
        if position.quantity > 0 and not valuation.priced:
            at_cost.append(AtCost(on, "price"))
        elif position.quantity > 0 and not valuation.converted:
            price_on = valuation.quote.on if valuation.quote else None
            at_cost.append(AtCost(on, "rate", price_on))
        return valuation

    opening = None
    if start is not None:
        eve = start - _DAY
        opening = value(eve, replay.advance(eve).position())
    valued: dict[date, tuple[Valuation, Valuation]] = {}
    for day in days:
        before = replay.advance(day, splits_only_on_last_day=True).position()
        after = replay.advance(day).position()
        valued[day] = (value(day, before), value(day, after))
    closing = value(end, replay.advance(end).position())
    unique = list(dict.fromkeys(at_cost))
    return _Timeline(opening, closing, valued, _money_moved(h.transactions), unique)


def _figures(
    h: History,
    line: _Timeline,
    start: date | None,
    end: date,
    *,
    base: bool,
) -> Figures:
    book = Replay(h.transactions).advance(end).book()
    in_period = [tx for tx in h.transactions if (start is None or tx.on >= start) and tx.on <= end]
    own_days = sorted({tx.on for tx in in_period if tx.kind is not Kind.SPLIT})
    sales = [s for s in book.sales if start is None or s.on >= start]
    income = [i for i in book.income if start is None or i.on >= start]

    def worth(v: Valuation | None) -> Decimal:
        return ZERO if v is None else (v.value_base if base else v.value)

    def cost(v: Valuation | None) -> Decimal:
        return ZERO if v is None else (v.cost_base if base else v.cost)

    def moved(day: date) -> tuple[Decimal, Decimal]:
        m = line.moved.get(day)
        if m is None:
            return ZERO, ZERO
        return (m.paid_in_base, m.taken_out_base) if base else (m.paid_in, m.taken_out)

    opening, closing = worth(line.opening), worth(line.closing)
    steps = [
        Day(day, worth(line.days[day][0]), worth(line.days[day][1]), *moved(day))
        for day in own_days
    ]
    flows = [Flow(start - _DAY, -opening)] if start is not None and opening else []
    flows += [Flow(s.on, s.outflow - s.inflow) for s in steps]
    flows.append(Flow(end, closing))
    with localcontext(EXACT):
        return Figures(
            opening_value=opening,
            closing_value=closing,
            opening_cost=cost(line.opening),
            closing_cost=cost(line.closing),
            realised=total(s.gain_base if base else s.gain for s in sales),
            dividends=total(
                i.gross_base if base else i.gross for i in income if i.kind is Kind.DIVIDEND
            ),
            interest=total(
                i.gross_base if base else i.gross for i in income if i.kind is Kind.INTEREST
            ),
            withholding_tax=total(
                i.withholding_tax_base if base else i.withholding_tax for i in income
            ),
            net_income=total(i.net_base if base else i.net for i in income),
            paid_in=total(s.inflow for s in steps),
            taken_out=total(s.outflow for s in steps),
            twr=twr(opening, steps, closing),
            xirr=xirr(flows),
        )


def report(histories: Sequence[History], start: date | None, end: date) -> Report:
    """Every holding's figures for the period, and the portfolio's."""
    days = flow_days(histories, start, end)
    first = start if start is not None else (days[0] if days else end)
    lines = [_timeline(h, start, days, end) for h in histories]
    holdings = tuple(
        HoldingFigures(
            key=h.key,
            native=_figures(h, line, start, end, base=False),
            base=_figures(h, line, start, end, base=True),
            closing=line.closing,
            at_cost=tuple(line.at_cost),
        )
        for h, line in zip(histories, lines, strict=True)
    )

    with localcontext(EXACT):
        steps = [
            Day(
                day,
                total(line.days[day][0].value_base for line in lines),
                total(line.days[day][1].value_base for line in lines),
                total(line.moved[day].paid_in_base for line in lines if day in line.moved),
                total(line.moved[day].taken_out_base for line in lines if day in line.moved),
            )
            for day in days
        ]
        opening = total(f.base.opening_value for f in holdings)
        closing = total(f.base.closing_value for f in holdings)
        flows = [Flow(start - _DAY, -opening)] if start is not None and opening else []
        flows += [Flow(s.on, s.outflow - s.inflow) for s in steps]
        flows.append(Flow(end, closing))
        portfolio = Figures(
            opening_value=opening,
            closing_value=closing,
            opening_cost=total(f.base.opening_cost for f in holdings),
            closing_cost=total(f.base.closing_cost for f in holdings),
            realised=total(f.base.realised for f in holdings),
            dividends=total(f.base.dividends for f in holdings),
            interest=total(f.base.interest for f in holdings),
            withholding_tax=total(f.base.withholding_tax for f in holdings),
            net_income=total(f.base.net_income for f in holdings),
            paid_in=total(s.inflow for s in steps),
            taken_out=total(s.outflow for s in steps),
            twr=twr(opening, steps, closing),
            xirr=xirr(flows),
        )
    return Report(start=first, end=end, holdings=holdings, portfolio=portfolio)
