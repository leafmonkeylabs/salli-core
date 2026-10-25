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

The share of each month's regular surplus invested is the placeholder,
all of it (`surplus_invested`): what the baseline's surplus, a recurring
change, an income change or a debt's freed payment adds each month goes
into the investments at the month's end and grows at the real return (4%,
a placeholder too); one-offs, a loan's money, invest moves and extra
payments go where they say. A figure that changed when the share became an
assumption says so: "surplus invested at the placeholder 100%" (before, the
whole surplus stayed in cash, which is the share at 0).

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

#: The placeholder real return, a twelfth of it a month.
MONTHLY = Decimal("0.04") / 12


async def _baseline(**profile: object) -> Baseline:
    uow = h.uow(**profile)
    return await BaselineService(uow.factory(), fx=h.fx(), today=lambda: h.AS_OF).build(h.USER)


@pytest.fixture
async def baseline() -> Baseline:
    return await _baseline()


@pytest.fixture
async def cash_only() -> Baseline:
    """The household with none of its surplus invested: the whole of it stays
    in cash, as before the share was an assumption."""
    return await _baseline(
        fi_assumptions={"surplus_invested": {"value": "0", "source": "kept in cash"}}
    )


def grown(amount: Decimal, months: int, monthly: Decimal = MONTHLY) -> Decimal:
    """`amount` invested at a month's end, `months` month-ends later."""
    return amount * (1 + monthly) ** months


def scenario(**doc: object) -> schema.Scenario:
    return schema.load({"schema": "salli.scenario/1", **doc})


def cents(value: Decimal | None) -> Decimal:
    assert value is not None
    return value.quantize(Decimal("0.01"))


async def test_the_baseline_these_start_from(baseline):
    """The figures every delta below is against."""
    assert baseline.surplus_invested == 1
    assert "surplus_invested" in baseline.placeholders
    base = engine.baseline_outlook(baseline)
    assert base.cash.forecast.today == Decimal("15801.47")
    # The regular surplus is the surplus, 1,962.91, plus what of the debts'
    # payments it already pays (the car loan's interest, 48.68, and the
    # student loan's whole 120.00), less their payments (350 + 120):
    # 1,661.59 a month; in the rest of October, 3,459.66 (its salary in it).
    plan = dict(base.cash.invested)
    assert (plan["2026-10"], plan["2026-11"], plan["2027-10"]) == (
        Decimal("3459.66"),
        Decimal("1661.59"),
        Decimal("1661.59"),
    )
    # Was: the month-ends climbed by it, from October's 19,261.13 to
    # 39,200.21 a year on. Surplus invested at the placeholder 100%: each
    # month's leaves cash for the investments at its end, so every month
    # ends where today does.
    assert {v for _, v in base.cash.month_ends} == {Decimal("15801.47")}
    # Was 15,740.01 on Oct 18. Surplus invested at the placeholder 100%,
    # the low is now a month's dip before its salary on the 25th, lowest in
    # February, whose 28 days put the most of the month's unscheduled
    # spending (250.97, spread evenly) before it: 15,801.47 less the rent
    # (1,500.00), streaming (12.99), eating out (74.45) and 24/28 of the
    # 250.97 (215.12).
    assert (base.cash.forecast.lowest, base.cash.forecast.lowest_date) == (
        Decimal("13998.91"),
        "2027-02-24",
    )
    assert dict(base.cash.unscheduled)["2027-02"] == Decimal("-250.97")
    # Was 247 months (2047-05): surplus invested at the placeholder 100%
    # (tests/golden/test_household_fi.py works through it); then 187
    # (2042-05), before the plan-consistency pass.
    assert (base.fi.months, base.fi.month) == (214, "2044-08")


async def test_with_none_of_the_surplus_invested_the_baseline_is_the_cash_only_one(cash_only):
    """Share 0: the whole surplus stays in cash, and the figures are those
    from before the share was an assumption."""
    base = engine.baseline_outlook(cash_only)
    assert {v for _, v in base.cash.invested} == {Decimal(0)}
    assert base.cash.month_ends[0] == ("2026-10", Decimal("19261.13"))
    assert base.cash.month_ends[1][1] - base.cash.month_ends[0][1] == Decimal("1661.59")
    assert base.cash.month_ends[-1] == ("2027-10", Decimal("39200.21"))
    assert (base.cash.forecast.lowest, base.cash.forecast.lowest_date) == (
        Decimal("15740.01"),
        "2026-10-18",
    )
    assert (base.fi.months, base.fi.month) == (294, "2051-04")  # was 247 (2047-05)


