"""
InsightsService — the numbers a finance dashboard is built on, from the ledger
(domain/reports/insights.py): cash flow and savings rate by month, spending by
category, net worth over time, and the recurring payments the user may not be
tracking as subscriptions yet.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.domain.accounting.ledger import native_signed
from salli.domain.currency import quantize
from salli.domain.money import from_minor
from salli.domain.reports import forecast as forecasting
from salli.domain.reports import insights
from salli.domain.rules.engine import payee_word
from salli.domain.rules.history import booked_transactions
from salli.domain.subscription.engine import find_matches
from salli.domain.subscription.models import Subscription


def _ratio(value: Decimal | None) -> str | None:
    return None if value is None else str(value.quantize(Decimal("0.0001")))


def _money(value: Decimal, currency: str) -> str:
    return str(quantize(value, currency))


class InsightsService:
    def __init__(
        self, uow_factory: Callable[[], Any], today: Callable[[], dt.date] = dt.date.today
    ):
        self._uow_factory = uow_factory
        self._today = today

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
        window = insights.last_months(self._today(), months)
        accounts, entries, base = await self._ledger(user_id, f"{window[0]}-01")
        flows = insights.cash_flow(entries, accounts, window)
        return {
            "currency": base,
            "months": [
                {
                    "month": f.month,
                    "income": _money(f.income, base),
                    "expenses": _money(f.expenses, base),
                    "net": _money(f.net, base),
                    "savings_rate": _ratio(f.savings_rate),
                }
                for f in flows
            ],
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
        """Book value at each month's end. What came before the window is
        summed by the database (each account's balance at its start), and
        only the window's entries are read."""
        window = insights.last_months(self._today(), months)
        start = f"{window[0]}-01"
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            opening = await uow.ledger.balances_before(user_id, start)
            entries = await uow.ledger.get_entries(user_id, from_date=start)
            base = await uow.user_profiles.base_currency(user_id)
        points = insights.net_worth_series(entries, accounts, window, opening)
        return {
            "currency": base,
            "points": [
                {
                    "month": p.month,
                    "assets": _money(p.assets, base),
                    "liabilities": _money(p.liabilities, base),
                    "net_worth": _money(p.net_worth, base),
                }
                for p in points
            ],
        }

    async def _snapshot(
        self, user_id: str, since: str | None = None
    ) -> tuple[list[Any], list[Any], str, list[Any]]:
        async with self._uow_factory() as uow:
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(user_id, from_date=since)
            base = await uow.user_profiles.base_currency(user_id)
            subscriptions = await uow.recurring_subscriptions.list(user_id, active_only=True)
        return accounts, entries, base, subscriptions

    async def recurring(self, user_id: str) -> dict[str, Any]:
        """Recurring payments found in the ledger's last two years (enough for
        a yearly rhythm and its slack), each with the declared subscription
        that already covers it, if any (`_coverage`)."""
        since = (self._today() - dt.timedelta(days=_RECURRING_DAYS)).isoformat()
        accounts, entries, base, subscriptions = await self._snapshot(user_id, since)
        found = insights.detect_recurring(booked_transactions(entries, accounts), self._today())
        covered_by = _coverage(subscriptions, entries, accounts, base)

        items: list[dict[str, Any]] = []
        for r in found:
            subscription_id = covered_by(r)
            items.append(
                {
                    "payee": r.payee,
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

    async def forecast(self, user_id: str, days: int = 60) -> dict[str, Any]:
        """Each cash account's balance from today to `days` ahead, and the
        total's, from what keeps happening in the ledger and the declared
        subscriptions it has not shown (domain/reports/forecast.py).

        Cash accounts are those that moved money in the last 90 days: the
        bank and cash accounts and cards transactions went through. Each is
        valued in its own currency; the total, in the base currency, at the
        rate of the latest posting in that currency (no rate is fetched)."""
        accounts, entries, base, subscriptions = await self._snapshot(user_id)
        today = self._today()
        end = today + dt.timedelta(days=days)
        by_id = {a.id: a for a in accounts}
        booked = booked_transactions(entries, accounts)

        recent = (today - dt.timedelta(days=90)).isoformat()
        cash = {
            b.money_account_id: by_id[b.money_account_id].currency
            for b in booked
            if b.entry.entry_date >= recent and b.money_account_id in by_id
        }
        balances = {account_id: (currency, Decimal(0)) for account_id, currency in cash.items()}
        latest_rate: dict[str, tuple[str, Decimal]] = {}  # currency -> (date, base per unit)
        for entry in entries:
            for p in entry.postings:
                if p.currency != base:
                    seen = latest_rate.get(p.currency)
                    if seen is None or entry.entry_date >= seen[0]:
                        latest_rate[p.currency] = (entry.entry_date, p.fx_rate)
                if p.account_id in balances:
                    signed = native_signed(p, cash[p.account_id], base)
                    if signed is not None:
                        currency, amount = balances[p.account_id]
                        balances[p.account_id] = (currency, amount + signed)

        found = insights.detect_recurring(booked, today, direction=None)
        covered_by = _coverage(subscriptions, entries, accounts, base)
        covered = {covered_by(r) for r in found} - {None}
        charges = [
            forecasting.DeclaredCharge(
                name=s["name"],
                amount=from_minor(s["amount_minor"], base),
                cadence=s["frequency"],
                next_due=dt.date.fromisoformat(s["next_due_date"]),
            )
            for s in subscriptions
            if s["id"] not in covered
        ]
        flows = [
            *forecasting.recurring_flows(found, cash, today, end),
            *forecasting.declared_flows(charges, base, today, end),
        ]
        result = forecasting.project(
            balances, flows, {c: rate for c, (_, rate) in latest_rate.items()}, base, today, end
        )

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
                    "name": by_id[a.account_id].name,
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
        }


# Two years: a yearly payment's last three charges, and their slack.
_RECURRING_DAYS = 2 * 366 + 30


def _coverage(
    subscriptions: list[Any], entries: list[Any], accounts: list[Any], base: str
) -> Callable[[insights.Recurring], str | None]:
    """Which declared subscription covers a recurring payment, if any.

    One covers a series only when the subscription engine's own matching
    (domain/subscription) takes most of the series' charges as its, the
    amounts agree within its tolerance or it is named after the payee, and
    its frequency is the series' rhythm. Matching alone was too loose: a
    subscription tied to an expense account matches every charge there, and
    an untied one any expense within 5%, so Netflix read as Disney+. The
    accounts matched against are the subscription report's (active ones)."""
    active = [a for a in accounts if a.is_active]
    declared: list[tuple[str, Subscription, set[str]]] = []
    for row in subscriptions:
        try:
            subscription = Subscription.from_row(row, base)
        except ValueError:
            continue  # a malformed row covers nothing
        matched = {m.entry_id for m in find_matches(subscription, entries, active)}
        declared.append((row["id"], subscription, matched))

    def covered_by(r: insights.Recurring) -> str | None:
        if r.direction != "out":
            return None  # income is no subscription
        for subscription_id, subscription, matched in declared:
            agreeing = sum(1 for e in r.entry_ids if e in matched)
            if agreeing * 2 <= len(r.entry_ids):
                continue
            tolerance = subscription.amount * subscription.amount_tolerance_pct
            same_amount = abs(r.typical_amount - subscription.amount) <= tolerance
            same_name = (payee_word(subscription.name) or subscription.name.casefold()) == r.key
            if (same_amount or same_name) and subscription.frequency == r.cadence:
                return subscription_id
        return None

    return covered_by
