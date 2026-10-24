"""
FI on the baseline's monthly timeline (domain/baseline/fi.py), and the
changes the timelines take (domain/baseline/timelines.py): loans taken out
later, extra payments for a run of months, money moved into investments.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from decimal import Decimal

from salli.domain.baseline import Baseline, BaselineDebt, fi, timelines
from salli.domain.debt import engine as debt_engine
from salli.domain.debt.models import Debt
from salli.domain.fi.assumptions import Applied
from salli.domain.reports.forecast import Flow
from tests.baseline_ledger import Ledger

AS_OF = dt.date(2026, 10, 11)


def _with_share(baseline: Baseline, share: str) -> Baseline:
    """`baseline` with the user's own share of the surplus invested."""
    applied = Applied(Decimal(share), "user", "test")
    return replace(baseline, assumptions=replace(baseline.assumptions, surplus_invested=applied))


def _books(rent: str = "1500", pay: str = "4000") -> Ledger:
    books = Ledger("NOK")
    books.account("bank", "asset")
    books.account("funds", "asset", asset_role="investment")
    books.account("equity", "equity")
    books.account("pay", "income")
    books.account("rent", "expense")
    books.book("2026-06-30", "bank", "equity", "10000", description="Opening")
    books.book("2026-06-30", "funds", "equity", "20000", description="Opening")
    for month in ("2026-07", "2026-08", "2026-09"):
        books.book(f"{month}-01", "rent", "bank", rent, description="RENT")
        books.book(f"{month}-25", "bank", "pay", pay, description="PAYROLL")
    return books


def test_the_fi_number_is_a_year_of_spending_over_the_withdrawal_rate():
    baseline = _books().baseline(AS_OF)
    # 1,500 a month × 12 / 0.04 (the placeholder rate).
    assert fi.spending(baseline) == Decimal("1500")
    assert fi.fi_number(baseline) == Decimal("450000")
    assert fi.fi_number(baseline, Decimal("2000")) == Decimal("600000")
    # No spending, no number (never "already FI").
    assert fi.fi_number(baseline, Decimal(0)) == 0


def test_the_fi_month_is_where_the_timelines_base_reaches_the_number():
    baseline = _books().baseline(AS_OF)
    timeline = fi.full_timeline(baseline)
    number = fi.fi_number(baseline)
    months = fi.months_to_fi(timeline.points, number)
    assert months is not None
    # The month before falls short; this one reaches it.
    assert (
        fi.asset_base(timeline.points[months])
        < number
        <= fi.asset_base(timeline.points[months + 1])
    )
    assert fi.fi_month(baseline, months) == debt_engine.month_after("2026-10", months)
    # 0 when it is reached already; None without a number.
    assert fi.months_to_fi(timeline.points, Decimal("1")) == 0
    assert fi.months_to_fi(timeline.points, Decimal(0)) is None
    # Not within 50 years: None, never a date.
    assert fi.months_to_fi(timeline.points, Decimal("1e12")) is None


def test_the_fi_base_is_cash_and_investments_less_debts():
    baseline = _books().baseline(AS_OF)
    first = fi.full_timeline(baseline).points[0]
    # 10,000 opened, then three months of 4,000 in and 1,500 out; 20,000 invested.
    assert first.cash == Decimal("17500")
    assert fi.asset_base(first) == Decimal("37500")
    years = fi.year_points(fi.full_timeline(baseline).points, 3)
    assert [p.month for p in years] == ["2026-10", "2027-10", "2028-10", "2029-10"]


