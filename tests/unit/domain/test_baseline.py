"""
The baseline (domain/baseline): one definition of income and expenses,
balances by role at the as-of rates, debts counted once, and two timelines
that agree.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from decimal import Decimal

import pytest

from salli.domain.baseline import timelines
from salli.domain.baseline.flows import observed_months
from tests.baseline_ledger import Ledger

AS_OF = dt.date(2027, 3, 18)


def _household() -> Ledger:
    """Swiss francs; a dollar account; pay on the 25th, rent on the 2nd."""
    books = Ledger("CHF")
    books.account("bank", "asset")
    books.account("dollars", "asset", "USD")
    books.account("funds", "asset", asset_role="investment")
    books.account("home", "asset", asset_role="other")
    books.account("card", "liability")
    books.account("mortgage", "liability")
    books.account("equity", "equity")
    books.account("pay", "income")
    books.account("rent", "expense")
    books.account("food", "expense")
    books.book("2026-11-30", "bank", "equity", "5000", description="Opening balance")
    books.book("2026-11-30", "funds", "equity", "20000", description="Opening balance")
    books.book("2026-11-30", "home", "equity", "400000", description="Opening balance")
    books.book("2026-11-30", "equity", "mortgage", "300000", description="Opening balance")
    books.book(
        "2026-11-30", "dollars", "equity", "1000", currency="USD", fx="0.90", description="Opening"
    )
    for month in ("2026-12", "2027-01", "2027-02", "2027-03"):
        books.book(
            f"{month}-02", "rent", "bank", "1800", description="RENT", tags={"need": "essential"}
        )
        books.book(f"{month}-10", "food", "card", "400", description="GROCER")
        if month != "2027-03":
            books.book(f"{month}-25", "bank", "pay", "6000", description="PAYROLL")
            books.book(f"{month}-15", "card", "bank", "400", description="CARD PAYMENT")
    books.rate("USD", "0.88", AS_OF.isoformat())
    return books


# ── Income and expenses ──────────────────────────────────────────────────────


def test_the_months_observed_are_full_months_from_the_first_flow():
    assert observed_months(AS_OF, "2026-12-02") == ["2026-12", "2027-01", "2027-02"]
    assert observed_months(AS_OF, None) == []
    # A ledger begun part-way through a month counts that month.
    assert observed_months(AS_OF, "2027-02-27") == ["2027-02"]
    # Twelve at most, and never the as-of month, which isn't over.
    assert observed_months(AS_OF, "2020-01-01") == [
        f"{y}-{m:02d}" for y, m in [(2026, n) for n in range(3, 13)] + [(2027, 1), (2027, 2)]
    ]
    assert observed_months(dt.date(2027, 3, 1), "2027-03-01") == []


def test_income_and_expenses_are_netted_per_month_and_averaged_over_those_observed():
    books = _household()
    mistake = books.book("2027-01-20", "food", "card", "250", description="GROCER")
    books.reverse(mistake)
    flows = books.baseline(AS_OF).flows

    assert flows.months == ("2026-12", "2027-01", "2027-02")
    # (3 × 6,000) / 3 and (3 × 2,200) / 3: the reversed 250 counts nothing.
    assert (flows.income, flows.expenses, flows.surplus) == (
        Decimal(6000),
        Decimal(2200),
        Decimal(3800),
    )
    assert flows.savings_rate == Decimal(3800) / Decimal(6000)
    # Rent is essential; groceries carry no need tag.
    assert flows.essential == Decimal(1800)
    assert flows.need_coverage == Decimal(1800) / Decimal(2200)
    assert [m.net for m in flows.by_month] == [Decimal(3800)] * 3


def test_without_need_tags_there_is_no_essential_figure():
    books = Ledger("NZD")
    books.account("bank", "asset")
    books.account("pay", "income")
    books.account("food", "expense")
    books.book("2027-02-25", "bank", "pay", "100")
    books.book("2027-02-26", "food", "bank", "40")
    flows = books.baseline(AS_OF).flows
    assert flows.essential is None
    assert flows.need_coverage == Decimal(0)


def test_with_no_full_month_yet_the_monthly_figures_are_zero_and_said():
    books = Ledger("NZD")
    books.account("bank", "asset")
    books.account("pay", "income")
    books.book("2027-03-05", "bank", "pay", "100")
    baseline = books.baseline(AS_OF)
    assert baseline.flows.months == ()
    assert baseline.flows.surplus == 0
    assert any("No full calendar month" in n for n in baseline.notes)


# ── Balances, roles and rates ────────────────────────────────────────────────


def test_balances_are_valued_at_the_published_rate_for_the_as_of_date():
    baseline = _household().baseline(AS_OF)
    by_id = {b.account_id: b for b in baseline.balances}
    dollars = by_id["dollars"]
    # 1,000 USD, bought at 0.90 (900.00 in the books), worth 880.00 at 0.88.
    assert (dollars.amount, dollars.value, dollars.role) == (
        Decimal(1000),
        Decimal("880.00"),
        "cash",
    )
    [rate] = baseline.rates
    assert (rate.currency, rate.rate, rate.source, rate.as_of) == (
        "USD",
        Decimal("0.88"),
        "test-bank",
        "2027-03-18",
    )
    assert (by_id["funds"].role, by_id["home"].role, by_id["card"].role) == (
        "investment",
        "other_asset",
        "liability",
    )


def test_without_a_published_rate_an_account_is_left_out_and_said():
    books = _household()
    books.rates.clear()
    baseline = books.baseline(AS_OF)
    dollars = next(b for b in baseline.balances if b.account_id == "dollars")
    assert (dollars.amount, dollars.value) == (Decimal(1000), None)
    assert baseline.rates[0].rate is None
    assert any("no published USD rate for 2027-03-18" in n for n in baseline.cash_notes)


def test_a_linked_debt_is_counted_once_and_an_unlinked_one_as_declared():
    books = _household()
    books.debt("mortgage-terms", "310000", "0.024", "1500", account_id="mortgage")
    books.debt("car", "12000", "0.069", "300")
    baseline = books.baseline(AS_OF)

    mortgage, car = baseline.debts
    # The account says 300,000 is owed (the declared 310,000 is ignored).
    assert (mortgage.source, mortgage.balance) == ("account", Decimal(300000))
    assert mortgage.already_paid == Decimal("600.00")  # 300,000 × 2.4% / 12
    assert (car.source, car.balance, car.already_paid) == ("declared", Decimal(12000), Decimal(300))
    # The mortgage account is the debt, not another liability on top: what
    # is left without terms is the card's 400 (not cash: it paid for one
    # kind of thing only).
    assert baseline.other_liabilities == Decimal(400)
    # Card 400 owed, the mortgage account 300,000, and the car declared 12,000.
    assert baseline.total_liabilities == Decimal(312400)
    assert baseline.net_worth == baseline.total_assets - Decimal(312400)


def test_an_investment_is_never_cash_whatever_paid_from_it():
    books = _household()
    books.book("2027-02-01", "food", "funds", "10", description="FUND FEE")
    baseline = books.baseline(AS_OF)
    cash = {b.account_id for b in baseline.balances if b.in_cash}
    # The card paid only one kind of expense, so it isn't cash.
    assert cash == {"bank", "dollars"}


# ── The timelines ────────────────────────────────────────────────────────────


def test_the_first_month_is_the_rest_of_the_as_of_month():
    first, second = timelines.periods(AS_OF, 2)
    assert (first.month, first.start, first.end, first.share) == (
        "2027-03",
        AS_OF,
        dt.date(2027, 3, 31),
        Decimal(14) / Decimal(31),
    )
    assert (second.month, second.start, second.share) == ("2027-04", dt.date(2027, 4, 1), 1)


def test_debt_schedules_land_on_calendar_months():
    books = _household()
    books.debt("car", "1000", "0.12", "400")
    monthly = timelines.monthly(books.baseline(AS_OF), 1)
    [car] = monthly.debts
    # The first payment is in the month after the as-of month.
    assert [(e.period, e.payment, e.remaining_balance) for e in car.schedule] == [
        ("2027-04", Decimal("400.00"), Decimal("610.00")),
        ("2027-05", Decimal("400.00"), Decimal("216.10")),
        ("2027-06", Decimal("218.26"), Decimal("0.00")),
    ]
    assert car.paid_off == monthly.debt_free == "2027-06"
    owed = {p.month: p.debts for p in monthly.points[1:5]}
    assert owed == {
        "2027-03": Decimal(1000),
        "2027-04": Decimal("610.00"),
        "2027-05": Decimal("216.10"),
        "2027-06": Decimal(0),
    }


def test_a_paid_off_debt_leaves_its_payment_in_cash():
    books = _household()
    books.debt("car", "1000", "0.12", "400")
    baseline = books.baseline(AS_OF)
    points = {p.month: p for p in timelines.monthly(baseline, 1).points[1:]}
    surplus = baseline.flows.surplus
    # While it's paid, the 400 is in the surplus already: cash grows by it.
    assert points["2027-05"].cash - points["2027-04"].cash == surplus
    # The last payment is smaller: the rest stays.
    assert points["2027-06"].cash - points["2027-05"].cash == surplus + Decimal("181.74")
    # Once it's paid off, the whole payment stays.
    assert points["2027-07"].cash - points["2027-06"].cash == surplus + 400


def test_investments_grow_at_the_real_return_and_other_assets_keep_their_value():
    books = _household()
    books.assume(real_return="0.06")
    monthly = timelines.monthly(books.baseline(AS_OF), 1)
    start, march, april = monthly.points[:3]
    assert march.investments == Decimal(20000) * (1 + Decimal("0.005") * Decimal(14) / 31)
    assert april.investments == march.investments * Decimal("1.005")
    assert start.other_assets == april.other_assets == Decimal(400000)
    assert monthly.real_return == Decimal("0.06")


def test_without_inflation_nominal_amounts_keep_their_real_value_and_it_is_said():
    baseline = _household().baseline(AS_OF)
    assert "inflation" in baseline.placeholders
    assert all(p.deflator == 1 for p in timelines.monthly(baseline, 2).points)


def test_with_inflation_cash_and_debts_are_deflated():
    books = _household()
    books.debt("car", "12000", "0.069", "300")
    books.assume(inflation="0.024")
    baseline = books.baseline(AS_OF)
    assert "inflation" not in baseline.placeholders
    points = timelines.monthly(baseline, 1).points
    april = points[2]
    assert april.deflator == (1 + Decimal("0.002") * Decimal(14) / 31) * Decimal("1.002")
    daily = timelines.daily(baseline)
    month_ends = dict(daily.month_ends)
    # Today's money is each month's own, deflated.
    assert abs(april.cash * april.deflator - month_ends["2027-04"]) < Decimal("1e-18")


def test_net_worth_is_everything_owned_less_everything_owed_at_every_point():
    books = _household()
    books.debt("car", "12000", "0.069", "300")
    books.debt("mortgage-terms", "300000", "0.024", "1500", account_id="mortgage")
    baseline = books.baseline(AS_OF)
    first = timelines.monthly(baseline, 2).points[0]
    assert first.net_worth == baseline.net_worth
    for p in timelines.monthly(baseline, 2).points:
        assert p.net_worth == (
            p.cash + p.investments + p.other_assets - p.debts - p.other_liabilities
        )


def test_the_daily_timeline_ends_each_month_where_the_plan_does():
    baseline = _household().baseline(AS_OF)
    daily = timelines.daily(baseline)
    monthly = timelines.monthly(baseline, 1)
    assert daily.forecast.start == "2027-03-18"
    assert daily.forecast.end == "2028-03-31"
    assert [m for m, _ in daily.month_ends] == [p.month for p in monthly.points[1:]]
    assert [v for _, v in daily.month_ends] == [p.cash for p in monthly.points[1:]]


def test_changes_move_both_timelines_alike():
    from salli.domain.reports.forecast import Flow

    baseline = _household().baseline(AS_OF)
    laptop = Flow("2027-05-03", None, Decimal("-2400"), "CHF", "Laptop", "change")
    before = timelines.monthly(baseline, 1)
    after = timelines.monthly(baseline, 1, [laptop])
    changed = timelines.daily(baseline, [laptop])
    deltas = [a.cash - b.cash for a, b in zip(after.points, before.points, strict=True)]
    assert deltas[:3] == [0, 0, 0]  # as-of, March, April
    assert set(deltas[3:]) == {Decimal(-2400)}
    assert [v for _, v in changed.month_ends] == [p.cash for p in after.points[1:]]


def test_a_horizon_is_one_to_fifty_years():
    baseline = _household().baseline(AS_OF)
    assert len(timelines.monthly(baseline, 50).points) == 1 + 50 * 12 + 1
    for bad in (0, 51):
        with pytest.raises(ValueError, match="horizon"):
            timelines.monthly(baseline, bad)


def test_an_extra_payment_on_a_debt_comes_out_of_cash_and_off_the_debt():
    books = _household()
    books.debt("car", "6000", "0.069", "300")
    baseline = books.baseline(AS_OF)
    extra = replace(
        baseline, debts=tuple(replace(d, extra_payment=Decimal(200)) for d in baseline.debts)
    )
    before = {p.month: p for p in timelines.monthly(baseline, 1).points[1:]}
    after = {p.month: p for p in timelines.monthly(extra, 1).points[1:]}
    assert after["2027-04"].cash == before["2027-04"].cash - 200
    assert after["2027-04"].debts == before["2027-04"].debts - 200
