"""
The baseline's two timelines. Pure, deterministic, Decimal; no model.

**The monthly cash plan** is what both read. In each full calendar month
after the as-of month, cash changes by:

- the average monthly surplus (`Flows.surplus`), held level in today's money
  (so it grows with inflation in each month's own money);
- plus what of the debts' payments the surplus already pays
  (`BaselineDebt.already_paid`), less what the debts are paid that month: a
  debt paid more than that takes the difference from cash, and once a debt
  is paid off its payment stays in cash. A debt's first payment falls in the
  month after the as-of month;
- plus any changes added (a scenario's), in the month they fall.

The as-of month is already partly over: in the rest of it, cash changes by
what is scheduled for it, and by its share of days of what an average month
does beyond its schedule. Not by its share of the whole surplus: a salary
still to come this month is not a share of one.

The surplus goes to cash: it is not assumed invested (a regular transfer to
an investment account shows on its day in the daily timeline, and the rest
of the month returns it). That is the same contribution FI's projection
counts, and a scenario that invests it says so.

**The daily cash timeline** (`daily`) runs from the as-of date to the end of
the twelfth month after it, in each day's own money: the cash accounts'
balances carried through what keeps happening (the cash forecast's flows),
the changes added, and the rest of each month's plan, spread evenly over its
days, so each month ends exactly where the plan says. `forecast` is the same
without that rest: the cash forecast and safe-to-spend show only what is
scheduled.

**The monthly timeline** (`monthly`) runs to a horizon of up to 50 years, at
each calendar month's end, in today's money:

- cash, from the plan, earning nothing: in today's money it loses what
  inflation takes;
- investments, growing at the base scenario's real return (a twelfth of it
  a month, compounded, as FI does);
- other assets, keeping their value in today's money;
- debts, on their calendar-month schedules (fixed payments, in each month's
  own money), and liabilities without terms, held as they are;
- net worth: all of them together.

Each month's own money is deflated by the user's inflation (a twelfth of it a
month, compounded). With none set, nominal amounts keep their real value,
and the baseline says so among its placeholders. The daily timeline's
month-ends are the monthly timeline's cash in each month's own money: the
same figure, before deflating.

**Changes** (`Changes`, a scenario's) add to both timelines: cash flows on
their days (forecast `Flow`s, in their day's own money), money moved into
investments (which then grow with them), loans taken out (owed from the
month they are taken out, paid from the month after, their last payment
clearing them), and extra payments on a debt for a run of months. A plain
sequence of flows is changes of cash alone. The as-of point is always the
baseline's own: changes start after it.

`safe_to_spend` is the cash forecast's answer to "how much could go out
today": the lowest the scheduled cash gets before money next comes in.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from salli.domain.baseline.models import Baseline, BaselineDebt
from salli.domain.currency import quantum
from salli.domain.debt import engine as debt_engine
from salli.domain.debt.models import Debt, PayoffScheduleEntry
from salli.domain.reports import forecast as forecasting

#: The longest horizon, in years.
MAX_HORIZON_YEARS = 50
#: The daily timeline covers the as-of month and the twelve after it.
DAILY_MONTHS = 13

_TWELVE = Decimal(12)


@dataclass(frozen=True)
class Period:
    """One calendar month of a timeline."""

    #: "YYYY-MM".
    month: str
    #: Its first day within the timeline (the as-of date, for the first) and its last.
    start: dt.date
    end: dt.date
    #: The part of the month within the timeline: 1, except the as-of month.
    share: Decimal


# ── Changes ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExtraPayment:
    """Paid on a debt on top of its minimum, each month from `start` to `end`
    ("YYYY-MM", inclusive; None: until it is paid off), in each month's own
    money. Debts are paid from the month after the as-of month, so an extra
    payment starts no sooner."""

    debt_id: str
    start: str
    end: str | None
    amount: Decimal


@dataclass(frozen=True)
class Changes:
    """What a scenario adds to the baseline's timelines."""

    #: Cash flows on their days, in their day's own money (source "change").
    flows: tuple[forecasting.Flow, ...] = ()
    #: Money moved into investments: (date, amount in the base currency, in
    #: that day's own money). Its cash side is one of `flows`.
    invested: tuple[tuple[str, Decimal], ...] = ()
    #: Loans taken out (`BaselineDebt.source` "scenario"). The money borrowed
    #: arrives as one of `flows`.
    loans: tuple[BaselineDebt, ...] = ()
    #: Extra payments on the baseline's debts (or on a loan above).
    extra: tuple[ExtraPayment, ...] = ()