def test_a_loan_taken_out_later_is_owed_from_its_month_and_cleared_by_its_term():
    baseline = _books().baseline(AS_OF)
    payment = Decimal("858.03")  # 5,000 at 6% over 6 months, rounded
    loan = BaselineDebt(
        debt_id="later",
        name="Later",
        apr=Decimal("0.06"),
        minimum_payment=payment,
        balance=Decimal("5000"),
        source="scenario",
        account_id=None,
        already_paid=Decimal(0),
        opened="2027-01",
        first_payment="2027-02",
        term_months=6,
    )
    arrives = Flow("2027-01-15", None, Decimal("5000"), "NOK", "Borrowed", "change")
    changes = timelines.Changes(flows=(arrives,), loans=(loan,))
    months = timelines.periods(AS_OF, 13)
    (path,) = timelines.debt_paths(baseline, months, changes)
    owed = dict(zip((p.month for p in months), path.owed, strict=True))
    paid = dict(zip((p.month for p in months), path.payments, strict=True))
    assert owed["2026-12"] == 0 and owed["2027-01"] == Decimal("5000")
    assert paid["2027-01"] == 0 and paid["2027-02"] == payment
    assert path.paid_off == "2027-07" and owed["2027-07"] == 0
    # The last payment clears what the rounding left.
    assert path.schedule[-1].remaining_balance == 0
    assert sum(path.payments) == Decimal("5000") + path.total_interest
    # Its payments are scheduled ones, out of the regular surplus: so much
    # less is invested each month it is paid.
    plan = timelines.cash_plan(baseline, months, [path], changes)
    paid_months = [i for i, p in enumerate(path.payments) if p]
    assert all(plan[i].regular == plan[i].planned for i in paid_months)
    before_plan = timelines.cash_plan(baseline, months, [], timelines.NO_CHANGES)
    assert [before_plan[i].invested - plan[i].invested for i in paid_months] == [
        path.payments[i] for i in paid_months
    ]
    # The money borrowed is a move into cash, where it stays: a year on, cash
    # is 5,000 higher, and the investments lower by the payments and what
    # they would have earned by then, at the placeholder 4%.
    before = timelines.monthly(baseline, 1)
    after = timelines.monthly(baseline, 1, changes)
    assert after.points[-1].cash - before.points[-1].cash == Decimal("5000")
    forgone = sum(
        (path.payments[i] * (1 + Decimal("0.04") / 12) ** (12 - i) for i in paid_months),
        Decimal(0),
    )
    cent = Decimal("0.01")
    lower = before.points[-1].investments - after.points[-1].investments
    assert lower.quantize(cent) == forgone.quantize(cent) == Decimal("5181.66")
    assert after.points[-1].debts == before.points[-1].debts
    # With none of the surplus invested, cash takes the money and the
    # payments: a year on, it is down by the interest alone.
    kept = _with_share(baseline, "0")
    assert (
        timelines.monthly(kept, 1).points[-1].cash
        - timelines.monthly(kept, 1, changes).points[-1].cash
        == path.total_interest
    )


def test_an_extra_payment_runs_for_its_months_only():
    def plan(extra):
        return debt_engine.compute_payoff_plan(
            [Debt("Loan", Decimal("10000"), Decimal("0.05"), Decimal("200"))],
            extra,
            "avalanche",
            first_month="2026-11",
        )

    steady = plan(Decimal(0))
    # 1,000 more in the plan's months 2 and 3 only.
    burst = plan(lambda m: Decimal(1000) if m in (2, 3) else Decimal(0))
    payments = [e.payment for e in burst.schedule]
    assert payments[:4] == [Decimal("200"), Decimal("1200"), Decimal("1200"), Decimal("200")]
    assert burst.total_interest_paid < steady.total_interest_paid
    assert burst.months_to_payoff is not None and steady.months_to_payoff is not None
    assert burst.months_to_payoff < steady.months_to_payoff


def test_a_term_clears_the_loan_whatever_the_rounding_left():
    # 1,000 at 0% over 3 months: 333.33 a month leaves 0.01 for the last.
    plan = debt_engine.compute_payoff_plan(
        [Debt("Loan", Decimal("1000"), Decimal(0), Decimal("333.33"), term_months=3)],
        Decimal(0),
        "avalanche",
    )
    assert [e.payment for e in plan.schedule] == [
        Decimal("333.33"),
        Decimal("333.33"),
        Decimal("333.34"),
    ]
    assert plan.months_to_payoff == 3


def test_money_moved_into_investments_grows_with_them():
    baseline = _books().baseline(AS_OF)
    moved = timelines.Changes(
        flows=(Flow("2026-11-02", None, Decimal("-1000"), "NOK", "Invest", "change"),),
        invested=(("2026-11-02", Decimal("1000")),),
    )
    before = timelines.monthly(baseline, 1)
    after = timelines.monthly(baseline, 1, moved)
    # In at November's end, then eleven months to October 2027 at 4% / 12.
    grown = Decimal(1000) * (1 + Decimal("0.04") / 12) ** 11
    cent = Decimal("0.01")
    gained = after.points[-1].investments - before.points[-1].investments
    assert gained.quantize(cent) == grown.quantize(cent) == Decimal("1037.28")
    assert before.points[-1].cash - after.points[-1].cash == Decimal("1000")


