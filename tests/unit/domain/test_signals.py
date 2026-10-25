"""Signals: what stands out, with its evidence, and nothing advised."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from salli.domain.reports.insights import MonthFlow, Recurring, SpendingLine
from salli.domain.reports.signals import (
    EXPENSIVE_DEBT_RATE,
    decision_reviews_due,
    emergency_fund_low,
    expensive_debts,
    low_balance_ahead,
    new_recurring,
    price_changes,
    ranked,
    review_waiting,
    savings_rate_drop,
    spending_spikes,
)
from tests.guardrails import assert_never_urges

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


def test_a_decision_due_for_review_is_an_invitation_not_an_alarm():
    [signal] = decision_reviews_due([("d-1", "Laptop:\n cash or not?", "2027-04-11")])
    assert (signal.kind, signal.severity, signal.action, signal.refs, signal.date) == (
        "decision_review_due",
        "info",
        "review_decision",
        ("d-1",),
        "2027-04-11",
    )
    assert '"Laptop: cash or not?"' in signal.detail


def test_cash_covering_fewer_months_than_the_target_is_described_once_a_month_is_seen():
    low = emergency_fund_low(Decimal(500), Decimal(1000), 6, 1, "USD")
    assert [s.kind for s in low] == ["emergency_fund_low"]
    assert "0.5 months" in low[0].detail and low[0].action == "see_cash_flow"
    assert_never_urges([s.title for s in low] + [s.detail for s in low])
    assert emergency_fund_low(Decimal(500), Decimal(1000), 6, 0, "USD") == []
    assert emergency_fund_low(Decimal(6000), Decimal(1000), 6, 3, "USD") == []


def test_a_debt_at_or_above_the_methods_line_is_described_with_its_source():
    found = expensive_debts(
        [
            ("d1", "Card", Decimal("0.24"), Decimal(2000)),
            ("d2", "Car loan", EXPENSIVE_DEBT_RATE - Decimal("0.01"), Decimal(9000)),
            ("d3", "Old card", Decimal("0.30"), Decimal(0)),
        ],
        "USD",
    )
    assert [(s.kind, s.refs, s.action) for s in found] == [("expensive_debt", ("d1",), "see_debts")]
    assert "placeholder" in found[0].detail and "not any country's figure" in found[0].detail
    assert_never_urges([found[0].title, found[0].detail])