NO_CHANGES = Changes()


def as_changes(changes: Changes | Sequence[forecasting.Flow]) -> Changes:
    """`changes` as `Changes`: a plain sequence of flows is cash flows alone."""
    return changes if isinstance(changes, Changes) else Changes(flows=tuple(changes))


def month_index(month: str) -> int:
    """A calendar month ("YYYY-MM") as a count of months, to subtract."""
    return int(month[:4]) * 12 + int(month[5:7]) - 1


def periods(as_of: dt.date, count: int) -> list[Period]:
    """`count` calendar months from the as-of month."""
    out: list[Period] = []
    for i in range(count):
        index = as_of.year * 12 + as_of.month - 1 + i
        year, month = index // 12, index % 12 + 1
        days = calendar.monthrange(year, month)[1]
        first = dt.date(year, month, 1)
        start = max(first, as_of)
        end = dt.date(year, month, days)
        share = Decimal((end - start).days + 1) / Decimal(days) if i == 0 else Decimal(1)
        out.append(Period(f"{year:04d}-{month:02d}", start, end, share))
    return out


def deflators(baseline: Baseline, months: Sequence[Period]) -> list[Decimal]:
    """Each month's end in today's money: divide its own money by this. All
    ones when the user set no inflation."""
    inflation = baseline.inflation or Decimal(0)
    out: list[Decimal] = []
    level = Decimal(1)
    for p in months:
        level *= Decimal(1) + inflation / _TWELVE * p.share
        out.append(level)
    return out


# ── Debts on calendar months ─────────────────────────────────────────────────


@dataclass(frozen=True)
class DebtPath:
    """A debt's schedule on the timeline's months, in each month's own money."""

    debt: BaselineDebt
    #: What it is paid in each month of the timeline (nothing in the as-of month).
    payments: tuple[Decimal, ...]
    #: What it owes at each month's end.
    owed: tuple[Decimal, ...]
    schedule: tuple[PayoffScheduleEntry, ...]
    #: The calendar month of its last payment; None when not paid off within
    #: the timeline (or nothing is owed).
    paid_off: str | None
    total_interest: Decimal


def _extra_for(
    d: BaselineDebt, extras: Sequence[ExtraPayment], first: str
) -> Decimal | Callable[[int], Decimal]:
    """What is paid on `d` beyond its minimum in its plan's month m (1 is the
    month `first`): its own constant extra, and the extra payments named for
    it in the months they run."""
    mine = [x for x in extras if x.debt_id == d.debt_id]
    if not mine:
        return d.extra_payment

    def extra(m: int) -> Decimal:
        month = debt_engine.month_after(first, m - 1)
        return d.extra_payment + sum(
            (x.amount for x in mine if x.start <= month and (x.end is None or month <= x.end)),
            Decimal(0),
        )

    return extra