# ── An extra payment before a debt's first payment ───────────────────────────
#
# A debt owed on the as-of date is first paid in the month after the as-of
# month, a loan in the month after it is taken out. An extra payment in the
# month before (the as-of month, or the loan's opening month) is paid at
# that month's end, up to what is owed, out of cash, before the schedule
# starts.


def _card() -> Baseline:
    """The books with a card owing 1,000.00 at 12% a year (1% a month),
    100.00 a month, the ledger not holding it."""
    books = _books()
    books.debt("card", "1000", "0.12", "100")
    return books.baseline(AS_OF)


def _extra(amount: str, start: str = "2026-10", end: str | None = "2026-10") -> timelines.Changes:
    return timelines.Changes(extra=(timelines.ExtraPayment("card", start, end, Decimal(amount)),))


def test_an_extra_payment_in_the_as_of_month_is_paid_at_its_end():
    baseline = _card()
    months = timelines.periods(AS_OF, 13)
    (before,) = timelines.debt_paths(baseline, months)
    (after,) = timelines.debt_paths(baseline, months, _extra("300"))
    # Owed at the as-of month's end: 1,000.00 - 300.00, nothing scheduled yet.
    assert after.owed[0] == Decimal("700") and before.owed[0] == Decimal("1000")
    assert (after.payments[0], after.extra[0], after.scheduled[0]) == (
        Decimal("300"),
        Decimal("300"),
        Decimal(0),
    )
    # November's interest is on 700.00: 7.00, so 100.00 leaves 607.00
    # (10.00 and 910.00 without it).
    nov = next(e for e in after.schedule if e.period == "2026-11")
    assert (nov.interest_paid, nov.payment, nov.remaining_balance) == (
        Decimal("7.00"),
        Decimal("100.00"),
        Decimal("607.00"),
    )
    assert after.owed[1] == Decimal("607.00") and before.owed[1] == Decimal("910.00")
    # Then, at 1% a month and 100.00 a month (half up to the cent):
    # 607.00 → 6.07 → 513.07 → 5.13 → 418.20 → 4.18 → 322.38 → 3.22 → 225.60
    # → 2.26 → 127.86 → 1.28 → 29.14 → 0.29, the last 29.43 clearing it in
    # 2027-06. Interest: 7.00 + 6.07 + 5.13 + 4.18 + 3.22 + 2.26 + 1.28 +
    # 0.29 = 29.43.
    assert [e.interest_paid for e in after.schedule if e.month] == [
        Decimal(x) for x in ("7.00", "6.07", "5.13", "4.18", "3.22", "2.26", "1.28", "0.29")
    ]
    assert after.total_interest == Decimal("29.43") < before.total_interest
    assert after.paid_off == "2027-06"
    # In the schedule as month 0, in the as-of month.
    assert (after.schedule[0].month, after.schedule[0].period) == (0, "2026-10")
    # Out of cash in the as-of month: the plan's extra, and so its cash.
    plan = timelines.cash_plan(baseline, months, [after], _extra("300"))
    base = timelines.cash_plan(baseline, months, [before])
    assert plan[0].extra == Decimal("300")
    assert base[0].cash_change - plan[0].cash_change == Decimal("300")
    # Both timelines agree: 300.00 less cash at the as-of month's end, on
    # the daily timeline (spread over the rest of the month, as every extra
    # payment is) and the monthly, whose debts are 300.00 less too, so net
    # worth is the same.
    daily = dict(timelines.daily(baseline).month_ends)
    daily_after = dict(timelines.daily(baseline, _extra("300")).month_ends)
    assert daily["2026-10"] - daily_after["2026-10"] == Decimal("300")
    was = timelines.monthly(baseline, 1).points[1]
    now = timelines.monthly(baseline, 1, _extra("300")).points[1]
    assert (was.cash - now.cash, was.debts - now.debts) == (Decimal("300"), Decimal("300"))
    assert now.net_worth == was.net_worth
    monthly = timelines.monthly(baseline, 1, _extra("300"))
    (card,) = monthly.debts
    assert (card.total_interest, card.owed[0]) == (Decimal("29.43"), Decimal("700"))


