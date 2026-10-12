"""
Scenario results and comparisons as JSON-ready data: what the API, the MCP
tools and the agents all serve. Pure.

Money is a decimal string with exactly the currency's decimals; a month of
spending covered and a rate are decimal strings too; never a float. Every
figure is `{"baseline", "scenario", "delta"}` (a month's delta is in months,
`delta_months`; a day's in days, `delta_days`).
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from salli.domain.baseline.models import RuleSetRef
from salli.domain.currency import quantize
from salli.domain.fi.assumptions import assumptions_dict, rate_text
from salli.domain.portfolio.lots import plain
from salli.domain.scenarios.comparison import Comparison, Delta, Sensitive
from salli.domain.scenarios.engine import (
    BreakEven,
    DayFigure,
    Figure,
    MonthFigure,
    ScenarioResult,
)
from salli.domain.scenarios.holdings import Trade
from salli.domain.scenarios.tax import YearTax

_HUNDREDTH = Decimal("0.01")


class _Writer:
    def __init__(self, currency: str) -> None:
        self.currency = currency

    def money(self, value: Decimal | None, currency: str | None = None) -> str | None:
        if value is None:
            return None
        return str(quantize(value, currency or self.currency, strict=False))

    @staticmethod
    def months(value: Decimal | None) -> str | None:
        return None if value is None else str(value.quantize(_HUNDREDTH, rounding=ROUND_HALF_UP))

    def figure(self, f: Figure, currency: str | None = None) -> dict[str, str | None]:
        return {
            "baseline": self.money(f.baseline, currency),
            "scenario": self.money(f.scenario, currency),
            "delta": self.money(f.delta, currency),
        }

    def months_figure(self, f: Figure) -> dict[str, str | None]:
        return {
            "baseline": self.months(f.baseline),
            "scenario": self.months(f.scenario),
            "delta": self.months(f.delta),
        }

    @staticmethod
    def month(f: MonthFigure) -> dict[str, Any]:
        return {"baseline": f.baseline, "scenario": f.scenario, "delta_months": f.delta}

    @staticmethod
    def day(f: DayFigure) -> dict[str, Any]:
        return {"baseline": f.baseline, "scenario": f.scenario, "delta_days": f.delta}


def money_text(value: Decimal | None, currency: str) -> str | None:
    """An amount as a decimal string to the currency's smallest unit."""
    return _Writer(currency).money(value)


def _percent(rate: Decimal) -> str:
    return f"{(rate * 100).normalize():f}%"