async def test_the_emergency_fund_and_safe_to_spend_count_cash_alone(baseline, cash_only):
    """What is invested never counts as an emergency fund, nor as money to
    spend: both read cash, which the share invested leaves at each month's
    end."""
    nothing = scenario(changes=[])
    invested, kept = engine.run(baseline, nothing), engine.run(cash_only, nothing)
    # Safe-to-spend reads what is scheduled before the next income and the
    # everyday spending: the same whatever the share.
    assert invested.cash.safe_to_spend.baseline == kept.cash.safe_to_spend.baseline
    assert invested.cash.safe_to_spend.baseline == Decimal("15316.35")
    # Emergency-fund months are cash over essential spending (1,898.32 a
    # month). A year on, with the surplus invested, cash is still 15,801.47:
    # 8.32 months; kept in cash, it is 39,200.21: 20.65 months.
    essential = baseline.flows.essential
    assert essential is not None and cents(essential) == Decimal("1898.32")
    assert invested.cash.at_end.baseline == Decimal("15801.47")
    assert invested.resilience.at_end.baseline == Decimal("15801.47") / essential
    assert cents(invested.resilience.at_end.baseline) == Decimal("8.32")
    assert cents(kept.resilience.at_end.baseline) == Decimal("20.65")
    # The FI score's emergency fund is today's cash-role balances: 8.10
    # months whatever the share (tests/golden/test_household_fi.py).


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
    # stays 2,400.00 lower, in today's money, at every horizon. A one-off is
    # a move out of cash: what is invested each month doesn't change.
    assert result.cash.at_end.delta == Decimal("-2400.00")
    for point in result.monthly:
        assert cents(point.cash.delta) == Decimal("-2400.00")
        assert cents(point.net_worth.delta) == Decimal("-2400.00")
        assert point.investments.delta == 0 and point.debts.delta == 0
    assert [p.years for p in result.monthly] == [1, 5, 10, 20]

    # Safe-to-spend runs to the salary on Oct 25, before the laptop.
    assert result.cash.safe_until == "2026-10-25"
    assert result.cash.safe_to_spend.delta == 0

    # A one-off isn't spending for good: the FI number stays 1,868.41 × 12 /
    # 0.0314 = 714,042.04 (was 2,037.09 × 12 / 0.04 = 611,127, before the
    # debts' payments left the spending and the rate was derived). FI is
    # 2044-08, whose end has 716,046.90 less the emergency fund held out
    # (11,210.46), 2,004.86 past it; 2,400.00 less falls short, so FI is a
    # month later, as it was.
    assert cents(result.fi.fi_number.scenario) == Decimal("714042.04")
    base_points = engine.baseline_outlook(baseline).monthly.points
    held_out = fi.reserve(baseline)
    assert cents(fi.asset_base(base_points[214 + 1], held_out)) == Decimal("716046.90")
    assert (result.fi.fi_month.baseline, result.fi.fi_month.scenario) == ("2044-08", "2044-09")
    assert result.fi.months_gained == -1

    # Emergency-fund months at the low point, over essential spending
    # (1,898.32 a month). Was 15,740.01 and 15,072.91, so 8.29 and 7.94.
    # Surplus invested at the placeholder 100%, the cash total's low is
    # February's, 13,998.91 (see the baseline), and the laptop leaves it
    # 2,400.00 lower: the surplus that would have made it up is invested, not
    # kept. The emergency fund is cash alone: what is invested never counts.
    assert result.resilience.basis == "essential"
    assert cents(result.cash.lowest.scenario) == Decimal("11598.91")
    assert result.cash.lowest_date.scenario == "2027-02-24"
    assert result.resilience.lowest.baseline is not None
    assert cents(result.resilience.lowest.baseline) == Decimal("7.37")
    assert cents(result.resilience.lowest.scenario) == Decimal("6.11")
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

    # 1,200.00 in, 5 × 207.06 + 207.05 = 1,242.35 out. Was: a year on, and
    # ever after, cash and net worth 42.35 lower (the interest). Surplus
    # invested at the placeholder 100%: the money borrowed is a move into
    # cash, where it stays, 1,200.00 more ever after; the payments are
    # scheduled ones, out of the regular surplus, so each month from
    # December to May that much less is invested, and what it would have
    # earned is lost too. A year on (2027-10's end), the December payment
    # would have grown ten months, May's five.
    payments = [e.payment for e in schedule]
    forgone = sum(
        (grown(p, months) for p, months in zip(payments, range(10, 4, -1), strict=True)),
        Decimal(0),
    )
    assert cents(forgone) == Decimal("1273.77")
    one_year = result.monthly[0]
    assert cents(one_year.cash.delta) == Decimal("1200.00")
    assert cents(one_year.investments.delta) == Decimal("-1273.77")
    # 42.35 of interest and 31.42 of growth forgone; nothing owed on it.
    assert cents(one_year.net_worth.delta) == Decimal("-73.77")
    for point in result.monthly:
        assert cents(point.cash.delta) == Decimal("1200.00")
        assert point.debts.delta == 0
    # The forgone 1,242.35 keeps compounding while the 1,200.00 earns
    # nothing in cash.
    assert [cents(p.net_worth.delta) for p in result.monthly] == [
        Decimal("-73.77"),
        Decimal("-294.38"),
        Decimal("-624.64"),
        Decimal("-1520.23"),
    ]


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

    # The regular surplus of 1,661.59 a month becomes a deficit of 2,338.41:
    # a deficit invests nothing and is drawn from cash, never from the
    # investments, so cash runs out within the year. Its low is Oct 24,
    # 2027, the day before the salary, after twelve payments. Was
    # -12,243.12. Surplus invested at the placeholder 100%: the rest of
    # October (3,459.66) was invested at October's end, before the new rent
    # starts, so cash is that much lower: the baseline's 14,019.73 that day,
    # less twelve rents of 4,000.00, plus the eleven months' 1,661.59
    # (November to September) the baseline invested and the deficit takes.
    base = dict(engine.baseline_outlook(baseline).cash.forecast.daily)
    assert base["2027-10-24"] == Decimal("14019.73")
    assert Decimal("14019.73") - 12 * Decimal(4000) + 11 * Decimal("1661.59") == Decimal(
        "-15702.78"
    )
    assert result.cash.lowest.scenario == Decimal("-15702.78")
    assert result.cash.lowest_date.scenario == "2027-10-24"
    chk = next(a for a in result.cash.accounts if a.account_id == "chk")
    assert chk.below_zero == (False, True)
    # Cash is below zero at a month's end from May 2027 (15,801.47 less
    # seven deficits of 2,338.41), and the result says so.
    assert any("below zero from the end of 2027-05" in n for n in result.notes)

    # The break-even: the most the rent can be with cash at or above zero.
    # Above the regular surplus, cash on Oct 24, 2027 is the baseline's
    # 14,019.73, less twelve rents, plus the eleven months' surplus the
    # deficit takes: 14,019.73 + 11 × 1,661.59 - 12 × amount >= 0, so at
    # most 32,297.22 / 12 = 2,691.435, to the cent 2,691.43. Was 2,979.74
    # (35,756.88 / 12): surplus invested at the placeholder 100%, October's
    # 3,459.66 is invested before the rent starts, 288.31 a month less.
    (floor,) = result.break_evens
    assert (floor.kind, floor.status, floor.change) == ("recurring_cash_floor", "found", 0)
    assert floor.value == Decimal("2691.43")
    assert (floor.low, floor.high) == (Decimal(0), Decimal("4000.00"))

    def lowest(amount: str) -> Decimal:
        trial = scenario(
            changes=[{**rent.changes[0].model_dump(by_alias=True, mode="json"), "amount": amount}]
        )
        return engine.run(baseline, trial).cash.lowest.scenario or Decimal(0)

    # 32,297.22 - 12 × 2,691.43 = 0.06; a cent more each time is 0.12 more.
    assert lowest("-2691.43") == Decimal("0.06")
    assert lowest("-2691.44") == Decimal("-0.06")

    # A new rent with no end is spending for good: the FI number rises by
    # 4,000 × 12 over the rate (was / 0.04 = 1,200,000).
    swr = baseline.assumptions.safe_withdrawal_rate.value
    assert cents(result.fi.fi_number.delta) == cents(Decimal(48000) / swr)


