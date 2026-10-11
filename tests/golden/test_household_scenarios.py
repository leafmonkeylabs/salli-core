"""
Hand-worked scenarios on the household ledger (tests/golden/household.py).

The household, as of Sunday 2026-10-11, in euros: 15,801.47 of cash
(checking 6,543.15, savings 7,800.00, 2,500 USD at 0.86 = 2,150.00, less
691.68 on the card), 38,000 invested, a car loan (9,900.00 at 5.9%, 350 a
month, linked to its account) and a student loan the ledger doesn't hold
(8,000.00 at 4.5%, 120 a month). Income 4,000.00 and spending 2,037.09 a
month on average (1,898.32 of it essential); no inflation set, so nothing is
deflated and every "today's money" amount is its own.

What the ledger says keeps happening on checking, and so what moves it day
by day: the card payment (479.69) on the 15th, the salary (4,000.00) on the
25th, 500.00 to the brokerage and 300.00 to savings on the 26th, and the
rent (1,500.00) on the 1st.

Each test shows its arithmetic. Every figure is the scenario engine's,
through the same baseline the API builds.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.domain.baseline import Baseline, fi, timelines
from salli.domain.scenarios import comparison, engine, schema
from tests.golden import household as h

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def baseline() -> Baseline:
    uow = h.uow()
    return await BaselineService(uow.factory(), fx=h.fx(), today=lambda: h.AS_OF).build(h.USER)


def scenario(**doc: object) -> schema.Scenario:
    return schema.load({"schema": "salli.scenario/1", **doc})


def cents(value: Decimal | None) -> Decimal:
    assert value is not None
    return value.quantize(Decimal("0.01"))


async def test_the_baseline_these_start_from(baseline):
    """The figures every delta below is against."""
    base = engine.baseline_outlook(baseline)
    assert base.cash.forecast.today == Decimal("15801.47")
    assert (base.cash.forecast.lowest, base.cash.forecast.lowest_date) == (
        Decimal("15740.01"),
        "2026-10-18",
    )
    # The month-ends climb by the surplus, 1,962.91, plus what of the debts'
    # payments it already pays (the car loan's interest, 48.68, and the
    # student loan's whole 120.00), less their payments (350 + 120):
    # 1,661.59 a month, from October's 19,261.13 to 39,200.21 a year on.
    assert base.cash.month_ends[0] == ("2026-10", Decimal("19261.13"))
    assert base.cash.month_ends[1][1] - base.cash.month_ends[0][1] == Decimal("1661.59")
    assert base.cash.month_ends[-1] == ("2027-10", Decimal("39200.21"))
    assert (base.fi.months, base.fi.month) == (247, "2047-05")


async def test_a_one_off_purchase(baseline):
    laptop = scenario(
        label="Laptop",
        changes=[
            {
                "type": "one_off",
                "date": "2026-11-02",
                "amount": "-2400.00",
                "account": "chk",
                "label": "New laptop",
            }
        ],
    )
    result = engine.run(baseline, laptop)

    # Checking, from 6,543.15: the card payment on Oct 15 (-479.69, its low
    # until now: 6,063.46), the salary on the 25th (+4,000.00), 800.00 out on
    # the 26th, the rent on Nov 1 (-1,500.00): 7,763.46. The laptop on Nov 2
    # takes it to 5,363.46, and November's card payment on the 15th to
    # 4,883.77: its lowest. After that each month adds 4,000.00 and takes
    # 500 + 300 + 1,500 + 479.69, so it never falls that low again.
    chk = next(a for a in result.cash.accounts if a.account_id == "chk")
    assert (chk.lowest.baseline, chk.lowest_date.baseline) == (Decimal("6063.46"), "2026-10-15")
    assert (chk.lowest.scenario, chk.lowest_date.scenario) == (Decimal("4883.77"), "2026-11-15")
    assert chk.below_zero == (False, False)

    # Every day from Nov 2 on is 2,400.00 lower; cash earns nothing, so it
    # stays 2,400.00 lower, in today's money, at every horizon.
    assert result.cash.at_end.delta == Decimal("-2400.00")
    for point in result.monthly:
        assert cents(point.cash.delta) == Decimal("-2400.00")
        assert cents(point.net_worth.delta) == Decimal("-2400.00")
        assert point.investments.delta == 0 and point.debts.delta == 0
    assert [p.years for p in result.monthly] == [1, 5, 10, 20]

    # Safe-to-spend runs to the salary on Oct 25, before the laptop.
    assert result.cash.safe_until == "2026-10-25"
    assert result.cash.safe_to_spend.delta == 0

    # A one-off isn't spending for good: the FI number stays 2,037.09 × 12 /
    # 0.04 = 611,127. At 2047-05's end the baseline's FI base is 612,498.44,
    # 1,371.44 past it; 2,400.00 less falls short, so FI is a month later.
    assert result.fi.fi_number.scenario == Decimal("611127")
    base_points = engine.baseline_outlook(baseline).monthly.points
    assert cents(fi.asset_base(base_points[247 + 1])) == Decimal("612498.44")
    assert (result.fi.fi_month.baseline, result.fi.fi_month.scenario) == ("2047-05", "2047-06")
    assert result.fi.months_gained == -1

    # Emergency-fund months at the low point, over essential spending
    # (1,898.32 a month): the cash total's low, 15,740.01 before; the
    # laptop's November low is 15,072.91.
    assert result.resilience.basis == "essential"
    assert cents(result.cash.lowest.scenario) == Decimal("15072.91")
    assert result.resilience.lowest.baseline is not None
    assert cents(result.resilience.lowest.baseline) == Decimal("8.29")
    assert cents(result.resilience.lowest.scenario) == Decimal("7.94")
    assert result.break_evens == ()  # cash never goes below zero


async def test_a_loan_amortised_as_by_hand(baseline):
    loan = scenario(
        label="Borrow",
        changes=[
            {
                "type": "loan",
                "principal": "1200.00",
                "annual_rate": "0.12",
                "term_months": 6,
                "start": "2026-11-02",
                "into": "chk",
                "label": "Small loan",
            }
        ],
    )
    result = engine.run(baseline, loan)

    # The level payment: r = 0.12 / 12 = 0.01; 1,200 × 0.01 / (1 - 1.01^-6)
    # = 12 / 0.0579547647 = 207.0580…, rounded to 207.06. Taken out in
    # November, paid from December:
    #
    #   month    balance  interest  payment  left
    #   2026-12  1200.00    12.00    207.06  1004.94
    #   2027-01  1004.94    10.05    207.06   807.93
    #   2027-02   807.93     8.08    207.06   608.95
    #   2027-03   608.95     6.09    207.06   407.98
    #   2027-04   407.98     4.08    207.06   205.00
    #   2027-05   205.00     2.05    207.05     0.00   (the last clears it)
    #
    # Interest: 12.00 + 10.05 + 8.08 + 6.09 + 4.08 + 2.05 = 42.35.
    (applied,) = result.changes
    assert (applied.payment, applied.first_payment) == (Decimal("207.06"), "2026-12")
    months = timelines.periods(baseline.as_of, timelines.horizon_months(2))
    changes = engine.translate(baseline, loan, until=months[-1].end).changes
    schedule = timelines.monthly(baseline, 2, changes).debts[-1].schedule
    assert [(e.period, e.interest_paid, e.payment, e.remaining_balance) for e in schedule] == [
        ("2026-12", Decimal("12.00"), Decimal("207.06"), Decimal("1004.94")),
        ("2027-01", Decimal("10.05"), Decimal("207.06"), Decimal("807.93")),
        ("2027-02", Decimal("8.08"), Decimal("207.06"), Decimal("608.95")),
        ("2027-03", Decimal("6.09"), Decimal("207.06"), Decimal("407.98")),
        ("2027-04", Decimal("4.08"), Decimal("207.06"), Decimal("205.00")),
        ("2027-05", Decimal("2.05"), Decimal("207.05"), Decimal("0.00")),
    ]
    item = result.debts.items[-1]
    assert (item.source, item.paid_off.baseline, item.paid_off.scenario) == (
        "scenario",
        None,
        "2027-05",
    )
    assert (item.total_interest.baseline, item.total_interest.scenario) == (0, Decimal("42.35"))
    assert result.debts.total_interest.delta == Decimal("42.35")
    # The household's own debts still finish last.
    assert result.debts.debt_free.delta == 0

    # 1,200.00 in, 5 × 207.06 + 207.05 = 1,242.35 out: a year on, and ever
    # after, cash and net worth are 42.35 lower (the interest), and nothing
    # is owed on it.
    for point in result.monthly:
        assert cents(point.cash.delta) == Decimal("-42.35")
        assert cents(point.net_worth.delta) == Decimal("-42.35")
        assert point.debts.delta == 0


async def test_a_recurring_cost_that_pushes_cash_below_zero_and_its_break_even(baseline):
    rent = scenario(
        label="Bigger flat",
        changes=[
            {
                "type": "recurring",
                "amount": "-4000.00",
                "cadence": "monthly",
                "start": "2026-11-01",
                "account": "chk",
                "label": "Bigger flat",
            }
        ],
    )
    result = engine.run(baseline, rent)

    # The baseline adds 1,661.59 a month; 4,000.00 more out each month is a
    # fall of 2,338.41 a month, so cash runs out within the year: its low is
    # Oct 24, 2027, the day before the salary, after twelve payments.
    assert result.cash.lowest.scenario == Decimal("-12243.12")
    assert result.cash.lowest_date.scenario == "2027-10-24"
    chk = next(a for a in result.cash.accounts if a.account_id == "chk")
    assert chk.below_zero == (False, True)

    # The break-even: cash stays at or above zero while, on every day d,
    # baseline(d) - amount × payments-by-d >= 0. The tightest day is that
    # same Oct 24: the baseline has 35,756.88 then, after 12 payments, and
    # 35,756.88 / 12 = 2,979.74 exactly. So up to 2,979.74 a month keeps cash
    # at or above zero over the year; a cent more doesn't.
    base = dict(engine.baseline_outlook(baseline).cash.forecast.daily)
    assert base["2027-10-24"] == Decimal("35756.88")
    assert Decimal("35756.88") / 12 == Decimal("2979.74")
    (floor,) = result.break_evens
    assert (floor.kind, floor.status, floor.change) == ("recurring_cash_floor", "found", 0)
    assert floor.value == Decimal("2979.74")
    assert (floor.low, floor.high) == (Decimal(0), Decimal("4000.00"))

    def lowest(amount: str) -> Decimal:
        trial = scenario(
            changes=[{**rent.changes[0].model_dump(by_alias=True, mode="json"), "amount": amount}]
        )
        return engine.run(baseline, trial).cash.lowest.scenario or Decimal(0)

    assert lowest("-2979.74") == Decimal("0.00")
    assert lowest("-2979.75") < 0

    # A new rent with no end is spending for good: the FI number rises by
    # 4,000 × 12 / 0.04 = 1,200,000, to 1,811,127.
    assert result.fi.fi_number.delta == Decimal("1200000")


async def test_debt_or_invest_and_the_return_where_investing_wins(baseline):
    invest = scenario(
        label="Invest",
        horizon_years=10,
        changes=[
            {
                "type": "invest",
                "amount": "5000.00",
                "date": "2026-12-01",
                "from": "sav",
                "label": "Bonus, invested",
            }
        ],
    )
    pay_down = scenario(
        label="Pay down",
        horizon_years=10,
        changes=[
            {
                "type": "extra_debt_payment",
                "debt": "debt-student",
                "monthly": "5000.00",
                "from": "2026-12-01",
                "to": "2026-12-31",
                "label": "Bonus, on the student loan",
            }
        ],
    )
    result = comparison.compare(baseline, [invest, pay_down])
    by_label = dict(zip(result.labels, result.options, strict=True))

    # Paying 5,000.00 off the student loan in December clears it in 2029-01
    # rather than 2033-03, and its interest falls from 1,223.12 to 197.29:
    # 1,025.83 saved. Both loans are paid off within the ten years, so that
    # is the whole of what paying it down adds to net worth at the horizon.
    student = next(d for d in by_label["Pay down"].debts.items if d.debt_id == "debt-student")
    assert (student.paid_off.baseline, student.paid_off.scenario) == ("2033-03", "2029-01")
    assert (student.total_interest.baseline, student.total_interest.scenario) == (
        Decimal("1223.12"),
        Decimal("197.29"),
    )
    assert cents(by_label["Pay down"].monthly[-1].net_worth.delta) == Decimal("1025.83")

    # Investing it instead: the 5,000.00 joins the investments at December's
    # end and grows from January 2027 to October 2036, 118 months, at r / 12
    # a month: it adds 5,000 × ((1 + r/12)^118 - 1). That beats 1,025.83
    # first at a real return of 1.90% (1,026.24); at 1.89% it is 1,020.33.
    def gain(r: str) -> Decimal:
        return Decimal(5000) * ((1 + Decimal(r) / 12) ** 118 - 1)

    assert cents(gain("0.0190")) == Decimal("1026.24")
    assert cents(gain("0.0189")) == Decimal("1020.33")
    (break_even,) = result.break_evens
    assert (break_even.kind, break_even.status) == ("invest_vs_debt_return", "found")
    assert (break_even.option, break_even.options) == ("Invest", ("Invest", "Pay down"))
    assert break_even.value == Decimal("0.0190")

    # Neither is "best": at the base 4% investing ends ahead at ten years;
    # paying down keeps more cash and owes less sooner. The trade says so.
    trade = {(t.option, t.against): t for t in result.trade}
    gains = {d.figure for d in trade[("Invest", "Pay down")].gains}
    gives_up = {d.figure for d in trade[("Invest", "Pay down")].gives_up}
    assert "monthly.10y.net_worth" in gains
    assert {"monthly.1y.debts", "debts.total_interest"} <= gives_up
    assert {d.figure for d in trade[("Pay down", "Invest")].gains} == gives_up

    # Sensitivity: at the conservative 2% the investing option is still just
    # ahead at ten years; at the growth 6%, further.
    sens = {o.option: dict(o.by_return) for o in result.sensitivity}
    for name in ("conservative", "base", "growth"):
        assert sens["Invest"][name].net_worth.delta is not None
    ahead = {
        name: (sens["Invest"][name].net_worth.scenario or 0)
        - (sens["Pay down"][name].net_worth.scenario or 0)
        for name in ("conservative", "base", "growth")
    }
    assert 0 < ahead["conservative"] < ahead["base"] < ahead["growth"]


async def test_an_income_change(baseline):
    raise_ = scenario(
        label="New job",
        changes=[
            {
                "type": "income_change",
                "monthly_net": "+600.00",
                "from": "2027-01-01",
                "label": "New job",
            }
        ],
    )
    result = engine.run(baseline, raise_)

    # 600.00 more on the 1st of each month from January 2027: by October
    # 2027's end that is ten months, 6,000.00; by 2031-10, 58 months,
    # 34,800.00; by 2036-10, 118, 70,800.00; by 2046-10, 238, 142,800.00.
    # All of it in cash, which earns nothing.
    assert [(p.years, cents(p.cash.delta)) for p in result.monthly] == [
        (1, Decimal("6000.00")),
        (5, Decimal("34800.00")),
        (10, Decimal("70800.00")),
        (20, Decimal("142800.00")),
    ]
    # Nothing changes before January: the low point, safe-to-spend.
    assert result.cash.lowest.delta == 0 and result.cash.safe_to_spend.delta == 0
    # Income isn't spending: the FI number stays; FI comes 49 months sooner.
    assert result.fi.fi_number.delta == 0
    assert (result.fi.fi_month.scenario, result.fi.months_gained) == ("2043-04", 49)


async def test_cash_or_instalments_and_the_rate_they_cost_the_same(baseline):
    """can_i_afford's comparison: with no inflation set, paying later at any
    rate above 0% costs more, so the break-even rate is 0%."""
    purchase = {"type": "one_off", "date": "2026-11-02", "amount": "-2400.00", "label": "Laptop"}
    cash = scenario(label="Pay cash", changes=[purchase])
    instalments = scenario(
        label="Instalments",
        changes=[
            purchase,
            {
                "type": "loan",
                "principal": "2400.00",
                "annual_rate": "0.069",
                "term_months": 12,
                "start": "2026-11-02",
                "label": "Laptop instalments",
            },
        ],
    )
    result = comparison.compare(baseline, [cash, instalments])
    by_label = dict(zip(result.labels, result.options, strict=True))
    # 2,400 at 6.9% over 12 months: r = 0.00575, 2,400 × r / (1 - 1.00575^-12)
    # = 207.55; the twelve payments carry 90.68 of interest.
    loan = by_label["Instalments"].changes[1]
    assert loan.payment == Decimal("207.55")
    assert by_label["Instalments"].debts.items[-1].total_interest.scenario == Decimal("90.68")
    # A year on (2027-10) eleven payments are made and 89.49 of the interest
    # has accrued; by five years on the loan is gone and net worth is the
    # price and all its interest lower: 2,400.00 + 90.68.
    one_year, five_years = by_label["Instalments"].monthly[:2]
    assert cents(one_year.net_worth.delta) == Decimal("-2489.49")
    assert cents(five_years.net_worth.delta) == Decimal("-2490.68")
    assert cents(by_label["Pay cash"].monthly[1].net_worth.delta) == Decimal("-2400.00")
    (rate,) = result.break_evens
    assert (rate.kind, rate.option, rate.status, rate.value) == (
        "loan_rate",
        "Instalments",
        "found",
        Decimal("0"),
    )


async def test_cancelling_a_subscription(baseline):
    cancel = scenario(
        label="Cancel streaming",
        changes=[{"type": "stop_recurring", "key": "streamflix", "from": "2026-11-01"}],
    )
    result = engine.run(baseline, cancel)
    # Streamflix, 12.99 a month on the card on the 8th: from November it
    # stays with the household, twelve times in the year to 2027-10, 155.88;
    # and it was spending, so the FI number falls by 12.99 × 12 / 0.04 =
    # 3,897.
    (applied,) = result.changes
    assert applied.label == "Stop Streamflix" and applied.monthly == Decimal("12.99")
    assert result.cash.at_end.delta == Decimal("155.88")
    assert result.fi.fi_number.delta == Decimal("-3897")


async def test_nothing_is_written(baseline):
    uow = h.uow()
    service_baseline = await BaselineService(uow.factory(), fx=h.fx(), today=lambda: h.AS_OF).build(
        h.USER
    )
    before = (list(uow.ledger.entries), dict(uow.debts.rows), list(uow.fi_scores.rows))
    engine.run(
        service_baseline,
        scenario(
            changes=[{"type": "one_off", "date": "2026-11-02", "amount": "-1.00", "label": "x"}]
        ),
    )
    assert (list(uow.ledger.entries), dict(uow.debts.rows), list(uow.fi_scores.rows)) == before
    assert dt.date(2026, 10, 11) == baseline.as_of