def test_an_extra_payment_that_clears_the_debt_pays_it_off_in_the_as_of_month():
    baseline = _card()
    months = timelines.periods(AS_OF, 13)
    (before,) = timelines.debt_paths(baseline, months)
    # 1,500.00 asked, 1,000.00 owed: only what is owed is paid.
    (after,) = timelines.debt_paths(baseline, months, _extra("1500"))
    assert after.paid_off == "2026-10"
    assert after.extra[0] == Decimal("1000") and after.total_interest == 0
    assert all(owed == 0 for owed in after.owed)
    assert sum(after.payments) == Decimal("1000") and sum(after.scheduled) == 0
    # Its 100.00 a month is freed into the regular surplus from November,
    # and 1,000.00 (not 1,500.00) leaves cash in October.
    plan = timelines.cash_plan(baseline, months, [after], _extra("1500"))
    base = timelines.cash_plan(baseline, months, [before])
    assert plan[0].extra == Decimal("1000")
    assert plan[1].planned - base[1].planned == Decimal("100")
    monthly = timelines.monthly(baseline, 1, _extra("1500"))
    assert monthly.debt_free == "2026-10"
    assert monthly.points[1].debts == 0


def test_a_recurring_extra_payment_from_the_as_of_month_keeps_that_months_one():
    baseline = _card()
    months = timelines.periods(AS_OF, 13)
    (path,) = timelines.debt_paths(baseline, months, _extra("50", "2026-10", "2026-12"))
    # 50.00 at October's end, then 100.00 + 50.00 in November and December:
    # 950.00 → 9.50 → 809.50 → 8.10 → 667.60.
    assert path.extra[:4] == (Decimal("50"), Decimal("50"), Decimal("50"), Decimal(0))
    assert path.owed[:3] == (Decimal("950"), Decimal("809.50"), Decimal("667.60"))
    plan = timelines.cash_plan(baseline, months, [path], _extra("50", "2026-10", "2026-12"))
    assert [m.extra for m in plan[:4]] == [Decimal("50"), Decimal("50"), Decimal("50"), 0]


def test_an_extra_payment_in_a_loans_opening_month_is_paid_at_its_end():
    baseline = _books().baseline(AS_OF)
    loan = BaselineDebt(
        debt_id="later",
        name="Later",
        apr=Decimal("0.06"),
        minimum_payment=Decimal("858.03"),  # 5,000 at 6% over 6 months
        balance=Decimal("5000"),
        source="scenario",
        account_id=None,
        already_paid=Decimal(0),
        opened="2027-01",
        first_payment="2027-02",
        term_months=6,
    )
    arrives = Flow("2027-01-15", None, Decimal("5000"), "NOK", "Borrowed", "change")
    changes = timelines.Changes(
        flows=(arrives,),
        loans=(loan,),
        extra=(timelines.ExtraPayment("later", "2027-01", "2027-01", Decimal("2000")),),
    )
    months = timelines.periods(AS_OF, 13)
    (path,) = timelines.debt_paths(baseline, months, changes)
    owed = dict(zip((p.month for p in months), path.owed, strict=True))
    extra = dict(zip((p.month for p in months), path.extra, strict=True))
    # Owed 5,000.00 from January, 2,000.00 of it paid at its end.
    assert owed["2026-12"] == 0 and owed["2027-01"] == Decimal("3000")
    assert extra["2027-01"] == Decimal("2000")
    # Then 858.03 a month at 0.5%: 3,000.00 → 15.00 → 2,156.97 → 10.78 →
    # 1,309.72 → 6.55 → 458.24 → 2.29, the last 460.53 clearing it in May.
    assert [e.interest_paid for e in path.schedule if e.month] == [
        Decimal(x) for x in ("15.00", "10.78", "6.55", "2.29")
    ]
    assert path.schedule[-1].payment == Decimal("460.53")
    assert (path.paid_off, path.total_interest) == ("2027-05", Decimal("34.62"))
    # Out of cash in January, as an extra payment.
    plan = timelines.cash_plan(baseline, months, [path], changes)
    assert plan[3].period.month == "2027-01" and plan[3].extra == Decimal("2000")