def debt_paths(
    baseline: Baseline,
    months: Sequence[Period],
    changes: Changes | Sequence[forecasting.Flow] = NO_CHANGES,
) -> list[DebtPath]:
    """Each debt amortised on its own terms (minimum plus any extra), its
    first payment in the month after the as-of month; then each loan the
    changes take out, owed from the month it is taken out and paid from its
    first payment's month, its last payment clearing it."""
    added = as_changes(changes)
    paths: list[DebtPath] = []
    count = len(months)
    start = month_index(months[0].month)
    for d in (*baseline.debts, *added.loans):
        opened = 0 if d.opened is None else month_index(d.opened) - start
        first = 1 if d.first_payment is None else max(month_index(d.first_payment) - start, 1)
        payments = [Decimal(0)] * count
        owed = [Decimal(0) if i < opened else d.balance for i in range(count)]
        schedule: list[PayoffScheduleEntry] = []
        paid_off: str | None = None
        interest = Decimal(0)
        if d.balance > 0 and opened < count and first < count:
            plan = debt_engine.compute_payoff_plan(
                [
                    Debt(
                        d.name,
                        d.balance,
                        d.apr,
                        d.minimum_payment,
                        id=d.debt_id,
                        term_months=d.term_months,
                    )
                ],
                _extra_for(d, added.extra, months[first].month),
                "avalanche",
                max_months=count - first,
                money_quantum=quantum(baseline.currency),
                first_month=months[first].month,
            )
            schedule = plan.schedule
            interest = plan.total_interest_paid
            paid_off = plan.debt_free_period
            for e in schedule:
                payments[first - 1 + e.month] = e.payment
            remaining = d.balance
            by_index = {first - 1 + e.month: e.remaining_balance for e in schedule}
            for i in range(first, count):
                remaining = by_index.get(i, Decimal(0) if paid_off else remaining)
                owed[i] = remaining
        paths.append(DebtPath(d, tuple(payments), tuple(owed), tuple(schedule), paid_off, interest))
    return paths


# ── The monthly cash plan ────────────────────────────────────────────────────


@dataclass(frozen=True)
class MonthPlan:
    period: Period
    #: Today's money at the month's end: divide its own money by this.
    deflator: Decimal
    #: In the month's own money: the surplus (with what the debts' payments
    #: it already pays), less the debts' payments that month.
    planned: Decimal
    #: The changes added in the month, in the base currency.
    changes: Decimal

    @property
    def cash_change(self) -> Decimal:
        return self.planned + self.changes


def _in_base(baseline: Baseline, flow: forecasting.Flow) -> Decimal | None:
    if flow.currency == baseline.currency:
        return flow.amount
    rate = next((r.rate for r in baseline.rates if r.currency == flow.currency), None)
    return None if rate is None else flow.amount * rate


def scheduled_net(baseline: Baseline, months: Sequence[Period]) -> dict[str, Decimal]:
    """What the scheduled flows move the cash total by in each of the daily
    timeline's months, at the as-of rates."""
    window = months[:DAILY_MONTHS]
    net: dict[str, Decimal] = defaultdict(Decimal)
    for flow in scheduled_flows(baseline, baseline.as_of, window[-1].end):
        value = _in_base(baseline, flow)
        if value is not None:
            net[flow.date[:7]] += value
    return net


def cash_plan(
    baseline: Baseline,
    months: Sequence[Period],
    paths: Sequence[DebtPath],
    changes: Changes | Sequence[forecasting.Flow] = NO_CHANGES,
) -> list[MonthPlan]:
    """The cash plan for `months` (the as-of month first, at least the daily
    timeline's thirteen).

    A full month: the surplus (with what of the debts' payments it already
    pays), in that month's money, less the debts' payments. The as-of month:
    what is scheduled for the rest of it, and its share of what an average
    month's surplus is beyond its schedule (averaged over the daily
    timeline's twelve full months). Not its share of the whole surplus: a
    salary still to come this month is not a share of one. Debts are paid
    from the next month on, so they don't touch it.

    Every month's amount is rounded to the currency's smallest unit, so the
    daily timeline, which spreads it over the days, sums to it exactly."""
    currency = baseline.currency
    surplus = baseline.flows.surplus
    already = sum((p.debt.already_paid for p in paths), Decimal(0))
    added: dict[str, Decimal] = defaultdict(Decimal)
    first = months[0].start.isoformat()
    for flow in as_changes(changes).flows:
        value = _in_base(baseline, flow)
        if value is not None and flow.date >= first:
            added[flow.date[:7]] += value

    levels = deflators(baseline, months)
    full: list[Decimal] = [Decimal(0)]
    for i in range(1, len(months)):
        paid = sum((path.payments[i] for path in paths), Decimal(0))
        full.append(_money((surplus + already) * levels[i] - paid, currency))

    net = scheduled_net(baseline, months)
    rests = [
        surplus * levels[i] - net.get(months[i].month, Decimal(0)) for i in range(1, DAILY_MONTHS)
    ]
    average_rest = sum(rests, Decimal(0)) / Decimal(len(rests))
    full[0] = _money(
        net.get(months[0].month, Decimal(0)) + average_rest * months[0].share, currency
    )

    return [
        MonthPlan(p, level, planned, added.get(p.month, Decimal(0)))
        for p, level, planned in zip(months, levels, full, strict=True)
    ]