def _bonus_options() -> tuple[schema.Scenario, schema.Scenario]:
    """A 5,000.00 bonus in December: invested, or paid off the student loan
    (4.5%), over ten years."""
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
    return invest, pay_down


def _student_schedule(baseline: Baseline, option: schema.Scenario) -> list[tuple[str, Decimal]]:
    months = timelines.periods(baseline.as_of, timelines.horizon_months(10))
    changes = engine.translate(baseline, option, until=months[-1].end).changes
    (student,) = [
        d for d in timelines.monthly(baseline, 10, changes).debts if d.debt_id == "debt-student"
    ]
    return [(e.period, e.payment) for e in student.schedule]


async def test_debt_or_invest_breaks_even_at_the_loans_own_rate(baseline):
    """Both sides treated alike: the bonus comes out of cash either way, and
    what each frees or earns afterwards is invested at the same share (the
    placeholder's 100%), so investing beats paying down a 4.5% loan once the
    real return is the loan's own rate."""
    invest, pay_down = _bonus_options()
    result = comparison.compare(baseline, [invest, pay_down])
    by_label = dict(zip(result.labels, result.options, strict=True))

    # Paying 5,000.00 off the student loan in December clears it in 2029-01
    # rather than 2033-03, and its interest falls from 1,223.12 to 197.29:
    # 1,025.83 saved.
    student = next(d for d in by_label["Pay down"].debts.items if d.debt_id == "debt-student")
    assert (student.paid_off.baseline, student.paid_off.scenario) == ("2033-03", "2029-01")
    assert (student.total_interest.baseline, student.total_interest.scenario) == (
        Decimal("1223.12"),
        Decimal("197.29"),
    )

    # What paying down frees: its last payment is 77.29 in 2029-01, so 42.71
    # of that month's 120.00; 120.00 a month from 2029-02 to 2033-02, and the
    # 103.12 the other option still pays in 2033-03. 6,025.83 in all: the
    # 5,000.00 and the 1,025.83 of interest saved. It joins the regular
    # surplus, and is invested at each month's end.
    paid = _student_schedule(baseline, pay_down)
    unpaid = _student_schedule(baseline, invest)
    assert (paid[1], paid[-1], unpaid[-1]) == (
        ("2026-12", Decimal("5120.00")),
        ("2029-01", Decimal("77.29")),
        ("2033-03", Decimal("103.12")),
    )
    freed = [("2029-01", Decimal("42.71"))]
    freed += [
        (timelines.periods(dt.date(2029, 2, 1), 49)[k].month, Decimal(120)) for k in range(49)
    ]
    freed += [("2033-03", Decimal("103.12"))]
    assert sum((f for _, f in freed), Decimal(0)) == Decimal("6025.83")

    # The horizon is 2036-10's end. Investing: the 5,000.00 goes in at
    # December's end and grows 118 months. Paying down: each freed payment
    # grows from its month's end. Both start with the same 5,000.00 out of
    # cash, and both loans are gone by the horizon, so net worth differs by
    # these alone. At the loan's 4.5% they are the same to two cents: the
    # cents its interest is rounded to each month.
    end = timelines.month_index("2036-10")
    at_loan_rate = Decimal("0.045") / 12

    def by_horizon(amounts: list[tuple[str, Decimal]], monthly: Decimal) -> Decimal:
        return sum(
            (grown(f, end - timelines.month_index(m), monthly) for m, f in amounts), Decimal(0)
        )

    assert cents(by_horizon([("2026-12", Decimal(5000))], at_loan_rate)) == Decimal("7776.53")
    assert cents(by_horizon(freed, at_loan_rate)) == Decimal("7776.55")

    # So the break-even is the loan's own rate, within the bisection's basis
    # point: at 4.50% investing ends 0.02 behind, at 4.51% ahead. Was 1.90%,
    # when the freed payments sat in cash, earning nothing, while the 5,000.00
    # invested compounded: now surplus invested at the placeholder 100%, both
    # sides are treated alike.
    def net_worth(option: schema.Scenario, rate: str) -> Decimal:
        changes = engine.translate(baseline, option).changes
        timeline = timelines.monthly(baseline, 10, changes, real_return=Decimal(rate))
        return timeline.points[-1].net_worth

    def ahead(rate: str) -> Decimal:
        return net_worth(invest, rate) - net_worth(pay_down, rate)

    assert cents(ahead("0.0450")) == Decimal("-0.02")
    assert cents(ahead("0.0451")) == Decimal("3.18")
    (break_even,) = result.break_evens
    assert (break_even.kind, break_even.status) == ("invest_vs_debt_return", "found")
    assert (break_even.option, break_even.options) == ("Invest", ("Invest", "Pay down"))
    assert break_even.value == Decimal("0.0451")
    assert abs(break_even.value - Decimal("0.045")) <= comparison.RATE_STEP

    # At the base 4%, below the loan's rate, paying down ends ahead at every
    # horizon. Was: investing ahead at ten years. Each option: the 5,000.00
    # out of cash, and 5,000.00 grown 118 months (7,404.72) or the freed
    # 6,025.83 grown from 2029 (7,558.51).
    assert cents(by_label["Invest"].monthly[-1].net_worth.delta) == Decimal("2404.72")
    assert cents(by_label["Pay down"].monthly[-1].net_worth.delta) == Decimal("2558.51")
    assert cents(by_horizon(freed, MONTHLY)) == Decimal("7558.51")

    # Neither is "best": the trade says what each gains and gives up.
    # Investing holds more invested at one and five years; paying down owes
    # less sooner and, by ten years, holds more invested too, from what it
    # freed.
    trade = {(t.option, t.against): t for t in result.trade}
    gains = {d.figure for d in trade[("Invest", "Pay down")].gains}
    gives_up = {d.figure for d in trade[("Invest", "Pay down")].gives_up}
    assert gains == {"monthly.1y.investments", "monthly.5y.investments"}
    assert {
        "monthly.10y.net_worth",
        "monthly.10y.investments",
        "monthly.1y.debts",
        "debts.total_interest",
        "debts.debt_free",
    } <= gives_up
    assert {d.figure for d in trade[("Pay down", "Invest")].gains} == gives_up

    # Sensitivity: at the conservative 2% and the base 4%, paying down ends
    # ten years ahead; at the growth 6%, investing does. The lead flips
    # between them, as the break-even says.
    sens = {o.option: dict(o.by_return) for o in result.sensitivity}
    lead = {
        name: (sens["Invest"][name].net_worth.scenario or 0)
        - (sens["Pay down"][name].net_worth.scenario or 0)
        for name in ("conservative", "base", "growth")
    }
    assert lead["conservative"] < lead["base"] < 0 < lead["growth"]