def break_even_view(b: BreakEven, result_currency: str, end: str | None = None) -> dict[str, Any]:
    """A break-even, with a sentence saying what it means."""
    w = _Writer(result_currency)
    amount = b.kind == "recurring_cash_floor"

    def value(v: Decimal | None) -> str | None:
        if v is None:
            return None
        return w.money(v) if amount else rate_text(v)

    if b.kind == "recurring_cash_floor":
        until = f" through {end}" if end else ""
        says = (
            f"Up to {w.money(b.value)} {result_currency} each time keeps cash at or above "
            f"zero{until}."
            if b.status == "found"
            else "Cash goes below zero in the next twelve months even without this cost."
        )
    elif b.kind == "invest_vs_debt_return":
        invest = b.option
        debt = next((o for o in b.options if o != invest), invest)
        if b.status == "found":
            assert b.value is not None
            says = (
                f"At a real return of {_percent(b.value)} a year or more, {invest} ends the "
                f"horizon with at least {debt}'s net worth; below it, {debt} ends with more."
            )
        else:
            behind = next((o for o in b.options if o != b.ahead), b.ahead)
            says = (
                f"{b.ahead} ends the horizon with more net worth than {behind} at every real "
                f"return from {_percent(b.low)} to {_percent(b.high)}."
            )
    elif b.kind == "asset_growth":
        others = [o for o in b.options if o != b.option]
        other = others[0] if others else b.option
        asset = f"the value of {b.option}'s asset"
        if b.status == "found" and b.value == b.low:
            says = (
                f"Only from a growth of {_percent(b.low)} a year beyond inflation in {asset} "
                f"does {b.option} end the horizon with at least {other}'s net worth."
            )
        elif b.status == "found":
            assert b.value is not None
            says = (
                f"At a growth of {_percent(b.value)} a year beyond inflation or more in "
                f"{asset}, {b.option} ends the horizon with at least {other}'s net worth; "
                f"below it, {other} ends with more."
            )
        else:
            behind = next((o for o in b.options if o != b.ahead), b.ahead)
            ends = "at least" if b.ahead == b.option else "more net worth than"
            whose = f"{behind}'s net worth" if b.ahead == b.option else behind
            says = (
                f"{b.ahead} ends the horizon with {ends} {whose} at every growth in {asset} "
                f"from {_percent(b.low)} to {_percent(b.high)} a year beyond inflation."
            )
    else:
        others = [o for o in b.options if o != b.option]
        other = others[0] if others else b.option
        if b.status == "found" and b.value == b.low:
            says = (
                f"Only at a loan rate of {_percent(b.low)} does {b.option} end the horizon with "
                f"at least {other}'s net worth; at any higher rate, {other} costs less."
            )
        elif b.status == "found":
            assert b.value is not None
            says = (
                f"At a loan rate of {_percent(b.value)} or less, {b.option} ends the horizon "
                f"with at least {other}'s net worth; above it, {other} costs less."
            )
        else:
            behind = next((o for o in b.options if o != b.ahead), b.ahead)
            says = (
                f"{b.ahead} ends the horizon with more net worth than {behind} at every loan "
                f"rate from {_percent(b.low)} to {_percent(b.high)}."
            )
    return {
        "kind": b.kind,
        "options": list(b.options),
        "option": b.option,
        "change": b.change,
        "status": b.status,
        "unit": "amount" if amount else "rate",
        "value": value(b.value),
        "low": value(b.low),
        "high": value(b.high),
        "ahead": b.ahead,
        "says": says,
    }


def rule_set_view(x: RuleSetRef) -> dict[str, Any]:
    return {
        "country": x.country,
        "region": x.region,
        "year": x.year,
        "rule_set_id": x.rule_set_id,
        "version": x.version,
        "content_hash": x.content_hash,
    }


def _year_view(y: YearTax, w: _Writer) -> dict[str, Any]:
    cur = y.currency

    def net(value: Decimal | None) -> str | None:
        return None if value is None or cur is None else w.money(value, cur)

    delta = (
        None
        if y.net_baseline is None or y.net_scenario is None
        else y.net_scenario - y.net_baseline
    )
    return {
        "year": y.label,
        "start": y.start.isoformat(),
        "end": y.end.isoformat(),
        "status": y.status,
        "reason": y.reason,
        "rules": None
        if y.rules is None
        else {**rule_set_view(y.rules), "carried_forward": y.carried_forward},
        "currency": cur,
        "roles": [
            {
                "key": t.key,
                "kind": t.kind,
                "label": t.label,
                "actual": net(t.actual),
                "projected": net(t.projected),
                "scenario": net(t.scenario),
            }
            for t in y.roles
        ],
        "net": {
            "baseline": net(y.net_baseline),
            "scenario": net(y.net_scenario),
            "delta": net(delta),
        },
        "change": w.money(y.change),
        "monthly": [{"month": month, "amount": w.money(part)} for month, part in y.parts],
    }