def _money(value: Decimal, currency: str) -> Decimal:
    return value.quantize(quantum(currency), rounding=ROUND_HALF_UP)


# ── The daily cash timeline ──────────────────────────────────────────────────


@dataclass(frozen=True)
class CashTimeline:
    """Cash day by day, in each day's own money."""

    forecast: forecasting.Forecast
    #: The cash at each month's end ("YYYY-MM" → amount).
    month_ends: tuple[tuple[str, Decimal], ...]
    #: The rest of each month's plan, beyond what is scheduled.
    unscheduled: tuple[tuple[str, Decimal], ...]
    notes: tuple[str, ...] = field(default_factory=tuple)


def to_base(baseline: Baseline) -> dict[str, Decimal]:
    return {r.currency: r.rate for r in baseline.rates if r.rate is not None}


def scheduled_flows(
    baseline: Baseline, start: dt.date, end: dt.date, notes: list[str] | None = None
) -> list[forecasting.Flow]:
    """What keeps happening on the cash accounts from `start` to `end`: the
    rhythms in the ledger, and the declared subscriptions none of them shows."""
    cash = {account_id: currency for account_id, (currency, _) in baseline.cash_accounts.items()}
    return [
        *forecasting.recurring_flows(baseline.recurring, cash, start, end, notes),
        *forecasting.declared_flows(baseline.charges, baseline.currency, start, end),
    ]


def _within(flows: Sequence[forecasting.Flow], end: dt.date) -> list[forecasting.Flow]:
    last = end.isoformat()
    return [f for f in flows if f.date <= last]


def forecast(
    baseline: Baseline,
    end: dt.date,
    changes: Changes | Sequence[forecasting.Flow] = NO_CHANGES,
) -> tuple[forecasting.Forecast, list[str]]:
    """The cash forecast: only what is scheduled (and the changes' cash
    flows), from the as-of date to `end`, the total at the as-of rates."""
    notes: list[str] = []
    flows = [
        *scheduled_flows(baseline, baseline.as_of, end, notes),
        *_within(as_changes(changes).flows, end),
    ]
    result = forecasting.project(
        baseline.cash_accounts, flows, to_base(baseline), baseline.currency, baseline.as_of, end
    )
    return result, notes


def _spread(
    amount: Decimal, days: Sequence[dt.date], currency: str
) -> list[tuple[dt.date, Decimal]]:
    """`amount` over `days`, as evenly as the currency's smallest unit
    allows, summing to it exactly (the last day takes any fraction of a unit
    the rates leave)."""
    n = len(days)
    out: list[tuple[dt.date, Decimal]] = []
    before = Decimal(0)
    for j, day in enumerate(days, start=1):
        upto = amount if j == n else _money(amount * Decimal(j) / Decimal(n), currency)
        out.append((day, upto - before))
        before = upto
    return out