async def test_debt_or_invest_with_none_of_the_surplus_invested(cash_only):
    """Share 0: what paying down frees stays in cash, which earns nothing,
    while the 5,000.00 invested compounds. The two sides are no longer
    treated alike, and investing comes out ahead from far below the loan's
    rate: the 1.90% this test found before the share was an assumption."""
    invest, pay_down = _bonus_options()
    result = comparison.compare(cash_only, [invest, pay_down])
    by_label = dict(zip(result.labels, result.options, strict=True))

    # Paying down adds the interest it saves, and nothing more: the freed
    # 6,025.83 sits in cash, against the 5,000.00 it cost.
    assert cents(by_label["Pay down"].monthly[-1].net_worth.delta) == Decimal("1025.83")
    # Investing is unchanged: the 5,000.00 grows 118 months whatever the
    # share, since the share is of the regular surplus, not of a move.
    assert cents(by_label["Invest"].monthly[-1].net_worth.delta) == Decimal("2404.72")

    # Investing beats 1,025.83 at the lowest r where 5,000 × ((1 + r/12)^118
    # - 1) does: 1.90% (1,026.24); at 1.89% it is 1,020.33.
    def gain(r: str) -> Decimal:
        return Decimal(5000) * ((1 + Decimal(r) / 12) ** 118 - 1)

    assert cents(gain("0.0190")) == Decimal("1026.24")
    assert cents(gain("0.0189")) == Decimal("1020.33")
    (break_even,) = result.break_evens
    assert (break_even.kind, break_even.status, break_even.value) == (
        "invest_vs_debt_return",
        "found",
        Decimal("0.0190"),
    )


