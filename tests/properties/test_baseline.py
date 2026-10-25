"""
Properties of the baseline (domain/baseline), over random ledgers:

- the daily cash timeline's month-ends are the monthly timeline's cash in
  each month's own money, whatever share of the surplus is invested:
  exactly, when the user set no inflation;
- an entry and its reversal change nothing;
- taking on a debt never raises net worth at the horizon, and paying one off
  faster never lowers it;
- the baseline as of a day doesn't depend on anything dated after it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salli.domain.baseline import BaselineDebt, timelines
from tests.baseline_ledger import Ledger

AS_OF = dt.date(2026, 10, 11)
MONTHS = [f"2025-{m:02d}" for m in range(11, 13)] + [f"2026-{m:02d}" for m in range(1, 11)]

amounts = st.decimals(min_value=Decimal("1"), max_value=Decimal("5000"), places=2)
#: Shares of the surplus invested a user might set.
SHARES = ("0", "0.35", "0.8", "1")
days = st.integers(min_value=1, max_value=28)


def ledger_accounts() -> Ledger:
    """The random ledgers' accounts, with nothing booked."""
    books = Ledger("SEK")
    books.account("bank", "asset")
    books.account("savings", "asset")
    books.account("euros", "asset", "EUR")
    books.account("funds", "asset", asset_role="investment")
    books.account("card", "liability")
    books.account("loan", "liability")
    books.account("equity", "equity")
    books.account("pay", "income")
    books.account("rent", "expense")
    books.account("food", "expense")
    books.account("fun", "expense")
    return books


@st.composite
def ledgers(draw: st.DrawFn) -> Ledger:
    """Books in krona with a euro account: pay, rent, spending on a card and
    from the bank, transfers to savings and to investments, at random."""
    books = ledger_accounts()
    books.book("2025-10-31", "bank", "equity", draw(amounts) * 10, description="Opening")
    books.book("2025-10-31", "equity", "loan", draw(amounts) * 20, description="Opening")
    books.book(
        "2025-10-31",
        "euros",
        "equity",
        draw(amounts),
        currency="EUR",
        fx="11.40",
        description="Opening",
    )
    start = draw(st.integers(min_value=0, max_value=len(MONTHS) - 1))
    for month in MONTHS[start:]:
        last = month == "2026-10"
        if draw(st.booleans()) and not last:
            books.book(f"{month}-25", "bank", "pay", draw(amounts) * 4, description="PAYROLL")
        books.book(
            f"{month}-01", "rent", "bank", "9500", description="RENT", tags={"need": "essential"}
        )
        for _ in range(draw(st.integers(min_value=0, max_value=3))):
            day = min(draw(days), 10) if last else draw(days)
            books.book(f"{month}-{day:02d}", "food", "card", draw(amounts), description="GROCER")
        if draw(st.booleans()):
            books.book(
                f"{month}-{min(draw(days), 10):02d}",
                "fun",
                "card",
                draw(amounts),
                description="CINEMA",
            )
        if not last:
            books.book(f"{month}-15", "card", "bank", draw(amounts), description="CARD PAYMENT")
            if draw(st.booleans()):
                books.book(f"{month}-26", "savings", "bank", "1000", description="TO SAVINGS")
            if draw(st.booleans()):
                books.book(f"{month}-27", "funds", "bank", "2000", description="TO FUNDS")
            books.book(f"{month}-05", "loan", "bank", "1500", description="LOAN")
    books.rate("EUR", "11.25", AS_OF.isoformat())
    if draw(st.booleans()):
        books.debt(
            "loan-terms", "0", draw(st.sampled_from(["0.03", "0.059", "0.12"])), "1500", "loan"
        )
    if draw(st.booleans()):
        books.debt("student", str(draw(amounts) * 10), "0.045", "800")
    figures: dict[str, str] = {}
    if draw(st.booleans()):
        figures["inflation"] = draw(st.sampled_from(["0.015", "0.024", "0.06"]))
    # The share of the surplus invested: the placeholder's all of it, or the
    # user's own.
    share = draw(st.sampled_from([None, *SHARES]))
    if share is not None:
        figures["surplus_invested"] = share
    if figures:
        books.assume(**figures)
    return books