def daily(
    baseline: Baseline, changes: Changes | Sequence[forecasting.Flow] = NO_CHANGES
) -> CashTimeline:
    added = as_changes(changes)
    months = periods(baseline.as_of, DAILY_MONTHS)
    end = months[-1].end
    flows = _within(added.flows, end)
    paths = debt_paths(baseline, months, added)
    plan = cash_plan(baseline, months, paths, flows)
    notes: list[str] = []
    scheduled = scheduled_flows(baseline, baseline.as_of, end, notes)
    net = scheduled_net(baseline, months)

    rest: list[forecasting.Flow] = []
    unscheduled: list[tuple[str, Decimal]] = []
    for month in plan:
        p = month.period
        remainder = month.planned - net.get(p.month, Decimal(0))
        unscheduled.append((p.month, remainder))
        days = [p.start + dt.timedelta(days=k) for k in range((p.end - p.start).days + 1)]
        for day, amount in _spread(remainder, days, baseline.currency):
            if amount:
                rest.append(
                    forecasting.Flow(
                        day.isoformat(),
                        None,
                        amount,
                        baseline.currency,
                        "The rest of an average month",
                        "average",
                    )
                )

    result = forecasting.project(
        baseline.cash_accounts,
        [*scheduled, *flows, *rest],
        to_base(baseline),
        baseline.currency,
        baseline.as_of,
        end,
    )
    by_day = dict(result.daily)
    month_ends = tuple((m.period.month, by_day[m.period.end.isoformat()]) for m in plan)
    return CashTimeline(result, month_ends, tuple(unscheduled), tuple(dict.fromkeys(notes)))


# ── The monthly timeline ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class MonthPoint:
    """Where things stand at a month's end, in today's money."""

    #: "YYYY-MM"; the as-of point is its month too.
    month: str
    #: The as-of date for the first point, then each month's last day.
    date: str
    cash: Decimal
    investments: Decimal
    other_assets: Decimal
    debts: Decimal
    other_liabilities: Decimal
    net_worth: Decimal
    #: Divide the month's own money by this to get today's money.
    deflator: Decimal


@dataclass(frozen=True)
class DebtOutlook:
    debt_id: str
    name: str
    #: The calendar month of its last payment; None when not paid off within
    #: the horizon (or nothing is owed).
    paid_off: str | None
    total_interest: Decimal
    schedule: tuple[PayoffScheduleEntry, ...]


@dataclass(frozen=True)
class MonthlyTimeline:
    points: tuple[MonthPoint, ...]
    debts: tuple[DebtOutlook, ...]
    #: The month the last debt is paid off; None when one isn't within the
    #: horizon. With no debts, None too.
    debt_free: str | None
    #: The base scenario's real return the investments grow at.
    real_return: Decimal


def horizon_months(horizon_years: int) -> int:
    """The calendar months a horizon of `horizon_years` covers: the as-of
    month and the 12 × years after it."""
    if not 1 <= horizon_years <= MAX_HORIZON_YEARS:
        raise ValueError(f"A horizon is from 1 to {MAX_HORIZON_YEARS} years, not {horizon_years}")
    return horizon_years * 12 + 1


