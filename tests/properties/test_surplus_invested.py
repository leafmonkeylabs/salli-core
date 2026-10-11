"""
Properties of the share of each month's regular surplus invested
(`surplus_invested`, domain/baseline/timelines.py), over random ledgers (the
baseline's own, tests/properties/test_baseline.py) and random changes:

- at 0, the whole regular surplus stays in cash, as it did before the share
  was an assumption: cash is the cash-only plan's month by month, on both
  timelines, and the investments hold only what they held and what is moved
  into them;
- raising the share never lowers net worth, at the horizon or at any month
  before it, while the real return is at least zero (the ledgers' inflation,
  when set, is too): it only moves money from cash, which earns nothing, to
  where it earns that return;
- a scenario with no changes is the baseline, whatever the share;
- a debt's scheduled payments, freed once an extra payment clears it, join
  the regular surplus and are shared out at the share like the rest of it.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from decimal import ROUND_HALF_UP, ROUND_UP, Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salli.domain.baseline import Baseline, timelines
from salli.domain.currency import quantum
from salli.domain.fi.assumptions import Applied
from salli.domain.scenarios import engine, schema
from tests.baseline_ledger import Ledger
from tests.properties.test_baseline import AS_OF, SHARES, ledgers
from tests.properties.test_scenarios import _day, money_changes

_SETTINGS = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])

#: Real returns of at least zero, to the basis point, up to the plausible 15%.
returns = st.integers(min_value=0, max_value=1500).map(lambda bp: Decimal(bp) / 10000)
years = st.integers(min_value=1, max_value=30)


def with_share(baseline: Baseline, share: str) -> Baseline:
    """`baseline` with the user's own share of the surplus invested."""
    applied = Applied(Decimal(share), "user", "test")
    return replace(baseline, assumptions=replace(baseline.assumptions, surplus_invested=applied))


@st.composite
def changes(draw: st.DrawFn) -> list[dict]:
    """Costs and income, one-off and regular, money invested, a loan: none
    that names a debt, which a random ledger may not have."""
    out = draw(st.lists(st.one_of(money_changes(-1), money_changes(+1)), max_size=3))
    if draw(st.booleans()):
        out.append(
            {
                "type": "invest",
                "amount": f"{draw(st.integers(1, 20000))}.00",
                "date": _day(draw(st.integers(0, 400))),
                "label": "Invest",
            }
        )
    if draw(st.booleans()):
        out.append(
            {
                "type": "loan",
                "principal": f"{draw(st.integers(100, 50000))}.00",
                "annual_rate": draw(st.sampled_from(["0", "0.049", "0.12"])),
                "term_months": draw(st.integers(1, 120)),
                "start": _day(draw(st.integers(0, 400))),
                "label": "Loan",
            }
        )
    return out


def _translated(baseline: Baseline, docs: list[dict], horizon: int) -> timelines.Changes:
    months = timelines.periods(AS_OF, timelines.horizon_months(horizon))
    scenario = schema.load({"schema": "salli.scenario/1", "changes": docs})
    return engine.translate(baseline, scenario, until=months[-1].end).changes


def _money(value: Decimal, currency: str) -> Decimal:
    return value.quantize(quantum(currency), rounding=ROUND_HALF_UP)


@_SETTINGS
@given(ledgers(), changes(), years)
def test_with_none_invested_the_regular_surplus_stays_in_cash(
    books: Ledger, docs: list[dict], horizon: int
):
    baseline = with_share(books.baseline(AS_OF), "0")
    added = _translated(baseline, docs, horizon)
    months = timelines.periods(AS_OF, timelines.horizon_months(horizon))
    paths = timelines.debt_paths(baseline, months, added)
    plan = timelines.cash_plan(baseline, months, paths, added)
    assert all(m.invested == 0 for m in plan)

    # The cash-only plan, written out: each full month, the surplus (with
    # what of the debts' payments it already pays) in its own money, less
    # all the debts are paid (their schedules and any extra), plus every
    # change's cash flow; the as-of month's rest of the month as the plan
    # has it. Money moved into the investments grows there, and nothing
    # else joins them.
    currency = baseline.currency
    first = AS_OF.isoformat()
    flows: dict[str, Decimal] = defaultdict(Decimal)
    for flow in added.cash_flows:
        assert flow.currency == currency
        if flow.date >= first:
            flows[flow.date[:7]] += flow.amount
    moved: dict[str, Decimal] = defaultdict(Decimal)
    for day, amount in added.invested:
        moved[day[:7]] += amount
    already = sum((p.debt.already_paid for p in paths), Decimal(0))
    surplus = baseline.flows.surplus
    rate = baseline.assumptions.real_returns.base

    timeline = timelines.monthly(baseline, horizon, added)
    cash, invested = baseline.cash, baseline.investments
    own_money: list[Decimal] = []
    for i, (month, point) in enumerate(zip(plan, timeline.points[1:], strict=True)):
        p = month.period
        if i == 0:
            change = month.planned
        else:
            paid = sum((path.payments[i] for path in paths), Decimal(0))
            change = _money((surplus + already) * month.deflator - paid, currency)
        cash += change + flows.get(p.month, Decimal(0))
        invested = invested * (1 + rate / 12 * p.share) + moved.get(p.month, Decimal(0)) / (
            month.deflator
        )
        own_money.append(cash)
        assert point.cash == cash / month.deflator
        assert point.investments == invested

    # The daily timeline ends each month there too.
    daily = timelines.daily(baseline, added)
    assert [v for _, v in daily.month_ends] == own_money[: timelines.DAILY_MONTHS]