async def test_an_income_change(baseline):
    raise_ = scenario(
        label="New job",
        changes=[
            {
                "type": "income_change",
                "monthly": "+600.00",
                "from": "2027-01-01",
                "label": "New job",
            }
        ],
    )
    result = engine.run(baseline, raise_)

    # 600.00 more on the 1st of each month from January 2027, regular
    # surplus. Was: all of it in cash, 6,000.00 more by October 2027's end,
    # 34,800.00 by 2031-10, 70,800.00 by 2036-10 and 142,800.00 by 2046-10.
    # Surplus invested at the placeholder 100%: each 600.00 goes into the
    # investments at its month's end, so cash ends each month as before, and
    # the investments grow by the ten 600.00s to October 2027 with what they
    # earn: 600 × ((1 + 0.04/12)^10 - 1) / (0.04/12) = 6,090.80.
    assert cents(sum((grown(Decimal(600), k) for k in range(10)), Decimal(0))) == Decimal("6090.80")
    assert [(p.years, cents(p.cash.delta), cents(p.investments.delta)) for p in result.monthly] == [
        (1, Decimal("0.00"), Decimal("6090.80")),
        (5, Decimal("0.00"), Decimal("38321.48")),
        (10, Decimal("0.00"), Decimal("86569.79")),
        (20, Decimal("0.00"), Decimal("217410.95")),
    ]
    # Safe-to-spend doesn't change: its window ends before January.
    assert result.cash.safe_to_spend.delta == 0
    # Was: the low point didn't change either. Surplus invested at the
    # placeholder 100%, the baseline's low (Feb 24, 2027) is in a month the
    # 600.00 has come in on the 1st and stays until the month's end, so the
    # scenario's low is November's, before the new job: 14,013.25, 14.34
    # higher.
    assert result.cash.lowest.scenario == Decimal("14013.25")
    assert result.cash.lowest_date.scenario == "2026-11-24"
    assert result.cash.lowest.delta == Decimal("14.34")
    # Income isn't spending: the FI number stays. Was 49 months sooner
    # (2047-05 to 2043-04); surplus invested at the placeholder 100%, FI
    # comes 30 months sooner, from the baseline's 2042-05; now 34 months
    # sooner, from 2044-08 (the plan-consistency pass).
    assert result.fi.fi_number.delta == 0
    assert (result.fi.fi_month.scenario, result.fi.months_gained) == ("2041-10", 34)


