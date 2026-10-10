"""Signals: what stands out, with its evidence, and nothing advised."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from salli.domain.reports.insights import MonthFlow, Recurring, SpendingLine
from salli.domain.reports.signals import (
    low_balance_ahead,
    new_recurring,
    price_changes,
    ranked,
    review_waiting,
    savings_rate_drop,
    spending_spikes,
)

TODAY = dt.date(2026, 10, 9)


def _recurring(**kw) -> Recurring:
    defaults = dict(
        payee="Netflix",
        key="netflix",
        cadence="monthly",
        typical_amount=Decimal("15.99"),
        varies=False,
        currency="USD",
        account_id="tv",
        occurrences=4,
        last_date="2026-10-01",
        next_expected="2026-11-01",
        entry_ids=("e1", "e2", "e3", "e4"),
        first_date="2026-07-01",
    )
    return Recurring(**(defaults | kw))


def test_cash_below_zero_is_high_and_thin_cash_is_medium():
    [high] = low_balance_ahead(Decimal("-120"), "2026-10-28", Decimal(900), Decimal(2000), "USD")
    assert (high.severity, high.date, high.amount) == ("high", "2026-10-28", Decimal("-120"))
    [thin] = low_balance_ahead(Decimal("150"), "2026-10-28", Decimal(900), Decimal(2000), "USD")
    assert thin.severity == "medium"
    assert low_balance_ahead(Decimal("800"), "2026-10-28", Decimal(900), Decimal(2000), "USD") == []


def test_a_subscription_that_got_dearer_says_by_how_much():
    dearer = _recurring(previous_amount=Decimal("15.99"), latest_amount=Decimal("17.99"))
    [sig] = price_changes([dearer, _recurring()])
    assert (sig.kind, sig.severity, sig.amount) == ("price_change", "medium", Decimal("17.99"))
    assert "+13%" in sig.detail and sig.refs == ("e4",)


def test_a_new_untracked_recurring_charge_is_pointed_out_once_tracked_it_is_not():
    fresh = _recurring(payee="Gym", entry_ids=("g1", "g2", "g3"), first_date="2026-08-01")
    old = _recurring(first_date="2025-01-01")
    [sig] = new_recurring([fresh, old], {}, TODAY)
    assert sig.title == "New recurring payment: Gym"
    assert new_recurring([fresh], {"g1": True}, TODAY) == []


def test_a_category_half_again_above_usual_is_a_spike():
    months = ["2026-06", "2026-07", "2026-08", "2026-09"]
    food = SpendingLine(
        key="groceries",
        total=Decimal(1400),
        by_month=dict(zip(months, map(Decimal, ["300", "320", "310", "470"]), strict=True)),
        share=Decimal("0.5"),
    )
    steady = SpendingLine(
        key="rent",
        total=Decimal(4000),
        by_month=dict.fromkeys(months, Decimal(1000)),
        share=Decimal("0.5"),
    )
    [sig] = spending_spikes([food, steady], months, "USD")
    assert (sig.title, sig.amount, sig.date) == (
        "groceries was well above usual",
        Decimal("470"),
        "2026-09",
    )


def test_a_savings_rate_that_fell_is_named():
    flows = [
        MonthFlow(m, Decimal(1000), Decimal(1000) - Decimal(1000) * r, Decimal(1000) * r, r)
        for m, r in zip(
            ["2026-06", "2026-07", "2026-08", "2026-09"],
            map(Decimal, ["0.40", "0.35", "0.38", "0.10"]),
            strict=True,
        )
    ]
    [sig] = savings_rate_drop(flows)
    assert sig.kind == "savings_rate_drop" and "10%" in sig.detail and "38%" in sig.detail


def test_review_waiting_grows_more_pressing_with_age_and_ranking_puts_high_first():
    [fresh] = review_waiting(3, "2026-10-07", TODAY)
    [stale] = review_waiting(3, "2026-09-20", TODAY)
    assert (fresh.severity, stale.severity) == ("info", "medium")
    assert review_waiting(0, None, TODAY) == []
    [high] = low_balance_ahead(Decimal("-1"), "2026-11-01", Decimal(5), None, "USD")
    assert [s.severity for s in ranked([fresh, stale, high])] == ["high", "medium", "info"]