def trade_view(t: Trade, base: str) -> dict[str, Any]:
    """An invest into a holding, or a sale: the holding as the person named
    it, the units, the price and what it rests on, the fees, and a sale's
    lots and realised gain, in the holding's currency and the base one. No
    expected return: there is none per holding."""
    w = _Writer(base)

    def native(value: Decimal | None) -> str | None:
        return w.money(value, t.currency)

    return {
        "holding_id": t.holding_id,
        "symbol": t.symbol,
        "name": t.name,
        "currency": t.currency,
        "fx_rate": plain(t.fx_rate),
        "units": plain(t.units),
        "price": plain(t.price),
        "price_basis": {
            "date": t.price_date,
            "source": t.price_source,
            "price": plain(t.recorded_price),
            "grown": t.grown,
            "stale": t.stale,
        },
        "fees_given": t.fees_given,
        "fees": w.money(t.fees if t.fees is not None else Decimal(0)),
        "value": native(t.gross),
        "value_base": w.money(t.gross_base),
        "cost": native(t.cost),
        "cost_base": w.money(t.cost_base),
        "gain": native(t.gain),
        "gain_base": w.money(t.gain_base),
        "lots": [
            {
                "lot_id": lot.lot_id,
                "opened_on": lot.opened_on,
                "units": plain(lot.quantity),
                "cost": native(lot.cost),
                "cost_base": w.money(lot.cost_base),
            }
            for lot in t.lots
        ],
        "lot_id": t.lot_id,
        "account_id": t.account_id,
    }


def tax_view(r: ScenarioResult) -> dict[str, Any]:
    """A result's tax section: each tax year the scenario touches (the first
    two, and the years of the monthly checkpoints; the timeline uses all of
    them), the as-of date's year in brief, and the change over the horizon
    in today's money."""
    w = _Writer(r.currency)
    t = r.tax.outcome
    checkpoints = [dt.date.fromisoformat(c.date) for c in r.monthly]
    shown = [
        y
        for i, y in enumerate(t.years)
        if i < 2 or any(y.start <= day <= y.end for day in checkpoints)
    ]
    this_year = t.this_year
    return {
        "status": t.status,
        "reason": t.reason,
        "years": [_year_view(y, w) for y in shown],
        "this_year": None if this_year is None else _year_view(this_year, w),
        "change_this_year": w.money(t.change_this_year),
        "total_change": w.money(r.tax.total_change),
        "carried_forward": t.carried_forward,
    }


def result_view(r: ScenarioResult) -> dict[str, Any]:
    """A scenario's result as JSON-ready data."""
    w = _Writer(r.currency)
    cash = r.cash
    return {
        "schema": r.versions.schema,
        "label": r.label,
        "as_of": r.as_of.isoformat(),
        "horizon_years": r.horizon_years,
        "currency": r.currency,
        "hash": r.hash,
        "baseline_fingerprint": r.baseline_fingerprint,
        "scenario": r.scenario.model_dump(mode="json", by_alias=True, exclude_none=True),
        "changes": [
            {
                "index": c.index,
                "type": c.type,
                "label": c.label,
                "debt_id": c.debt_id,
                "payment": w.money(c.payment),
                "first_payment": c.first_payment,
                "monthly": w.money(c.monthly),
                "for_good": c.for_good,
                "stopped": [
                    {
                        "payee": s.payee,
                        "cadence": s.cadence,
                        "amount": w.money(s.amount, s.currency),
                        "currency": s.currency,
                    }
                    for s in c.stopped
                ],
                "holding": None if c.holding is None else trade_view(c.holding, r.currency),
            }
            for c in r.changes
        ],
        "cash": {
            "start": cash.start,
            "end": cash.end,
            "lowest": w.figure(cash.lowest),
            "lowest_date": w.day(cash.lowest_date),
            "at_end": w.figure(cash.at_end),
            "safe_to_spend": w.figure(cash.safe_to_spend),
            "safe_until": cash.safe_until,
            "accounts": [
                {
                    "account_id": a.account_id,
                    "name": a.name,
                    "currency": a.currency,
                    "lowest": w.figure(a.lowest, a.currency),
                    "lowest_date": w.day(a.lowest_date),
                    "below_zero": {"baseline": a.below_zero[0], "scenario": a.below_zero[1]},
                }
                for a in cash.accounts
            ],
            "below_zero": {
                "baseline": [a.account_id for a in cash.accounts if a.below_zero[0]],
                "scenario": [a.account_id for a in cash.accounts if a.below_zero[1]],
            },
        },
        "monthly": [
            {
                "years": c.years,
                "month": c.month,
                "date": c.date,
                "net_worth": w.figure(c.net_worth),
                "cash": w.figure(c.cash),
                "investments": w.figure(c.investments),
                "debts": w.figure(c.debts),
                "other_assets": w.figure(c.other_assets),
                "other_assets_value": w.figure(c.other_assets_value),
            }
            for c in r.monthly
        ],
        "debts": {
            "items": [
                {
                    "debt_id": d.debt_id,
                    "name": d.name,
                    "source": d.source,
                    "paid_off": w.month(d.paid_off),
                    "total_interest": w.figure(d.total_interest),
                }
                for d in r.debts.items
            ],
            "total_interest": w.figure(r.debts.total_interest),
            "debt_free": w.month(r.debts.debt_free),
        },
        "resilience": {
            "basis": r.resilience.basis,
            "monthly_spending": w.money(r.resilience.monthly_spending),
            "lowest": w.months_figure(r.resilience.lowest),
            "at_end": w.months_figure(r.resilience.at_end),
        },
        "fi": {
            "fi_number": w.figure(r.fi.fi_number),
            "monthly_spending": w.figure(r.fi.monthly_spending),
            "fi_month": w.month(r.fi.fi_month),
            "months_gained": r.fi.months_gained,
        },
        "break_evens": [break_even_view(b, r.currency, cash.end) for b in r.break_evens],
        "tax": tax_view(r),
        "assumptions": assumptions_dict(r.assumptions),
        "placeholders": list(r.placeholders),
        "versions": {
            "schema": r.versions.schema,
            "engine": r.versions.engine,
            "fi_assumptions": r.versions.fi_assumptions,
            "fire_strategy": r.versions.fire_strategy,
            "rule_sets": [rule_set_view(x) for x in r.versions.rule_sets],
        },
        "data_as_of": r.data_as_of,
        "is_stale": r.is_stale,
        "notes": list(r.notes),
    }