async def test_cash_or_instalments_and_the_rate_they_cost_the_same(baseline):
    """can_i_afford's comparison. Paying cash takes the price out of cash,
    which earns nothing; the instalments take it out of the regular surplus,
    of which the placeholder invests all. So with the surplus invested at
    the placeholder 100%, paying cash ends ahead at every loan rate, 0%
    included: the instalments forgo what the money would have earned. With
    the share at 0 (as before it was an assumption), the break-even rate is
    0%: with no inflation set, paying later at any rate above it costs more."""
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
    # Was: a year on, net worth 2,489.49 lower (eleven payments made, 89.49
    # of the interest accrued); five years on, the price and all its interest
    # lower, 2,490.68. Surplus invested at the placeholder 100%: the loan's
    # money pays the price, so cash is as it was, and the twelve payments
    # (eleven of 207.55 from December, a last of 207.63 in November 2027)
    # are that much less invested each month. Five years on, the loan gone,
    # net worth is lower by what they would have grown to by 2031-10.
    schedule = [
        *[(m.month, Decimal("207.55")) for m in timelines.periods(dt.date(2026, 12, 1), 11)],
        ("2027-11", Decimal("207.63")),
    ]
    end = timelines.month_index("2031-10")
    forgone = sum((grown(p, end - timelines.month_index(m)) for m, p in schedule), Decimal(0))
    assert cents(forgone) == Decimal("2966.34")
    one_year, five_years = by_label["Instalments"].monthly[:2]
    assert cents(one_year.net_worth.delta) == Decimal("-2527.92")
    assert cents(five_years.net_worth.delta) == Decimal("-2966.34")
    assert cents(five_years.cash.delta) == 0
    # Paying cash: 2,400.00 out of cash, for good, and nothing else.
    assert cents(by_label["Pay cash"].monthly[1].net_worth.delta) == Decimal("-2400.00")
    # Was found at 0%. Even at 0% the instalments, twelve of 200.00, forgo
    # what they would have earned, so no rate from 0% to 100% leaves them
    # level with paying cash.
    (rate,) = result.break_evens
    assert (rate.kind, rate.option, rate.status, rate.value, rate.ahead) == (
        "loan_rate",
        "Instalments",
        "none_in_range",
        None,
        "Pay cash",
    )