_SETTINGS = settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@_SETTINGS
@given(ledgers())
def test_the_daily_timelines_month_ends_are_the_monthly_timelines_cash(books: Ledger):
    baseline = books.baseline(AS_OF)
    daily = timelines.daily(baseline)
    monthly = timelines.monthly(baseline, 1)
    points = monthly.points[1:]
    assert [m for m, _ in daily.month_ends] == [p.month for p in points]
    for (_, month_end), point in zip(daily.month_ends, points, strict=True):
        if baseline.inflation is None:
            assert point.deflator == 1
            assert month_end == point.cash  # exactly
        else:
            # Today's money is the month's own, deflated.
            assert abs(point.cash * point.deflator - month_end) < Decimal("1e-15")


@_SETTINGS
@given(ledgers(), st.data())
def test_an_entry_and_its_reversal_change_nothing(books: Ledger, data: st.DataObject):
    before = books.baseline(AS_OF)
    month = data.draw(st.sampled_from(MONTHS))
    day = data.draw(days) if month != "2026-10" else data.draw(st.integers(1, 10))
    debit, credit = data.draw(
        st.sampled_from([("food", "bank"), ("bank", "pay"), ("fun", "card"), ("savings", "bank")])
    )
    mistake = books.book(
        f"{month}-{day:02d}", debit, credit, data.draw(amounts), tags={"need": "essential"}
    )
    books.reverse(mistake)
    after = books.baseline(AS_OF)
    assert after.flows == before.flows
    assert after.balances == before.balances
    assert timelines.monthly(after, 2).points == timelines.monthly(before, 2).points


@_SETTINGS
@given(
    ledgers(),
    amounts,
    st.sampled_from(["0", "0.02", "0.069", "0.19"]),
    st.booleans(),
    st.integers(min_value=1, max_value=20),
)
def test_taking_on_a_debt_never_raises_net_worth_at_the_horizon(
    books: Ledger, principal: Decimal, apr: str, received: bool, years: int
):
    baseline = books.baseline(AS_OF)
    # A new debt the surplus doesn't already pay: owed from the as-of date,
    # its principal received into cash or not (a purchase on credit).
    loan = BaselineDebt(
        debt_id="new",
        name="New loan",
        apr=Decimal(apr),
        minimum_payment=(principal / 12).quantize(Decimal("0.01")) + 1,
        balance=principal * 10,
        source="declared",
        account_id=None,
        already_paid=Decimal(0),
    )
    borrowed = replace(baseline, debts=(*baseline.debts, loan))
    if received:
        cash = next(b for b in baseline.balances if b.account_id == "bank")
        balances = tuple(
            replace(b, amount=b.amount + loan.balance, value=b.value + loan.balance)
            if b is cash and b.amount is not None and b.value is not None
            else b
            for b in baseline.balances
        )
        borrowed = replace(borrowed, balances=balances)
    without = timelines.monthly(baseline, years).points[-1].net_worth
    with_debt = timelines.monthly(borrowed, years).points[-1].net_worth
    assert with_debt <= without


@_SETTINGS
@given(ledgers(), amounts, st.integers(min_value=1, max_value=20))
def test_paying_a_debt_off_faster_never_lowers_net_worth_at_the_horizon(
    books: Ledger, extra: Decimal, years: int
):
    baseline = books.baseline(AS_OF)
    faster = replace(baseline, debts=tuple(replace(d, extra_payment=extra) for d in baseline.debts))
    before = timelines.monthly(baseline, years).points[-1].net_worth
    after = timelines.monthly(faster, years).points[-1].net_worth
    assert after >= before


@_SETTINGS
@given(ledgers(), st.data())
def test_the_baseline_as_of_a_day_ignores_what_is_dated_after_it(
    books: Ledger, data: st.DataObject
):
    before = books.baseline(AS_OF)
    for _ in range(data.draw(st.integers(min_value=1, max_value=4))):
        later = AS_OF + dt.timedelta(days=data.draw(st.integers(min_value=1, max_value=400)))
        debit, credit = data.draw(
            st.sampled_from(
                [("food", "bank"), ("bank", "pay"), ("euros", "bank"), ("rent", "card")]
            )
        )
        books.book(later.isoformat(), debit, credit, data.draw(amounts))
    after = books.baseline(AS_OF)
    assert after == before
    assert timelines.daily(after) == timelines.daily(before)