def _delta_view(d: Delta, w: _Writer) -> dict[str, Any]:
    if d.figure.endswith(("debt_free", "fi_month")):
        unit = "month"
        this, other, delta = d.this, d.other, d.delta
    elif d.figure.startswith("resilience."):
        unit = "months_of_spending"
        this = w.months(d.this) if isinstance(d.this, Decimal) else None
        other = w.months(d.other) if isinstance(d.other, Decimal) else None
        delta = w.months(d.delta) if isinstance(d.delta, Decimal) else None
    else:
        unit = "amount"
        this = w.money(d.this) if isinstance(d.this, Decimal) else None
        other = w.money(d.other) if isinstance(d.other, Decimal) else None
        delta = w.money(d.delta) if isinstance(d.delta, Decimal) else None
    return {"figure": d.figure, "unit": unit, "this": this, "other": other, "delta": delta}


def _sensitive_view(s: Sensitive, w: _Writer) -> dict[str, Any]:
    return {
        "net_worth": w.figure(s.net_worth),
        "investments": w.figure(s.investments),
        "fi_month": w.month(s.fi_month),
        "months_gained": s.months_gained,
    }


def comparison_view(c: Comparison) -> dict[str, Any]:
    """A comparison as JSON-ready data."""
    w = _Writer(c.currency)
    end = c.options[0].cash.end if c.options else None
    return {
        "as_of": c.as_of,
        "horizon_years": c.horizon_years,
        "currency": c.currency,
        "labels": list(c.labels),
        "options": [result_view(r) for r in c.options],
        "trade": [
            {
                "option": t.option,
                "against": t.against,
                "gains": [_delta_view(d, w) for d in t.gains],
                "gives_up": [_delta_view(d, w) for d in t.gives_up],
            }
            for t in c.trade
        ],
        "sensitivity": {
            "real_returns": {name: rate_text(rate) for name, rate in c.real_returns},
            "options": [
                {
                    "option": o.option,
                    **{name: _sensitive_view(s, w) for name, s in o.by_return},
                }
                for o in c.sensitivity
            ],
        },
        "break_evens": [break_even_view(b, c.currency, end) for b in c.break_evens],
    }
