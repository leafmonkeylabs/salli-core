"""Insights from the ledger: cash flow, spending, net worth, recurring payments."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.reports.insights import (
    cash_flow,
    detect_recurring,
    last_months,
    net_worth_series,
    spending,
)
from salli.domain.rules.history import booked_transactions

ACCOUNTS = [
    Account(id="bank", user_id="u", code="1000", name="Checking", type="asset", currency="USD"),
    Account(id="eur", user_id="u", code="1100", name="Euro cash", type="asset", currency="EUR"),
    Account(id="card", user_id="u", code="2000", name="Card", type="liability", currency="USD"),
    Account(id="salary", user_id="u", code="4000", name="Salary", type="income", currency="USD"),
    Account(id="food", user_id="u", code="5000", name="Food", type="expense", currency="USD"),
    Account(id="fun", user_id="u", code="5100", name="Fun", type="expense", currency="USD"),
    Account(id="open", user_id="u", code="3000", name="Opening", type="equity", currency="USD"),
]

_n = 0


def _entry(
    day: str,
    debit: str,
    credit: str,
    amount: str,
    description: str = "x",
    *,
    currency: str = "USD",
    fx_rate: str = "1",
    tags: dict[str, str] | None = None,
    reversed_by: str | None = None,
) -> StoredJournalEntry:
    global _n
    _n += 1
    leg = {"amount": Decimal(amount), "currency": currency, "fx_rate": Decimal(fx_rate)}
    return StoredJournalEntry(
        id=f"e{_n}",
        user_id="u",
        entry_date=day,
        description=description,
        source="manual",
        reversed_by=reversed_by,
        postings=[
            Posting(account_id=debit, direction=Direction.DEBIT, tags=tags or {}, **leg),
            Posting(account_id=credit, direction=Direction.CREDIT, **leg),
        ],
    )


def test_months_count_back_across_a_year_end():
    assert last_months(dt.date(2026, 2, 14), 4) == ["2025-11", "2025-12", "2026-01", "2026-02"]


# ── cash flow ─────────────────────────────────────────────────────────────────


def test_cash_flow_counts_income_and_spending_by_month_with_the_savings_rate():
    entries = [
        _entry("2026-08-01", "bank", "salary", "4000"),
        _entry("2026-08-03", "food", "bank", "1000"),
        _entry("2026-09-01", "bank", "salary", "4000"),
        _entry("2026-09-05", "fun", "card", "3000"),
        _entry("2026-09-20", "card", "bank", "3000"),  # paying the card is not spending
    ]
    aug, sep, oct_ = cash_flow(entries, ACCOUNTS, ["2026-08", "2026-09", "2026-10"])
    assert (aug.income, aug.expenses, aug.net, aug.savings_rate) == (
        Decimal(4000),
        Decimal(1000),
        Decimal(3000),
        Decimal("0.75"),
    )
    assert sep.savings_rate == Decimal("0.25")
    assert (oct_.income, oct_.expenses, oct_.savings_rate) == (0, 0, None)  # no income, no rate


def test_a_reversal_cancels_the_entry_it_reverses():
    wrong = _entry("2026-09-02", "food", "bank", "80", reversed_by="r")
    reversal = _entry("2026-09-03", "bank", "food", "80", "REVERSAL: x")
    right = _entry("2026-09-03", "food", "bank", "8")
    [sep] = cash_flow([wrong, reversal, right], ACCOUNTS, ["2026-09"])
    assert sep.expenses == Decimal(8)


def test_foreign_spending_is_counted_in_the_base_currency():
    entries = [_entry("2026-09-02", "food", "eur", "10", currency="EUR", fx_rate="1.10")]
    [sep] = cash_flow(entries, ACCOUNTS, ["2026-09"])
    assert sep.expenses == Decimal("11.00")


def test_spending_more_than_was_earned_is_a_negative_savings_rate():
    entries = [
        _entry("2026-09-01", "bank", "salary", "1000"),
        _entry("2026-09-02", "fun", "card", "1500"),
    ]
    [sep] = cash_flow(entries, ACCOUNTS, ["2026-09"])
    assert (sep.net, sep.savings_rate) == (Decimal(-500), Decimal("-0.5"))


# ── spending ──────────────────────────────────────────────────────────────────


def test_spending_by_category_falls_back_to_the_account_and_ranks_by_total():
    entries = [
        _entry("2026-09-01", "food", "bank", "30", tags={"category": "groceries"}),
        _entry("2026-10-01", "food", "bank", "50", tags={"category": "groceries"}),
        _entry("2026-10-02", "food", "bank", "20"),  # untagged: counted under its account
        _entry("2026-10-03", "fun", "bank", "100"),
        _entry("2026-10-04", "bank", "salary", "999"),  # income is not spending
    ]
    lines = spending(entries, ACCOUNTS, ["2026-09", "2026-10"])
    assert [(line.key, line.total) for line in lines] == [
        ("Fun", Decimal(100)),
        ("groceries", Decimal(80)),
        ("Food", Decimal(20)),
    ]
    assert lines[1].by_month == {"2026-09": Decimal(30), "2026-10": Decimal(50)}
    assert lines[0].by_month["2026-09"] == 0
    assert [line.share for line in lines] == [Decimal("0.5"), Decimal("0.4"), Decimal("0.1")]


def test_spending_by_account_and_by_need():
    entries = [
        _entry("2026-10-01", "food", "bank", "60", tags={"need": "essential"}),
        _entry("2026-10-02", "fun", "bank", "40", tags={"need": "discretionary"}),
        _entry("2026-10-03", "fun", "bank", "10"),
    ]
    by_account = spending(entries, ACCOUNTS, ["2026-10"], by="account")
    assert [(line.key, line.total) for line in by_account] == [
        ("Food", Decimal(60)),
        ("Fun", Decimal(50)),
    ]
    by_need = spending(entries, ACCOUNTS, ["2026-10"], by="need")
    assert [(line.key, line.total) for line in by_need] == [
        ("essential", Decimal(60)),
        ("discretionary", Decimal(40)),
        ("unclassified", Decimal(10)),
    ]


def test_a_refund_lowers_spending_and_a_fully_refunded_line_disappears():
    entries = [
        _entry("2026-10-01", "fun", "card", "100"),
        _entry("2026-10-09", "card", "fun", "100"),  # returned
        _entry("2026-10-02", "food", "bank", "40"),
        _entry("2026-10-03", "bank", "food", "15"),  # partly refunded
    ]
    lines = spending(entries, ACCOUNTS, ["2026-10"])
    assert [(line.key, line.total, line.share) for line in lines] == [
        ("Food", Decimal(25), Decimal(1))
    ]


def test_no_spending_is_no_lines():
    assert spending([], ACCOUNTS, ["2026-10"]) == []


# ── net worth ─────────────────────────────────────────────────────────────────


def test_net_worth_carries_balances_from_before_the_window_into_each_month_end():
    entries = [
        _entry("2025-01-01", "bank", "open", "5000"),  # long before the window
        _entry("2026-09-10", "fun", "card", "700"),
        _entry("2026-10-01", "bank", "salary", "1000"),
        _entry("2026-10-05", "card", "bank", "700"),
    ]
    sep, oct_ = net_worth_series(entries, ACCOUNTS, ["2026-09", "2026-10"])
    assert (sep.assets, sep.liabilities, sep.net_worth) == (
        Decimal(5000),
        Decimal(700),
        Decimal(4300),
    )
    assert (oct_.assets, oct_.liabilities, oct_.net_worth) == (Decimal(5300), 0, Decimal(5300))


def test_an_overdrawn_account_counts_as_owed():
    entries = [
        _entry("2026-10-01", "bank", "open", "100"),
        _entry("2026-10-02", "fun", "bank", "250"),
    ]
    [oct_] = net_worth_series(entries, ACCOUNTS, ["2026-10"])
    assert (oct_.assets, oct_.liabilities, oct_.net_worth) == (0, Decimal(150), Decimal(-150))


def test_foreign_holdings_are_valued_at_their_booked_rate():
    entries = [_entry("2026-10-01", "eur", "open", "100", currency="EUR", fx_rate="1.10")]
    [oct_] = net_worth_series(entries, ACCOUNTS, ["2026-10"])
    assert oct_.net_worth == Decimal("110.00")


# ── recurring payments ────────────────────────────────────────────────────────

TODAY = dt.date(2026, 10, 9)


def _charges(days: list[str], description: str, amounts: list[str] | str = "15.99", **kw):
    amounts = [amounts] * len(days) if isinstance(amounts, str) else amounts
    return [
        _entry(day, kw.get("to", "fun"), kw.get("source", "card"), amount, description)
        for day, amount in zip(days, amounts, strict=True)
    ]


def _recurring(entries):
    return detect_recurring(booked_transactions(entries, ACCOUNTS), TODAY)


def test_a_monthly_charge_is_found_with_when_the_next_one_is_due():
    entries = _charges(
        ["2026-06-30", "2026-07-30", "2026-08-31", "2026-09-30"],
        "NETFLIX.COM 866-579",
    )
    [netflix] = _recurring(entries)
    assert (netflix.payee, netflix.cadence, netflix.typical_amount, netflix.varies) == (
        "Netflix",
        "monthly",
        Decimal("15.99"),
        False,
    )
    assert (netflix.occurrences, netflix.last_date, netflix.next_expected) == (
        4,
        "2026-09-30",
        "2026-10-30",
    )
    assert (netflix.account_id, netflix.currency) == ("fun", "USD")
    assert netflix.entry_ids == tuple(e.id for e in entries)


def test_the_next_month_is_counted_in_calendar_months_on_the_usual_day():
    # On the 31st, which September does not have: October's is the 31st again.
    entries = _charges(["2026-07-31", "2026-08-31", "2026-09-30"], "GYM CLUB", "40")
    [gym] = detect_recurring(booked_transactions(entries, ACCOUNTS), dt.date(2026, 10, 1))
    assert (gym.next_expected, gym.anchor_days) == ("2026-10-31", (31,))
    entries = _charges(["2025-11-30", "2025-12-31", "2026-01-31"], "GYM CLUB", "40")
    [gym] = detect_recurring(booked_transactions(entries, ACCOUNTS), dt.date(2026, 2, 1))
    assert gym.next_expected == "2026-02-28"


def test_weekly_quarterly_and_yearly_rhythms():
    weekly = _charges(["2026-09-18", "2026-09-25", "2026-10-02", "2026-10-09"], "CLEANER", "30")
    quarterly = _charges(["2026-01-15", "2026-04-15", "2026-07-15"], "WATER BOARD", "60")
    yearly = _charges(["2023-11-01", "2024-11-01", "2025-11-01"], "DOMAIN RENEWAL", "12")
    found = {
        r.payee: r.cadence
        for r in detect_recurring(
            booked_transactions(weekly + quarterly + yearly, ACCOUNTS), dt.date(2026, 10, 9)
        )
    }
    assert found == {"Cleaner": "weekly", "Water Board": "quarterly", "Domain Renewal": "yearly"}


def test_a_charge_that_stopped_is_not_recurring():
    entries = _charges(["2026-04-01", "2026-05-01", "2026-06-01"], "OLD MAGAZINE")
    assert _recurring(entries) == []


def test_an_irregular_payee_is_not_recurring():
    entries = _charges(
        ["2026-08-01", "2026-08-03", "2026-08-20", "2026-09-29", "2026-10-02"], "STARBUCKS", "5"
    )
    assert _recurring(entries) == []


def test_two_charges_are_not_yet_a_rhythm():
    assert _recurring(_charges(["2026-08-30", "2026-09-30"], "SPOTIFY")) == []


def test_charges_that_vary_report_the_middle_amount():
    entries = _charges(
        ["2026-07-05", "2026-08-05", "2026-09-05", "2026-10-05"],
        "CITY POWER",
        ["80", "95", "120", "88"],
        to="food",
        source="bank",
    )
    [power] = _recurring(entries)
    assert (power.payee, power.typical_amount, power.varies) == (
        "City Power",
        Decimal("91.5"),
        True,
    )
    assert power.account_id == "food"


def test_money_coming_in_is_not_a_recurring_payment():
    entries = [
        _entry(day, "bank", "salary", "4000", "ACME PAYROLL")
        for day in ("2026-07-25", "2026-08-25", "2026-09-25")
    ]
    assert _recurring(entries) == []


def test_a_payee_is_named_the_way_its_charges_usually_are():
    entries = _charges(
        ["2026-07-02", "2026-08-02", "2026-09-02"], "POS 4411 BOLT OPERATIONS OU", "9"
    ) + _charges(["2026-10-02"], "BOLT.EU/O/2610", "9")
    [bolt] = _recurring(entries)
    assert (bolt.payee, bolt.key, bolt.occurrences) == ("Bolt Operations", "bolt", 4)


def test_one_payee_in_two_currencies_is_two_rhythms():
    usd = _charges(["2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01"], "SPOTIFY P1")
    eur = [
        _entry(day, "fun", "eur", "9.99", "SPOTIFY AB", currency="EUR", fx_rate="1.1")
        for day in ("2026-07-03", "2026-08-03", "2026-09-03", "2026-10-03")
    ]
    found = _recurring(usd + eur)
    assert sorted((r.payee, r.currency) for r in found) == [
        ("Spotify", "EUR"),
        ("Spotify", "USD"),
    ]


def test_a_charge_a_week_late_has_not_stopped():
    entries = _charges(["2026-06-30", "2026-07-30", "2026-08-30"], "GYM CLUB", "40")
    [gym] = detect_recurring(booked_transactions(entries, ACCOUNTS), dt.date(2026, 10, 6))
    assert gym.next_expected == "2026-09-30"


def test_income_is_found_when_asked_for():
    entries = [
        _entry(day, "bank", "salary", "4000", "ACME PAYROLL")
        for day in ("2026-07-25", "2026-08-25", "2026-09-25")
    ]
    booked = booked_transactions(entries, ACCOUNTS)
    assert detect_recurring(booked, TODAY) == []  # payments only, by default
    [salary] = detect_recurring(booked, TODAY, direction="in")
    assert (salary.direction, salary.money_account_id, salary.account_id) == (
        "in",
        "bank",
        "salary",
    )
    assert salary.next_expected == "2026-10-25"


def test_a_paycheck_every_other_week_is_biweekly():
    entries = [
        _entry(day, "bank", "salary", "2100", "ACME CORP PAYROLL")
        for day in ("2026-08-14", "2026-08-28", "2026-09-11", "2026-09-25")
    ]
    [pay] = detect_recurring(booked_transactions(entries, ACCOUNTS), TODAY, direction="in")
    assert (pay.cadence, pay.next_expected, pay.anchor_days) == ("biweekly", "2026-10-09", ())


def test_shopping_twice_a_month_on_set_days_is_not_a_rhythm():
    # The 8th and the 22nd, but never the same amount: groceries, not a bill.
    days = ["2026-07-08", "2026-07-22", "2026-08-08", "2026-08-22", "2026-09-08", "2026-09-22"]
    amounts = ["120", "84.20", "143.10", "97", "76.40", "131.55"]
    assert _recurring(_charges(days, "WHOLE FOODS #123", amounts)) == []


def test_a_salary_on_the_15th_and_the_last_is_semimonthly_not_biweekly():
    # 15/16-day gaps passed for every other week (26 paychecks a year, not 24).
    days = ["2026-07-15", "2026-07-31", "2026-08-14", "2026-08-31", "2026-09-15", "2026-09-30"]
    entries = [_entry(day, "bank", "salary", "2100", "ACME CORP PAYROLL") for day in days]
    [pay] = detect_recurring(booked_transactions(entries, ACCOUNTS), TODAY, direction="in")
    assert (pay.cadence, pay.anchor_days, pay.next_expected) == (
        "semimonthly",
        (15, 31),
        "2026-10-15",
    )


def test_every_other_week_is_tighter_than_twice_a_month():
    # 16-day gaps, drifting through the month: no rhythm at all now.
    days = ["2026-07-01", "2026-07-17", "2026-08-02", "2026-08-18", "2026-09-03"]
    entries = [
        _entry(day, "bank", "salary", str(100 + i), "ODD JOBS") for i, day in enumerate(days)
    ]
    assert detect_recurring(booked_transactions(entries, ACCOUNTS), TODAY, direction="in") == []


# ── What review found ─────────────────────────────────────────────────────────


def test_a_refund_only_line_has_no_share_and_the_others_stay_within_one():
    entries = [
        _entry("2026-10-02", "food", "bank", "100", tags={"category": "groceries"}),
        _entry("2026-10-03", "bank", "fun", "30", tags={"category": "concert"}),  # a refund
    ]
    lines = {line.key: line for line in spending(entries, ACCOUNTS, ["2026-10"], "account")}
    assert lines["Food"].share == Decimal(1)
    assert lines["Fun"].share is None and lines["Fun"].total == Decimal(-30)


def test_a_closed_account_is_still_owned_or_owed():
    closed = Account(
        id="old", user_id="u", code="1900", name="Old", type="asset", currency="USD",
        is_active=False,
    )  # fmt: skip
    entries = [_entry("2026-09-01", "old", "open", "500")]
    [point] = net_worth_series(entries, [*ACCOUNTS, closed], ["2026-10"])
    assert point.assets == Decimal(500)


def test_net_worth_from_opening_balances_and_the_windows_entries_alone():
    before = [
        _entry("2025-01-01", "bank", "open", "1000"),
        _entry("2025-02-01", "card", "bank", "0.5"),
    ]
    during = [_entry("2026-10-02", "food", "bank", "100")]
    from salli.domain.accounting.ledger import trial_balance

    whole = net_worth_series([*before, *during], ACCOUNTS, ["2026-09", "2026-10"])
    windowed = net_worth_series(during, ACCOUNTS, ["2026-09", "2026-10"], trial_balance(before))
    assert whole == windowed


def test_two_subscriptions_from_one_merchant_are_two():
    # APPLE.COM/BILL at 2.99 on the 3rd and 10.99 on the 5th merged, their
    # gaps looked irregular, and both disappeared.
    entries = [
        _entry(f"2026-{m:02d}-{d:02d}", "fun", "card", amount, "APPLE.COM/BILL")
        for m in (6, 7, 8, 9, 10)
        for d, amount in ((3, "2.99"), (5, "10.99"))
    ]
    found = detect_recurring(booked_transactions(entries, ACCOUNTS), dt.date(2026, 10, 9))
    assert sorted(r.typical_amount for r in found) == [Decimal("2.99"), Decimal("10.99")]
    assert {r.cadence for r in found} == {"monthly"}


def test_a_bill_that_drifts_in_price_stays_one_series():
    entries = [
        _entry(f"2026-{m:02d}-15", "fun", "card", amount, "CITY POWER")
        for m, amount in zip(range(5, 11), ("80", "85", "92", "101", "110", "120"), strict=True)
    ]
    [power] = detect_recurring(booked_transactions(entries, ACCOUNTS), dt.date(2026, 10, 20))
    assert power.occurrences == 6 and power.varies


def test_the_next_charge_is_on_its_anchor_day_nearest_a_period_on():
    # Paid 30 October for 1 November: next is 1 December, not 1 November.
    from salli.domain.reports.insights import next_due

    assert next_due(dt.date(2026, 10, 30), "monthly", (1,)) == dt.date(2026, 12, 1)
    # Rent for 30 September paid on 1 October: next is 30 October.
    assert next_due(dt.date(2026, 10, 1), "monthly", (30,)) == dt.date(2026, 10, 30)
    assert next_due(dt.date(2026, 10, 15), "monthly", (15,)) == dt.date(2026, 11, 15)


def test_a_salary_in_another_currency_says_its_amount_in_the_accounts():
    accounts = [
        Account(id="lkr", user_id="u", code="1", name="Bank", type="asset", currency="LKR"),
        Account(id="salary", user_id="u", code="4", name="Salary", type="income", currency="LKR"),
    ]
    entries = [
        _entry(day, "lkr", "salary", "3000", "ACME PAYROLL", currency="USD", fx_rate="300")
        for day in ("2026-07-25", "2026-08-25", "2026-09-25")
    ]
    [pay] = detect_recurring(
        booked_transactions(entries, accounts),
        TODAY,
        direction="in",
        currencies={a.id: a.currency for a in accounts},
        base="LKR",
    )
    assert (pay.typical_amount, pay.currency, pay.money_amount) == (
        Decimal(3000),
        "USD",
        Decimal(900000),
    )