async def test_cash_or_instalments_with_none_of_the_surplus_invested(cash_only):
    """Share 0: both come out of cash, which earns nothing; paying later
    costs exactly its interest, so the break-even rate is 0%, as before."""
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
    result = comparison.compare(cash_only, [cash, instalments])
    by_label = dict(zip(result.labels, result.options, strict=True))
    # A year on eleven payments are made and 89.49 of the interest has
    # accrued; five years on, net worth is the price and all its interest
    # lower: 2,400.00 + 90.68.
    one_year, five_years = by_label["Instalments"].monthly[:2]
    assert cents(one_year.net_worth.delta) == Decimal("-2489.49")
    assert cents(five_years.net_worth.delta) == Decimal("-2490.68")
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
    # stays with the household, twelve times in the year to 2027-10. Was:
    # 155.88 more cash at the year's end. Surplus invested at the placeholder
    # 100%, it is regular surplus, invested at each month's end: cash ends
    # the year as before, and the investments hold the twelve 12.99s with
    # what they earned, 158.77.
    (applied,) = result.changes
    assert applied.label == "Stop Streamflix" and applied.monthly == Decimal("12.99")
    assert result.cash.at_end.delta == 0
    assert cents(result.monthly[0].investments.delta) == cents(
        sum((grown(Decimal("12.99"), k) for k in range(12)), Decimal(0))
    )
    assert cents(result.monthly[0].investments.delta) == Decimal("158.77")
    # And it was spending, so the FI number falls by 12.99 × 12 over the
    # rate (was / 0.04 = 3,897).
    swr = baseline.assumptions.safe_withdrawal_rate.value
    assert cents(result.fi.fi_number.delta) == cents(Decimal("-155.88") / swr)


async def test_setting_part_of_the_surplus_aside(baseline, cash_only):
    """200.00 of each month's surplus kept in cash from November, for a year:
    with all of it invested (the placeholder), cash otherwise ends each month
    where it started; now it ends the year 12 × 200.00 higher, and the
    investments hold that much less, with what it would have earned."""
    aside = scenario(
        label="Emergency fund",
        changes=[
            {"type": "set_aside", "monthly": "200.00", "from": "2026-11-01", "to": "2027-10-31"}
        ],
    )
    result = engine.run(baseline, aside)
    (applied,) = result.changes
    assert (applied.label, applied.monthly, applied.for_good) == (
        "Set aside in cash",
        Decimal("200.00"),
        False,
    )
    assert result.cash.at_end.delta == Decimal("2400.00")  # 12 × 200.00
    assert cents(result.monthly[0].investments.delta) == -cents(
        sum((grown(Decimal(200), k) for k in range(12)), Decimal(0))
    )
    # What it costs a year on is only what the 2,400.00 would have earned:
    # 2,444.49 less invested, 2,400.00 more in cash.
    assert cents(result.monthly[0].net_worth.delta) == Decimal("-44.49")
    # It moves no money of its own, so the FI number doesn't change.
    assert result.fi.fi_number.delta == 0
    # When cash covers nine months of essential spending (9 × 1,898.32 =
    # 17,084.88): never as things are, in 2027-05 with the 200.00 (15,801.47
    # + 7 × 200.00 = 17,201.47; six months is 17,001.47, short).
    base = engine.baseline_outlook(baseline)
    _, done = engine.run_with_outlook(baseline, aside, base=base)
    cover = engine.cover_target(baseline, base, done.outlook, Decimal(9))
    assert (cover.monthly_spending, cover.target) == (Decimal("1898.32"), Decimal("17084.88"))
    assert cents(cover.now or Decimal(0)) == Decimal("8.32")  # 15,801.47 / 1,898.32
    assert (cover.reached.baseline, cover.reached.scenario, cover.months) == (
        None,
        "2027-05",
        (None, 7),
    )

    # With none of the surplus invested, all of it stays in cash anyway: a
    # set-aside changes nothing.
    kept = engine.run(cash_only, aside)
    assert kept.cash.at_end.delta == 0 and kept.monthly[-1].net_worth.delta == 0


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
