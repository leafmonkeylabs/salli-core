"""The cash-flow forecast: balances carried forward through what keeps happening."""

from __future__ import annotations

import dataclasses
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
        anchor_days=(day,) if day else (),
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


# ── What review found ─────────────────────────────────────────────────────────


def test_a_late_charge_moves_alone_and_the_schedule_keeps_its_dates():
    # Moving the late one to today shifted the rest: the 5th became the 9th
    # every month, and November's charge fell out of a window ending the 6th.
    late = _recurring("Gym", "40", "2026-10-05", day=5)
    flows = recurring_flows([late], CASH, TODAY, dt.date(2026, 11, 6))
    assert [f.date for f in flows] == ["2026-10-09", "2026-11-05"]


def test_each_side_moves_in_its_own_accounts_currency():
    # A USD salary into a rupee account added 3,000 rupees, not 900,000; and
    # a transfer between cash accounts in two currencies lost its second leg.
    cash = {"lkr": "LKR", "usd": "USD"}
    salary = dataclasses.replace(
        _recurring("Acme Payroll", "3000", "2026-10-25", direction="in", money="lkr", day=25),
        currency="USD",
        money_amount=Decimal(900000),
    )
    transfer = dataclasses.replace(
        _recurring("To Dollars", "300000", "2026-10-26", money="lkr", to="usd", day=26),
        currency="LKR",
        money_amount=Decimal(300000),
        counter_amount=Decimal(1000),
    )
    flows = recurring_flows([salary, transfer], cash, TODAY, dt.date(2026, 10, 31))
    assert [(f.account_id, f.amount, f.currency) for f in flows] == [
        ("lkr", Decimal(900000), "LKR"),
        ("lkr", Decimal(-300000), "LKR"),
        ("usd", Decimal(1000), "USD"),
    ]


def test_a_side_whose_amount_cant_be_known_is_left_out_and_said():
    unknown = dataclasses.replace(
        _recurring("Acme Payroll", "3000", "2026-10-25", direction="in", money="lkr"),
        currency="USD",
    )
    notes: list[str] = []
    assert recurring_flows([unknown], {"lkr": "LKR"}, TODAY, END, notes) == []
    assert notes and "can't be known" in notes[0]


def test_an_accounts_low_point_is_where_it_ends_the_day():
    # Rent before salary on one day was a dip that never happens.
    flows = recurring_flows(
        [
            _recurring("Landlord", "1500", "2026-10-15", day=15),
            _recurring("Acme Payroll", "3000", "2026-10-15", direction="in", day=15),
        ],
        CASH,
        TODAY,
        dt.date(2026, 10, 20),
    )
    [checking] = _project(flows).accounts
    assert (checking.lowest, checking.lowest_date) == (Decimal(1000), "2026-10-09")


def test_cash_is_what_money_is_spent_from():
    # After onboarding (bank, EPF, house, housing loan) every account that
    # moved was "cash", opening balances included: the house and the EPF
    # fund were forecast as spending money.
    from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
    from salli.domain.reports.forecast import cash_accounts
    from salli.domain.rules.history import booked_transactions

    def account(id_, type_):
        return Account(id=id_, user_id="u", code=id_, name=id_, type=type_, currency="LKR")

    accounts = [
        account("bank", "asset"),
        account("epf", "asset"),
        account("house", "asset"),
        account("loan", "liability"),
        account("card", "liability"),
        account("equity", "equity"),
        account("salary", "income"),
        account("food", "expense"),
        account("fuel", "expense"),
        account("interest", "expense"),
    ]

    def entry(n, day, debit, credit, description="x"):
        legs = {"amount": Decimal(100), "currency": "LKR"}
        return StoredJournalEntry(
            id=f"e{n}",
            user_id="u",
            entry_date=day,
            description=description,
            source="manual",
            postings=[
                Posting(account_id=debit, direction=Direction.DEBIT, **legs),
                Posting(account_id=credit, direction=Direction.CREDIT, **legs),
            ],
        )

    entries = [
        entry(1, "2026-09-01", "bank", "equity", "Opening balance: Bank"),
        entry(2, "2026-09-01", "epf", "equity", "Opening balance: EPF"),
        entry(3, "2026-09-01", "house", "equity", "Opening balance: House"),
        entry(4, "2026-09-01", "equity", "loan", "Opening balance: Housing loan"),
        entry(5, "2026-09-25", "bank", "salary"),
        entry(6, "2026-09-25", "epf", "salary"),  # contributions: in, never out
        entry(7, "2026-09-28", "food", "bank"),
        entry(8, "2026-09-30", "interest", "loan"),  # the loan's interest
        entry(9, "2026-10-01", "loan", "bank"),  # a repayment
        entry(10, "2026-10-02", "food", "card"),
        entry(11, "2026-10-03", "fuel", "card"),
    ]
    booked = booked_transactions(entries, accounts)
    assert set(cash_accounts(booked, accounts, "2026-07-11")) == {"bank", "card"}
    # An account a statement is imported into is cash, whatever it did.
    assert "epf" in cash_accounts(booked, accounts, "2026-07-11", {"epf"})