@_SETTINGS
@given(ledgers(), changes(), st.sampled_from(SHARES), st.sampled_from(SHARES), returns, years)
def test_raising_the_share_never_lowers_net_worth(
    books: Ledger, docs: list[dict], a: str, b: str, rate: Decimal, horizon: int
):
    baseline = books.baseline(AS_OF)
    lower, higher = sorted((a, b), key=Decimal)
    added = _translated(baseline, docs, horizon)
    less = timelines.monthly(with_share(baseline, lower), horizon, added, real_return=rate)
    more = timelines.monthly(with_share(baseline, higher), horizon, added, real_return=rate)
    # Every point, the horizon's among them, to Decimal's last digits (each
    # side deflates its own sum once).
    for x, y in zip(less.points, more.points, strict=True):
        assert y.net_worth >= x.net_worth - Decimal("1e-15")
        # What is invested only ever grows with the share; cash only ever
        # shrinks with it.
        assert y.investments >= x.investments
        assert y.cash <= x.cash


@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(ledgers())
def test_a_scenario_with_no_changes_is_the_baseline_at_every_share(books: Ledger):
    built = books.baseline(AS_OF)
    empty = schema.load({"schema": "salli.scenario/1", "changes": []})
    for share in SHARES:
        result = engine.run(with_share(built, share), empty)
        figures = [
            result.cash.lowest,
            result.cash.at_end,
            *(f for p in result.monthly for f in (p.net_worth, p.cash, p.investments, p.debts)),
        ]
        assert all(f.baseline == f.scenario for f in figures)
        assert result.fi.fi_month.baseline == result.fi.fi_month.scenario
        assert result.fi.months_gained in (0, None)


@_SETTINGS
@given(ledgers(), st.sampled_from(SHARES), years, st.data())
def test_freed_debt_payments_follow_the_share(
    books: Ledger, share: str, horizon: int, data: st.DataObject
):
    if data.draw(st.booleans()) or not books.uow.debts.rows:
        books.debt("extra", str(data.draw(st.integers(500, 30000))), "0.045", "300")
    baseline = with_share(books.baseline(AS_OF), share)
    currency = baseline.currency
    unit = quantum(currency)
    months = timelines.periods(AS_OF, timelines.horizon_months(horizon))
    first = months[1].month
    as_is = timelines.debt_paths(baseline, months)
    before = timelines.cash_plan(baseline, months, as_is)
    for debt in (d for d in baseline.debts if d.balance > 0):
        # A lump big enough to clear it in its first payment month.
        lump = (debt.balance * 2).quantize(unit, rounding=ROUND_UP)
        cleared = timelines.Changes(
            extra=(timelines.ExtraPayment(debt.debt_id, first, first, lump),)
        )
        paths = timelines.debt_paths(baseline, months, cleared)
        after = timelines.cash_plan(baseline, months, paths, cleared)
        (gone,) = [p for p in paths if p.debt.debt_id == debt.debt_id]
        assert gone.paid_off == first
        for i in range(len(months)):
            freed = sum((p.scheduled[i] for p in as_is), Decimal(0)) - sum(
                (p.scheduled[i] for p in paths), Decimal(0)
            )
            assert freed >= 0
            # Freed payments join the regular surplus, exactly.
            assert after[i].regular - before[i].regular == freed
            # And are shared out like the rest of it: the share into the
            # investments (to the currency's smallest unit), the rest kept.
            if before[i].regular >= 0:
                more = after[i].invested - before[i].invested
                assert abs(more - Decimal(share) * freed) <= unit
                # The rest stays in cash; the lump itself came out of cash.
                lump_out = after[i].extra - before[i].extra
                assert after[i].cash_change - before[i].cash_change == freed - more - lump_out
        # Every month after the lump that the debt would still have been
        # paid, its whole scheduled payment is freed.
        (still,) = [p for p in as_is if p.debt.debt_id == debt.debt_id]
        for i in range(2, len(months)):
            assert after[i].regular - before[i].regular == still.scheduled[i]