def monthly(
    baseline: Baseline,
    horizon_years: int,
    changes: Changes | Sequence[forecasting.Flow] = NO_CHANGES,
    *,
    real_return: Decimal | None = None,
) -> MonthlyTimeline:
    """The monthly timeline to `horizon_years`, with `changes` added; the
    investments grow at `real_return` (the base scenario's when None)."""
    added = as_changes(changes)
    months = periods(baseline.as_of, horizon_months(horizon_years))
    paths = debt_paths(baseline, months, added)
    plan = cash_plan(baseline, months, paths, added)
    real_return = baseline.assumptions.real_returns.base if real_return is None else real_return
    invested: dict[str, Decimal] = defaultdict(Decimal)
    first = baseline.as_of.isoformat()
    for day, amount in added.invested:
        if day >= first:
            invested[day[:7]] += amount

    cash = baseline.cash
    investments = baseline.investments
    other_assets = baseline.other_assets
    other_liabilities = baseline.other_liabilities
    points = [
        MonthPoint(
            month=baseline.as_of.isoformat()[:7],
            date=baseline.as_of.isoformat(),
            cash=cash,
            investments=investments,
            other_assets=other_assets,
            debts=baseline.debts_owed,
            other_liabilities=other_liabilities,
            net_worth=cash + investments + other_assets - baseline.debts_owed - other_liabilities,
            deflator=Decimal(1),
        )
    ]
    for i, month in enumerate(plan):
        cash += month.cash_change
        level = month.deflator
        investments *= Decimal(1) + real_return / _TWELVE * month.period.share
        # Money moved in during a month grows from the next, in today's money.
        investments += invested.get(month.period.month, Decimal(0)) / level
        owed = sum((path.owed[i] for path in paths), Decimal(0))
        points.append(
            MonthPoint(
                month=month.period.month,
                date=month.period.end.isoformat(),
                cash=cash / level,
                investments=investments,
                other_assets=other_assets,
                debts=owed / level,
                other_liabilities=other_liabilities / level,
                # What is held in money, deflated once, so the same money
                # moved between cash and a debt changes it by nothing.
                net_worth=(cash - owed - other_liabilities) / level + investments + other_assets,
                deflator=level,
            )
        )

    outlooks = tuple(
        DebtOutlook(p.debt.debt_id, p.debt.name, p.paid_off, p.total_interest, p.schedule)
        for p in paths
    )
    owing = [p for p in paths if p.debt.balance > 0]
    debt_free = (
        max(p.paid_off for p in owing if p.paid_off)
        if owing and all(p.paid_off for p in owing)
        else None
    )
    return MonthlyTimeline(tuple(points), outlooks, debt_free, real_return)


# ── Safe to spend ────────────────────────────────────────────────────────────

#: How far ahead safe-to-spend looks for the next income, and the window it
#: takes when the ledger expects none.
SAFE_LOOKAHEAD_DAYS = 45
SAFE_WINDOW_DAYS = 30


@dataclass(frozen=True)
class SafeToSpend:
    """How much could go out on the as-of date without the scheduled cash
    dropping below zero before money next comes in."""

    #: The lowest the cash total gets until `until`, never below zero.
    amount: Decimal
    cash_today: Decimal
    #: The next income's day, or 30 days on when the ledger expects none.
    until: str
    next_income: forecasting.Flow | None
    #: What goes out before then. Money moved between two cash accounts is
    #: neither income nor committed: it never leaves cash.
    committed: tuple[forecasting.Flow, ...]
    forecast: forecasting.Forecast
    notes: tuple[str, ...] = ()


def safe_to_spend(
    baseline: Baseline, changes: Changes | Sequence[forecasting.Flow] = NO_CHANGES
) -> SafeToSpend:
    """Safe-to-spend from the cash forecast (what is scheduled, and the
    changes' cash flows): the lowest the total gets from the as-of date until
    the day before the next income the ledger expects (a change's money in is
    not one, so a scenario is measured over the baseline's window), or over
    30 days when it expects none; never below zero."""
    as_of = baseline.as_of
    result, notes = forecast(baseline, as_of + dt.timedelta(days=SAFE_LOOKAHEAD_DAYS), changes)
    today = as_of.isoformat()
    income = next(
        (
            f
            for f in result.flows
            if f.amount > 0 and f.source == "recurring" and not f.transfer and f.date > today
        ),
        None,
    )
    until = income.date if income else (as_of + dt.timedelta(days=SAFE_WINDOW_DAYS)).isoformat()
    window = [v for d, v in result.daily if d < until] or [result.today]
    committed = tuple(f for f in result.flows if f.amount < 0 and not f.transfer and f.date < until)
    return SafeToSpend(
        amount=max(min(window), Decimal(0)),
        cash_today=result.today,
        until=until,
        next_income=income,
        committed=committed,
        forecast=result,
        notes=tuple(dict.fromkeys(notes)),
    )
