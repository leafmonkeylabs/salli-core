"""
InsightsService — the numbers a finance dashboard is built on, from the ledger
(domain/reports/insights.py): cash flow and savings rate by month, spending by
category, and the recurring payments the user may not be tracking as
subscriptions yet.

The cash forecast, safe-to-spend and the signals start from the baseline
(domain/baseline): the same cash accounts, the same rhythms and the same
exchange rates (the published ones for today) as every other figure. Cash
flow's averages are the baseline's income and expenses, under its one
definition, and net worth over time is the baseline's as of each month's
end.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import median
from typing import Any

from salli.application.services.baseline_service import BaselineService
from salli.domain.baseline import Baseline, timelines
from salli.domain.baseline import flows as baseline_flows
from salli.domain.baseline.models import MONTHS_OBSERVED
from salli.domain.currency import quantize
from salli.domain.fi.assumptions import rate_text
from salli.domain.fi.packs.registry import get_pack
from salli.domain.reports import forecast as forecasting
from salli.domain.reports import insights
from salli.domain.reports import signals as signal_rules
from salli.domain.rules.history import booked_transactions


def _ratio(value: Decimal | None) -> str | None:
    return None if value is None else str(value.quantize(Decimal("0.0001")))


def _money(value: Decimal, currency: str) -> str:
    return str(quantize(value, currency))


@dataclass(frozen=True)
class _Run:
    """A forecast and the baseline it was made from."""

    result: forecasting.Forecast
    baseline: Baseline
    notes: list[str]

    @property
    def base(self) -> str:
        return self.baseline.currency

    @property
    def names(self) -> dict[str, str]:
        return {b.account_id: b.name for b in self.baseline.balances}


class InsightsService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        today: Callable[[], dt.date] = dt.date.today,
        baselines: BaselineService | None = None,
    ):
        self._uow_factory = uow_factory
        self._today = today
        self._baselines = baselines or BaselineService(uow_factory, today=today)

    async def _ledger(
        self, user_id: str, from_date: str | None = None
    ) -> tuple[list[Any], list[Any], str]:
        """Every account (closed ones too), the entries from `from_date` on,
        and the base currency. Only a window's entries are read: a five-year
        ledger took over a second per call."""
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(user_id, from_date=from_date)
            base = await uow.user_profiles.base_currency(user_id)
        return accounts, entries, base

    async def cash_flow(self, user_id: str, months: int = 12) -> dict[str, Any]:
        """Income, expenses, what was left and the savings rate for each of the
        `months` full calendar months before this one, and for this month so
        far (marked incomplete). `average` is the baseline's monthly figures:
        over the full months observed (from the first month with income or
        expenses), at most twelve, the same months marked `observed`."""
        today = self._today()
        window = insights.last_months(today, months + 1)
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(
                user_id, from_date=f"{window[0]}-01", to_date=today.isoformat()
            )
            base = await uow.user_profiles.base_currency(user_id)
            first_flow = await uow.ledger.first_flow_date(user_id, to_date=today.isoformat())
        rows = insights.cash_flow(entries, accounts, window)
        average = baseline_flows.summarize(
            entries, accounts, today, first_flow, cap=min(months, MONTHS_OBSERVED)
        )
        observed = set(average.months)
        current = window[-1]
        return {
            "currency": base,
            "months": [
                {
                    "month": f.month,
                    "income": _money(f.income, base),
                    "expenses": _money(f.expenses, base),
                    "net": _money(f.net, base),
                    "savings_rate": _ratio(f.savings_rate),
                    "complete": f.month != current,
                    "observed": f.month in observed,
                }
                for f in rows
            ],
            "average": {
                "months_observed": list(average.months),
                "income": _money(average.income, base),
                "expenses": _money(average.expenses, base),
                "net": _money(average.surplus, base),
                "savings_rate": _ratio(average.savings_rate),
            },
        }

    async def spending(
        self, user_id: str, months: int = 3, by: insights.SpendingAxis = "category"
    ) -> dict[str, Any]:
        window = insights.last_months(self._today(), months)
        accounts, entries, base = await self._ledger(user_id, f"{window[0]}-01")
        lines = insights.spending(entries, accounts, window, by)
        return {
            "currency": base,
            "by": by,
            "months": window,
            "lines": [
                {
                    "key": line.key,
                    "total": _money(line.total, base),
                    "share": _ratio(line.share),
                    "by_month": {m: _money(v, base) for m, v in line.by_month.items()},
                }
                for line in lines
            ],
        }

    async def net_worth(self, user_id: str, months: int = 24) -> dict[str, Any]:
        """The baseline's net worth at each month's end, and this month's as
        of today (`BaselineService.worth`): each account at the published
        rate for that day, the debts the ledger doesn't hold at their
        declared principal. A point's `notes` say what it left out (an
        account in a currency with no rate for the day)."""
        today = self._today()
        window = insights.last_months(today, months)
        days = [*(_month_end(m) for m in window[:-1]), today]
        points = await self._baselines.worth(user_id, days)
        base = points[-1].currency
        return {
            "currency": base,
            "points": [
                {
                    "month": month,
                    "assets": _money(p.total_assets, base),
                    "liabilities": _money(p.total_liabilities, base),
                    "net_worth": _money(p.net_worth, base),
                    "notes": list(p.notes),
                }
                for month, p in zip(window, points, strict=True)
            ],
        }

    async def recurring(self, user_id: str) -> dict[str, Any]:
        """Recurring payments found in the ledger's last two years (enough for
        a yearly rhythm and its slack), each with the declared subscription
        that already covers it, if any (`forecast.coverage`)."""
        since = (self._today() - dt.timedelta(days=_RECURRING_DAYS)).isoformat()
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(user_id, from_date=since)
            base = await uow.user_profiles.base_currency(user_id)
            subscriptions = await uow.recurring_subscriptions.list(user_id, active_only=True)
        found = insights.detect_recurring(booked_transactions(entries, accounts), self._today())
        covered_by = forecasting.coverage(subscriptions, entries, accounts, base)

        items: list[dict[str, Any]] = []
        for r in found:
            subscription_id = covered_by(r)
            items.append(
                {
                    "payee": r.payee,
                    "key": r.key,
                    "cadence": r.cadence,
                    "typical_amount": str(quantize(r.typical_amount, r.currency, strict=False)),
                    "varies": r.varies,
                    "currency": r.currency,
                    "account_id": r.account_id,
                    "occurrences": r.occurrences,
                    "last_date": r.last_date,
                    "next_expected": r.next_expected,
                    "examples": list(r.examples),
                    "tracked": subscription_id is not None,
                    "subscription_id": subscription_id,
                }
            )
        return {"items": items}

    async def _project(
        self,
        user_id: str,
        days: int,
        changes: Sequence[forecasting.Flow] = (),
        today: dt.date | None = None,
    ) -> _Run:
        """The cash forecast and the baseline it rests on, for the forecast,
        safe-to-spend and the signals alike (as of `today`, the clock's day
        unless given)."""
        today = today or self._today()
        baseline = await self._baselines.build(user_id, today)
        result, notes = timelines.forecast(baseline, today + dt.timedelta(days=days), changes)
        return _Run(result, baseline, [*baseline.cash_notes, *notes])

    async def forecast(
        self, user_id: str, days: int = 60, changes: Sequence[forecasting.Flow] = ()
    ) -> dict[str, Any]:
        """Each cash account's balance from today to `days` ahead, and the
        total's, from what keeps happening in the ledger and the declared
        subscriptions it has not shown (domain/reports/forecast.py), plus any
        `changes` (a scenario's flows).

        Cash accounts are the baseline's: asset accounts whose role is cash,
        and the cards money is spent from. Each is valued in its own currency,
        from what the database sums of its postings (exact, and no history
        loaded); an account whose balance in its currency can't be known is
        left out and said in `notes`, never shown at a wrong balance. The
        total is in the base currency at the published rate for today
        (`fx`), as every baseline figure is."""
        run = await self._project(user_id, days, changes)
        result, base = run.result, run.base
        names = run.names

        def money(value: Decimal, currency: str) -> str:
            return str(quantize(value, currency, strict=False))

        return {
            "currency": base,
            "start": result.start,
            "end": result.end,
            "today": money(result.today, base),
            "end_balance": money(result.end_balance, base),
            "lowest": money(result.lowest, base),
            "lowest_date": result.lowest_date,
            "daily": [{"date": d, "balance": money(v, base)} for d, v in result.daily],
            "accounts": [
                {
                    "account_id": a.account_id,
                    "name": names[a.account_id],
                    "currency": a.currency,
                    "today": money(a.today, a.currency),
                    "end": money(a.end, a.currency),
                    "lowest": money(a.lowest, a.currency),
                    "lowest_date": a.lowest_date,
                }
                for a in result.accounts
            ],
            "flows": [
                {
                    "date": f.date,
                    "account_id": f.account_id,
                    "amount": money(f.amount, f.currency),
                    "currency": f.currency,
                    "description": f.description,
                    "source": f.source,
                }
                for f in result.flows
            ],
            "fx": _rates(run.baseline),
            "notes": list(dict.fromkeys(run.notes)),
        }

    async def safe_to_spend(
        self, user_id: str, changes: Sequence[forecasting.Flow] = ()
    ) -> dict[str, Any]:
        """Free to spend until payday (`timelines.safe_to_spend`, which
        scenarios read too): the lowest the cash gets before money next comes
        in, after what is scheduled and a usual day's everyday spending, less
        a cushion and the cash set aside for goals; never below zero. Money
        moved between two cash accounts (paying the card from checking) is
        neither income nor committed: it never leaves cash."""
        baseline = await self._baselines.build(user_id, self._today())
        safe = timelines.safe_to_spend(baseline, changes)
        income, before, until = safe.next_income, safe.committed, safe.until
        base = baseline.currency
        notes = [*baseline.cash_notes, *safe.notes]

        def money(value: Decimal, currency: str = base) -> str:
            return str(quantize(value, currency, strict=False))

        return {
            "currency": base,
            "amount": money(safe.amount),
            "cash_today": money(safe.cash_today),
            "low_point": money(safe.low_point),
            "low_point_date": safe.low_point_date,
            "everyday_spending": money(safe.everyday),
            "cushion": money(safe.cushion),
            "held_for_goals": money(safe.held_for_goals),
            "until": until,
            "next_income": None
            if income is None
            else {
                "date": income.date,
                "description": income.description,
                "amount": money(income.amount, income.currency),
                "currency": income.currency,
            },
            "committed": [
                {
                    "date": f.date,
                    "description": f.description,
                    "amount": money(f.amount, f.currency),
                    "currency": f.currency,
                }
                for f in before
            ],
            "fx": _rates(baseline),
            "notes": list(dict.fromkeys(notes)),
        }

    async def signals(self, user_id: str) -> dict[str, Any]:
        """What needs the user's attention now (domain/reports/signals.py),
        most pressing first."""
        today = self._today()
        run = await self._project(user_id, 60)
        base = run.base
        months = insights.last_months(today, 5)[:-1]  # full months only
        accounts, entries, _ = await self._ledger(user_id, f"{months[0]}-01")
        flows = insights.cash_flow(entries, accounts, months)
        lines = insights.spending(entries, accounts, months)
        spent = [f.expenses for f in flows if f.expenses > 0]
        usual_spending = median(spent) if spent else None
        found = list(run.baseline.recurring)
        tracked = {
            r.entry_ids[0]: covered is not None
            for r, covered in zip(found, run.baseline.covered_by, strict=True)
            if r.entry_ids
        }
        pending = await self._pending(user_id)
        oldest = min((t.raw.date for t in pending), default=None)
        async with self._uow_factory() as uow:
            due = await uow.decisions.due(user_id, today)
        detected = [
            *signal_rules.low_balance_ahead(
                run.result.lowest, run.result.lowest_date, run.result.today, usual_spending, base
            ),
            *signal_rules.price_changes(found),
            *signal_rules.new_recurring(found, tracked, today),
            *signal_rules.spending_spikes(
                lines, months, base, floor=(usual_spending or Decimal(0)) / 20
            ),
            *signal_rules.savings_rate_drop(flows),
            *signal_rules.review_waiting(len(pending), oldest, today),
            *signal_rules.emergency_fund_low(
                run.baseline.liquid,
                run.baseline.flows.expenses,
                get_pack().emergency_fund_target_months,
                len(run.baseline.flows.months),
                base,
            ),
            *signal_rules.expensive_debts(
                [
                    (d.debt_id, d.name, d.apr, d.balance)
                    for d in run.baseline.debts
                    if d.source != "scenario"
                ],
                base,
            ),
            *signal_rules.decision_reviews_due(
                [(str(d["id"]), str(d["question"]), _iso(d["review_on"])) for d in due]
            ),
        ]

        def money(value: Decimal | None, currency: str | None) -> str | None:
            if value is None or currency is None:
                return None
            return str(quantize(value, currency, strict=False))

        return {
            "signals": [
                {
                    "kind": sig.kind,
                    "severity": sig.severity,
                    "title": sig.title,
                    "detail": sig.detail,
                    "action": sig.action,
                    "amount": money(sig.amount, sig.currency),
                    "currency": sig.currency,
                    "date": sig.date,
                    "refs": list(sig.refs),
                    "rationale": sig.rationale,
                }
                for sig in signal_rules.ranked(detected)
            ]
        }

    async def cash_below_zero_on(self, user_id: str, today: dt.date) -> dt.date | None:
        """The first day the cash forecast goes below zero, when the
        `low_balance_ahead` signal says it does (at `high`), over the signals'
        60 days from `today` (a person's own local date, for their digest)."""
        run = await self._project(user_id, 60, today=today)
        result = run.result
        signals = signal_rules.low_balance_ahead(
            result.lowest, result.lowest_date, result.today, None, run.base
        )
        if not any(s.severity == "high" for s in signals):
            return None
        first = next((d for d, balance in result.daily if balance < 0), result.lowest_date)
        return dt.date.fromisoformat(first)

    async def transactions_waiting(self, user_id: str) -> tuple[int, dt.date | None]:
        """How many imported transactions wait for review, and the oldest one's
        date (the `review_waiting` signal's figures)."""
        pending = await self._pending(user_id)
        oldest = min((t.raw.date for t in pending), default=None)
        return len(pending), None if oldest is None else dt.date.fromisoformat(oldest)

    async def _pending(self, user_id: str) -> list[Any]:
        async with self._uow_factory() as uow:
            return await uow.statements.get_all_pending(user_id)


def _month_end(month: str) -> dt.date:
    year, number = int(month[:4]), int(month[5:7])
    return dt.date(year, number, calendar.monthrange(year, number)[1])


def _iso(value: object) -> str:
    return value.isoformat() if isinstance(value, dt.date) else str(value)


def _rates(baseline: Baseline) -> list[dict[str, str | None]]:
    """The published rates the cash total is in the base currency at."""
    return [
        {
            "currency": r.currency,
            "rate": None if r.rate is None else rate_text(r.rate),
            "source": r.source,
            "as_of": r.as_of,
        }
        for r in baseline.rates
        if any(b.in_cash and b.currency == r.currency for b in baseline.balances)
    ]


# Two years: a yearly payment's last three charges, and their slack.
_RECURRING_DAYS = 2 * 366 + 30
