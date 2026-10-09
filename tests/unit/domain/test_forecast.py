"""The cash-flow forecast: balances carried forward through what keeps happening."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from salli.domain.reports.forecast import (
    DeclaredCharge,
    declared_flows,
    project,
    recurring_flows,
)
from salli.domain.reports.insights import Recurring

TODAY = dt.date(2026, 10, 9)
END = dt.date(2026, 11, 30)
CASH = {"checking": "USD", "card": "USD", "euro": "EUR"}


def _recurring(
    payee, amount, next_expected, *, direction="out", money="checking", to="x", day=None
):
    return Recurring(
        payee=payee,
        key=payee.lower(),
        cadence="monthly",
        typical_amount=Decimal(amount),
        varies=False,
        currency=CASH.get(money, "USD"),
        account_id=to,
        occurrences=3,
        last_date="2026-09-01",
        next_expected=next_expected,
        direction=direction,
        money_account_id=money,
        anchor_day=day,
    )


def _project(flows, balances=None, rates=None):
    balances = balances or {"checking": ("USD", Decimal(1000))}
    return project(balances, flows, rates or {}, "USD", TODAY, END)


def test_salary_and_rent_carry_the_balance_forward_and_find_the_low_point():
    flows = recurring_flows(
        [
            _recurring("Acme Payroll", "3000", "2026-10-25", direction="in", day=25),
            _recurring("Landlord", "1500", "2026-10-15", day=15),
        ],
        CASH,
        TODAY,
        END,
    )
    assert [(f.date, f.amount) for f in flows] == [
        ("2026-10-25", Decimal(3000)),
        ("2026-11-25", Decimal(3000)),
        ("2026-10-15", Decimal(-1500)),
        ("2026-11-15", Decimal(-1500)),
    ]
    result = _project(flows)
    assert (result.today, result.end_balance) == (Decimal(1000), Decimal(4000))
    assert (result.lowest, result.lowest_date) == (Decimal(-500), "2026-10-15")
    assert dict(result.daily)["2026-10-24"] == Decimal(-500)
    [checking] = result.accounts
    assert (checking.lowest, checking.lowest_date) == (Decimal(-500), "2026-10-15")


def test_a_transfer_between_cash_accounts_moves_both_and_not_the_total():
    pay_card = _recurring("Card Payment", "400", "2026-10-20", to="card")
    flows = recurring_flows([pay_card], CASH, TODAY, END)
    result = _project(
        flows, balances={"checking": ("USD", Decimal(1000)), "card": ("USD", Decimal(-400))}
    )
    by_account = {a.account_id: a for a in result.accounts}
    assert by_account["checking"].end == Decimal(200)
    assert by_account["card"].end == Decimal(400)  # paid off, then paid again
    assert result.end_balance == result.today == Decimal(600)


def test_a_charge_a_little_late_is_expected_today_not_skipped():
    late = _recurring("Gym", "40", "2026-10-05", day=5)
    [first, *_] = recurring_flows([late], CASH, TODAY, END)
    assert (first.date, first.amount) == ("2026-10-09", Decimal(-40))


def test_what_happens_on_a_non_cash_account_is_left_out():
    elsewhere = _recurring("Broker Fee", "10", "2026-10-20", money="brokerage")
    assert recurring_flows([elsewhere], CASH, TODAY, END) == []


def test_a_declared_subscription_moves_only_the_total_from_its_next_due_date():
    charges = [DeclaredCharge("Streaming", Decimal("15.99"), "monthly", dt.date(2026, 9, 30))]
    flows = declared_flows(charges, "USD", TODAY, END)
    # Its due date passed without the user updating it: it rolls forward.
    assert [(f.date, f.account_id) for f in flows] == [
        ("2026-10-30", None),
        ("2026-11-30", None),
    ]
    result = _project(flows)
    assert result.end_balance == Decimal("968.02")
    assert result.accounts[0].end == Decimal(1000)  # no account says who pays it


def test_foreign_accounts_count_at_their_rate_or_only_in_their_own_outlook():
    balances = {"checking": ("USD", Decimal(1000)), "euro": ("EUR", Decimal(100))}
    with_rate = _project([], balances, rates={"EUR": Decimal("1.10")})
    assert with_rate.today == Decimal("1110.00")
    without = _project([], balances)
    assert without.today == Decimal(1000)
    assert {a.account_id: a.end for a in without.accounts}["euro"] == Decimal(100)


def test_a_bill_on_the_31st_stays_on_the_last_day_of_short_months():
    rent = _recurring("Landlord", "1000", "2026-10-31", day=31)
    flows = recurring_flows([rent], CASH, TODAY, dt.date(2027, 1, 31))
    assert [f.date for f in flows] == ["2026-10-31", "2026-11-30", "2026-12-31", "2027-01-31"]
