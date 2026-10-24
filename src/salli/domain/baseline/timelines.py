"""
The baseline's two timelines. Pure, deterministic, Decimal; no model.

**The monthly cash plan** (`cash_plan`) is what both read. Each month's money
comes in two kinds, and only the first is shared out:

- **The regular surplus**: what happens month after month. In each full
  calendar month after the as-of month: the average monthly surplus
  (`Flows.surplus`), held level in today's money (so it grows with inflation
  in each month's own money), plus what of the debts' payments the surplus
  already pays (`BaselineDebt.already_paid`), less the debts' scheduled
  payments that month. So once a debt or a scenario's loan is paid off, its
  payment is freed and joins the regular surplus, whether its schedule ran
  out or an extra payment cleared it early. A debt's first payment falls in
  the month after the as-of month (a scenario's loan's, the month after it
  is taken out). A scenario's regular changes add to it in
  the month they fall: recurring costs and income, income changes, stopped
  flows (`Changes.regular`).
- **Moves**, which go where they say: one-offs and the money a loan brings
  in, in or out of cash (`Changes.flows`); money moved into investments, out
  of cash and into them (`Changes.invested`); and payments on a debt beyond
  its schedule, out of cash and onto the debt (`Changes.extra`,
  `BaselineDebt.extra_payment`). A scenario's extra payment in the month
  before a debt's first payment (the as-of month; a loan's opening month)
  is paid at that month's end, up to what is owed, before the schedule
  starts (`debt_paths`).

The share invested (`Baseline.surplus_invested`, an FI assumption: the
user's, or the placeholder of all of it) of a month's regular surplus moves
into investments at the month's end, rounded to the currency's smallest
unit, and grows at the real return from the next month; the rest stays in
cash, which earns nothing. A scenario may set an amount aside first
(`Changes.kept`): that much of the month's regular surplus stays in cash,
and the share invested is of what is left (none of it, when the amount set
aside is the whole surplus or more). A month whose regular surplus is a deficit
invests nothing: the deficit is drawn from cash, never from investments, and
if cash runs out it is left below zero (the monthly timeline's `notes` say
from when) rather than investments being sold. A share of 0 keeps the whole
surplus in cash; 1, the placeholder, invests all of it, as FI projections
conventionally do.

The as-of month is already partly over: in the rest of it, the regular
surplus is what is scheduled for it, and its share of days of what an
average month does beyond its schedule. Not its share of the whole surplus:
a salary still to come this month is not a share of one. It is shared out
like any other month's.

A regular transfer to an investment account, which the ledger shows, is no
part of the surplus: it shows on its day in the daily timeline, and the rest
of the month returns it. What is invested is the share.

**The daily cash timeline** (`daily`) runs from the as-of date to the end of
the twelfth month after it, in each day's own money: the cash accounts'
balances carried through what keeps happening (the cash forecast's flows),
the changes added, the rest of each month's plan, spread evenly over its
days, and the share invested, leaving cash on the month's last day. So each
month ends exactly where the plan says, and the lowest point reflects what
was invested. `forecast` is the same without the plan: the cash forecast and
safe-to-spend show only what is scheduled.

**The monthly timeline** (`monthly`) runs to a horizon of up to 50 years, at
each calendar month's end, in today's money:

- cash, from the plan, earning nothing: in today's money it loses what
  inflation takes;
- investments, growing at the base scenario's real return (a twelfth of it
  a month, compounded, as FI does); what moves into them in a month (the
  share of the regular surplus, or a scenario's investment) grows from the
  next;
- other assets: the baseline's keep their value in today's money; an asset
  a scenario buys (`Changes.assets`) is counted from the end of the month
  it is bought, at its price in today's money, and grows at its own real
  growth (a twelfth of it a month, compounded) from the next. It counts at
  what it would fetch, its value less its selling costs (`other_assets`);
  `other_assets_value` is the same before selling costs;
- debts, on their calendar-month schedules (fixed payments, in each month's
  own money), and liabilities without terms, held as they are;
- net worth: all of them together.

Each month's own money is deflated by the user's inflation (a twelfth of it a
month, compounded). With none set, nominal amounts keep their real value,
and the baseline says so among its placeholders. The daily timeline's
month-ends are the monthly timeline's cash in each month's own money: the
same figure, before deflating.

**Changes** (`Changes`, a scenario's) add to both timelines: cash flows on
their days (forecast `Flow`s, in their day's own money; regular ones apart
from moves), money moved into investments (which then grow with them),
assets bought (their price is one of the moves), loans
taken out (owed from the month they are taken out, paid from the month
after, their last payment clearing them), and extra payments on a debt for a
run of months (from the as-of month, or a loan's opening month, on). A plain
sequence of flows is moves of cash alone. The as-of point is always the
baseline's own: changes start after it.

`safe_to_spend` is the cash forecast's answer to "how much could go out
today": the lowest the scheduled cash gets before money next comes in.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
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
    money. In the month before the debt's first payment (the as-of month, or
    a loan's opening month) it is paid at the month's end, before the
    schedule starts (`debt_paths`)."""

    debt_id: str
    start: str
    end: str | None
    amount: Decimal


@dataclass(frozen=True)
class KeptInCash:
    """Kept in cash out of the regular surplus each month from `start` to
    `end` ("YYYY-MM", inclusive; None: for good), before the share invested
    is taken from the rest, in each month's own money."""

    start: str
    end: str | None
    amount: Decimal

    def in_month(self, month: str) -> Decimal:
        return (
            self.amount
            if self.start <= month and (self.end is None or month <= self.end)
            else Decimal(0)
        )


@dataclass(frozen=True)
class Asset:
    """Something a scenario buys that holds value (an `asset` change): its
    price leaves cash on `date` (one of `Changes.flows`); the asset is
    counted from that month's end and grows at `real_growth` a year beyond
    inflation, a twelfth a month, compounded, from the next. It counts at
    its value less `selling_costs` (a share of it)."""

    #: The day it is bought ("YYYY-MM-DD").
    date: str
    #: Its price in the base currency, in that day's own money.
    price: Decimal
    real_growth: Decimal = Decimal(0)
    selling_costs: Decimal = Decimal(0)


@dataclass(frozen=True)
class Changes:
    """What a scenario adds to the baseline's timelines."""

    #: Moves of cash on their days, in their day's own money (source
    #: "change"): one-offs, a loan's money, money moved into investments.
    #: They go where they say: none of them is shared out.
    flows: tuple[forecasting.Flow, ...] = ()
    #: Money moved into investments: (date, amount in the base currency, in
    #: that day's own money). Its cash side is one of `flows`.
    invested: tuple[tuple[str, Decimal], ...] = ()
    #: Loans taken out (`BaselineDebt.source` "scenario"). The money borrowed
    #: arrives as one of `flows`; the payments are scheduled ones.
    loans: tuple[BaselineDebt, ...] = ()
    #: Extra payments on the baseline's debts (or on a loan above): out of
    #: cash.
    extra: tuple[ExtraPayment, ...] = ()
    #: Cash flows that are part of the regular surplus, on their days, in
    #: their day's own money (source "change"): recurring costs and income,
    #: income changes, stopped flows. Shared out with the rest of it.
    regular: tuple[forecasting.Flow, ...] = ()
    #: Amounts set aside in cash out of the regular surplus, before the
    #: share invested is taken from what is left.
    kept: tuple[KeptInCash, ...] = ()
    #: Assets bought: other assets from their month on. Each price's cash
    #: side is one of `flows`.
    assets: tuple[Asset, ...] = ()

    @property
    def cash_flows(self) -> tuple[forecasting.Flow, ...]:
        """Every flow that moves cash on its day: moves and regular ones."""
        return (*self.flows, *self.regular)


NO_CHANGES = Changes()


def as_changes(changes: Changes | Sequence[forecasting.Flow]) -> Changes:
    """`changes` as `Changes`: a plain sequence of flows is moves of cash alone."""
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
    #: What it is paid in each month of the timeline: before its first
    #: payment (the as-of month; a loan's opening month), only an extra
    #: payment.
    payments: tuple[Decimal, ...]
    #: The part of each month's payment beyond its schedule: an extra
    #: payment, out of cash. The rest is scheduled (`scheduled`).
    extra: tuple[Decimal, ...]
    #: What it owes at each month's end.
    owed: tuple[Decimal, ...]
    #: Its payments: an extra payment before the first is month 0.
    schedule: tuple[PayoffScheduleEntry, ...]
    #: The calendar month of its last payment; None when not paid off within
    #: the timeline (or nothing is owed).
    paid_off: str | None
    total_interest: Decimal

    @property
    def scheduled(self) -> tuple[Decimal, ...]:
        """The part of each month's payment its own terms call for: the
        minimum, or what is left when that is less (a loan's last payment
        clears it). Out of the regular surplus; nothing once it is paid off."""
        return tuple(p - x for p, x in zip(self.payments, self.extra, strict=True))


def _named(extras: Sequence[ExtraPayment], debt_id: str) -> Callable[[str], Decimal]:
    """What the extra payments named for a debt add up to in a calendar
    month ("YYYY-MM")."""
    mine = [x for x in extras if x.debt_id == debt_id]

    def in_month(month: str) -> Decimal:
        return sum(
            (x.amount for x in mine if x.start <= month and (x.end is None or month <= x.end)),
            Decimal(0),
        )

    return in_month


def _extra_for(
    d: BaselineDebt, extras: Sequence[ExtraPayment], first: str
) -> Decimal | Callable[[int], Decimal]:
    """What is paid on `d` beyond its minimum in its plan's month m (1 is the
    month `first`): its own constant extra, and the extra payments named for
    it in the months they run."""
    if not any(x.debt_id == d.debt_id for x in extras):
        return d.extra_payment
    named = _named(extras, d.debt_id)

    def extra(m: int) -> Decimal:
        return d.extra_payment + named(debt_engine.month_after(first, m - 1))

    return extra


def _beyond_schedule(
    d: BaselineDebt, entry: PayoffScheduleEntry, requested: Decimal | Callable[[int], Decimal]
) -> Decimal:
    """The part of `entry`'s payment beyond `d`'s schedule. The debt engine
    pays a debt its minimum first (or, in a loan's last month, what is left),
    then the extra on top, up to what is left: so the extra is what was
    asked for, as far as the payment goes beyond the minimum; none in a
    loan's last month."""
    if d.term_months is not None and entry.month >= d.term_months:
        return Decimal(0)
    asked = requested(entry.month) if callable(requested) else requested
    return max(Decimal(0), min(asked, entry.payment - d.minimum_payment))


def debt_paths(
    baseline: Baseline,
    months: Sequence[Period],
    changes: Changes | Sequence[forecasting.Flow] = NO_CHANGES,
) -> list[DebtPath]:
    """Each debt amortised on its own terms (minimum plus any extra), its
    first payment in the month after the as-of month; then each loan the
    changes take out, owed from the month it is taken out and paid from its
    first payment's month, its last payment clearing it. Each payment is
    split into its scheduled part and the extra beyond it.

    An extra payment named for a debt in a month before its first payment
    (the as-of month, for a debt owed on the as-of date; the month it is
    taken out, for a loan) is paid at that month's end, up to what is owed,
    out of cash: what is owed is that much less before the schedule starts,
    so the interest after it is on less. One that clears the debt pays it
    off in that month, and nothing is scheduled after it. It is in the
    schedule as month 0."""
    added = as_changes(changes)
    paths: list[DebtPath] = []
    count = len(months)
    start = month_index(months[0].month)
    for d in (*baseline.debts, *added.loans):
        opened = 0 if d.opened is None else month_index(d.opened) - start
        first = 1 if d.first_payment is None else max(month_index(d.first_payment) - start, 1)
        payments = [Decimal(0)] * count
        beyond = [Decimal(0)] * count
        owed = [Decimal(0) if i < opened else d.balance for i in range(count)]
        schedule: list[PayoffScheduleEntry] = []
        paid_off: str | None = None
        interest = Decimal(0)
        balance = d.balance
        if balance > 0:
            # Before its first payment: what extra payments say, at the
            # month's end, before any interest.
            named = _named(added.extra, d.debt_id)
            for i in range(max(opened, 0), min(first, count)):
                paid = min(named(months[i].month), balance)
                if paid <= 0:
                    continue
                balance -= paid
                payments[i] = beyond[i] = paid
                owed[i:] = [balance] * (count - i)
                schedule.append(
                    PayoffScheduleEntry(
                        month=0,
                        debt_name=d.name,
                        payment=paid,
                        principal_paid=paid,
                        interest_paid=Decimal(0),
                        remaining_balance=balance,
                        period=months[i].month,
                        debt_id=d.debt_id,
                    )
                )
                if balance == 0:
                    paid_off = months[i].month
                    break
        if balance > 0 and opened < count and first < count:
            requested = _extra_for(d, added.extra, months[first].month)
            plan = debt_engine.compute_payoff_plan(
                [
                    Debt(
                        d.name,
                        balance,
                        d.apr,
                        d.minimum_payment,
                        id=d.debt_id,
                        term_months=d.term_months,
                    )
                ],
                requested,
                "avalanche",
                max_months=count - first,
                money_quantum=quantum(baseline.currency),
                first_month=months[first].month,
            )
            schedule += plan.schedule
            interest = plan.total_interest_paid
            paid_off = plan.debt_free_period
            for e in plan.schedule:
                payments[first - 1 + e.month] = e.payment
                beyond[first - 1 + e.month] = _beyond_schedule(d, e, requested)
            remaining = balance
            by_index = {first - 1 + e.month: e.remaining_balance for e in plan.schedule}
            for i in range(first, count):
                remaining = by_index.get(i, Decimal(0) if paid_off else remaining)
                owed[i] = remaining
        paths.append(
            DebtPath(
                d, tuple(payments), tuple(beyond), tuple(owed), tuple(schedule), paid_off, interest
            )
        )
    return paths


# ── The monthly cash plan ────────────────────────────────────────────────────


@dataclass(frozen=True)
class MonthPlan:
    """One month of the cash plan, in the month's own money (see the module)."""

    period: Period
    #: Today's money at the month's end: divide its own money by this.
    deflator: Decimal
    #: The baseline's part of the regular surplus: the average surplus (with
    #: what of the debts' payments it already pays) less the debts'
    #: scheduled payments that month; in the as-of month, the rest of it.
    #: Rounded to the currency's smallest unit.
    planned: Decimal
    #: A scenario's regular changes in the month, in the base currency:
    #: recurring costs and income, income changes, stopped flows.
    regular_changes: Decimal
    #: Paid on the debts beyond their schedules: out of cash.
    extra: Decimal
    #: A scenario's moves of cash in the month, in the base currency:
    #: one-offs, a loan's money, money moved into investments (out).
    changes: Decimal
    #: The share of the regular surplus moved into investments at the
    #: month's end, rounded to the currency's smallest unit: nothing when
    #: the regular surplus is a deficit. Of what is left once any amount set
    #: aside (`set_aside`) has stayed in cash.
    invested: Decimal
    #: What a scenario asked to set aside in cash out of the month's regular
    #: surplus before the share invested.
    set_aside: Decimal = Decimal(0)

    @property
    def regular(self) -> Decimal:
        """The month's regular surplus; below zero, a deficit."""
        return self.planned + self.regular_changes

    @property
    def cash_change(self) -> Decimal:
        """What cash changes by over the month: the regular surplus less the
        share invested, less the extra payments, plus the moves."""
        return self.regular - self.invested - self.extra + self.changes


def in_base(baseline: Baseline, flow: forecasting.Flow) -> Decimal | None:
    """A flow's amount in the base currency at the as-of rate; None without one."""
    if flow.currency == baseline.currency:
        return flow.amount
    rate = next((r.rate for r in baseline.rates if r.currency == flow.currency), None)
    return None if rate is None else flow.amount * rate


def _by_month(
    baseline: Baseline, flows: Sequence[forecasting.Flow], first: str
) -> dict[str, Decimal]:
    """What `flows` from the day `first` on add up to in each month, in the
    base currency at the as-of rates."""
    out: dict[str, Decimal] = defaultdict(Decimal)
    for flow in flows:
        value = in_base(baseline, flow)
        if value is not None and flow.date >= first:
            out[flow.date[:7]] += value
    return out


def scheduled_net(baseline: Baseline, months: Sequence[Period]) -> dict[str, Decimal]:
    """What the scheduled flows move the cash total by in each of the daily
    timeline's months, at the as-of rates."""
    window = months[:DAILY_MONTHS]
    net: dict[str, Decimal] = defaultdict(Decimal)
    for flow in scheduled_flows(baseline, baseline.as_of, window[-1].end):
        value = in_base(baseline, flow)
        if value is not None:
            net[flow.date[:7]] += value
    return net


def invested_share(regular: Decimal, share: Decimal, currency: str) -> Decimal:
    """What of a month's regular surplus moves into investments: `share` of
    it, rounded to the currency's smallest unit; nothing from a deficit."""
    return _money(share * regular, currency) if regular > 0 else Decimal(0)


def cash_plan(
    baseline: Baseline,
    months: Sequence[Period],
    paths: Sequence[DebtPath],
    changes: Changes | Sequence[forecasting.Flow] = NO_CHANGES,
) -> list[MonthPlan]:
    """The cash plan for `months` (the as-of month first, at least the daily
    timeline's thirteen).

    A full month's planned part: the surplus (with what of the debts'
    payments it already pays), in that month's money, less the debts'
    scheduled payments. The as-of month's: what is scheduled for the rest of
    it, and its share of what an average month's surplus is beyond its
    schedule (the schedule averaged over the daily timeline's twelve full
    months), in the as-of month's money. Not its share of the whole surplus:
    a salary still to come this month is not a share of one. Debts' scheduled
    payments start the next month, so they don't touch it (an extra payment
    in it is a move, out of cash). With the scenario's regular changes, that
    is the month's regular surplus, of which `baseline.surplus_invested`
    moves into investments at the month's end; extra payments and moves go
    in and out of cash.

    An amount a scenario sets aside (`Changes.kept`) stays in cash first:
    the share invested is of the regular surplus less it, and nothing when
    that is nothing or less.

    Every month's planned part and share invested is rounded to the
    currency's smallest unit, so the daily timeline, which spreads the one
    over the days and takes the other on the last, sums to it exactly."""
    currency = baseline.currency
    surplus = baseline.flows.surplus
    share = baseline.surplus_invested
    already = sum((p.debt.already_paid for p in paths), Decimal(0))
    added = as_changes(changes)
    first = months[0].start.isoformat()
    moves = _by_month(baseline, added.flows, first)
    regular = _by_month(baseline, added.regular, first)

    levels = deflators(baseline, months)
    # Each path's scheduled payments once: `scheduled` builds them all.
    schedules = [path.scheduled for path in paths]
    planned: list[Decimal] = [Decimal(0)]
    for i in range(1, len(months)):
        scheduled = sum((s[i] for s in schedules), Decimal(0))
        planned.append(_money((surplus + already) * levels[i] - scheduled, currency))

    # The as-of month's rest: what an average month's surplus is beyond its
    # schedule (the schedule averaged over the daily timeline's twelve full
    # months), at the as-of month's own prices, not at the average of the
    # next twelve months'.
    net = scheduled_net(baseline, months)
    schedule = [net.get(months[i].month, Decimal(0)) for i in range(1, DAILY_MONTHS)]
    average_rest = surplus * levels[0] - sum(schedule, Decimal(0)) / Decimal(len(schedule))
    planned[0] = _money(
        net.get(months[0].month, Decimal(0)) + average_rest * months[0].share, currency
    )

    out: list[MonthPlan] = []
    for i, (p, level) in enumerate(zip(months, levels, strict=True)):
        regular_changes = regular.get(p.month, Decimal(0))
        kept = sum((k.in_month(p.month) for k in added.kept), Decimal(0))
        out.append(
            MonthPlan(
                period=p,
                deflator=level,
                planned=planned[i],
                regular_changes=regular_changes,
                extra=sum((path.extra[i] for path in paths), Decimal(0)),
                changes=moves.get(p.month, Decimal(0)),
                invested=invested_share(planned[i] + regular_changes - kept, share, currency),
                set_aside=kept,
            )
        )
    return out


def _money(value: Decimal, currency: str) -> Decimal:
    return value.quantize(quantum(currency), rounding=ROUND_HALF_UP)


# ── The daily cash timeline ──────────────────────────────────────────────────


@dataclass(frozen=True)
class CashTimeline:
    """Cash day by day, in each day's own money."""

    forecast: forecasting.Forecast
    #: The cash at each month's end ("YYYY-MM" → amount), after the share
    #: invested has left it.
    month_ends: tuple[tuple[str, Decimal], ...]
    #: The rest of each month's plan, beyond what is scheduled, spread over
    #: its days.
    unscheduled: tuple[tuple[str, Decimal], ...]
    #: The share of each month's regular surplus that leaves cash for the
    #: investments on its last day.
    invested: tuple[tuple[str, Decimal], ...] = field(default_factory=tuple)
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
        *_within(as_changes(changes).cash_flows, end),
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
    """Cash day by day (see the module): what is scheduled, the changes'
    cash flows, the rest of each month's plan spread over its days (extra
    payments on debts among it), and the share invested leaving cash on the
    month's last day."""
    added = as_changes(changes)
    months = periods(baseline.as_of, DAILY_MONTHS)
    end = months[-1].end
    within = replace(
        added,
        flows=tuple(_within(added.flows, end)),
        regular=tuple(_within(added.regular, end)),
    )
    paths = debt_paths(baseline, months, within)
    plan = cash_plan(baseline, months, paths, within)
    notes: list[str] = []
    scheduled = scheduled_flows(baseline, baseline.as_of, end, notes)
    net = scheduled_net(baseline, months)

    rest: list[forecasting.Flow] = []
    unscheduled: list[tuple[str, Decimal]] = []
    invested: list[tuple[str, Decimal]] = []
    for month in plan:
        p = month.period
        remainder = month.planned - month.extra - net.get(p.month, Decimal(0))
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
        invested.append((p.month, month.invested))
        if month.invested:
            rest.append(
                forecasting.Flow(
                    p.end.isoformat(),
                    None,
                    -month.invested,
                    baseline.currency,
                    "The share of the month's surplus invested",
                    "invested",
                )
            )

    result = forecasting.project(
        baseline.cash_accounts,
        [*scheduled, *within.cash_flows, *rest],
        to_base(baseline),
        baseline.currency,
        baseline.as_of,
        end,
    )
    by_day = dict(result.daily)
    month_ends = tuple((m.period.month, by_day[m.period.end.isoformat()]) for m in plan)
    return CashTimeline(
        result,
        month_ends,
        tuple(unscheduled),
        tuple(invested),
        tuple(dict.fromkeys(notes)),
    )


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
    #: What moved into investments over the month, in its own money: the
    #: share of the regular surplus and a scenario's investments (nothing at
    #: the as-of point).
    invested: Decimal = Decimal(0)
    #: Other assets before selling costs: `other_assets` counts a scenario's
    #: assets at their value less them (always set; the baseline's own other
    #: assets are the same in both).
    other_assets_value: Decimal = Decimal(0)


@dataclass(frozen=True)
class DebtOutlook:
    debt_id: str
    name: str
    #: The calendar month of its last payment; None when not paid off within
    #: the horizon (or nothing is owed).
    paid_off: str | None
    total_interest: Decimal
    schedule: tuple[PayoffScheduleEntry, ...]
    #: Its yearly rate, a fraction.
    apr: Decimal = Decimal(0)
    #: What it owes at the end of each of the timeline's months (the points
    #: after the as-of point), in each month's own money.
    owed: tuple[Decimal, ...] = ()


@dataclass(frozen=True)
class MonthlyTimeline:
    points: tuple[MonthPoint, ...]
    debts: tuple[DebtOutlook, ...]
    #: The month the last debt is paid off; None when one isn't within the
    #: horizon. With no debts, None too.
    debt_free: str | None
    #: The base scenario's real return the investments grow at.
    real_return: Decimal
    #: The share of each month's regular surplus moved into investments.
    surplus_invested: Decimal = Decimal(1)
    #: What a reader should know: from when cash is below zero, if it is.
    notes: tuple[str, ...] = ()


class _AssetValues:
    """A scenario's assets month by month, in today's money: each counted
    from the end of the month it is bought, at its price deflated to that
    month, and grown at its real growth from the next month (as money moved
    into investments is)."""

    def __init__(self, assets: Sequence[Asset], first: str) -> None:
        self.assets = [a for a in assets if a.date >= first]
        self.values = [Decimal(0)] * len(self.assets)

    def at(self, month: MonthPlan) -> tuple[Decimal, Decimal]:
        """After `month`: the assets' value, and what they would fetch (their
        value less their selling costs)."""
        value = fetches = Decimal(0)
        for k, asset in enumerate(self.assets):
            if self.values[k]:
                self.values[k] *= Decimal(1) + asset.real_growth / _TWELVE * month.period.share
            if asset.date[:7] == month.period.month:
                self.values[k] += asset.price / month.deflator
            value += self.values[k]
            fetches += self.values[k] * (Decimal(1) - asset.selling_costs)
        return value, fetches


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
    investments grow at `real_return` (the base scenario's when None) and
    take the share of each month's regular surplus the baseline's
    `surplus_invested` says (see the module)."""
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
    bought = _AssetValues(added.assets, first)
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
            other_assets_value=other_assets,
        )
    ]
    below_zero: str | None = None
    for i, month in enumerate(plan):
        cash += month.cash_change
        if cash < 0 and below_zero is None:
            below_zero = month.period.month
        level = month.deflator
        investments *= Decimal(1) + real_return / _TWELVE * month.period.share
        # Money moved in during a month (a scenario's investment, and the
        # share of the regular surplus) grows from the next, in today's money.
        moved = invested.get(month.period.month, Decimal(0)) + month.invested
        investments += moved / level
        owed = sum((path.owed[i] for path in paths), Decimal(0))
        value, fetches = bought.at(month)
        points.append(
            MonthPoint(
                month=month.period.month,
                date=month.period.end.isoformat(),
                cash=cash / level,
                investments=investments,
                other_assets=other_assets + fetches,
                debts=owed / level,
                other_liabilities=other_liabilities / level,
                # What is held in money, deflated once, so the same money
                # moved between cash and a debt changes it by nothing.
                net_worth=(cash - owed - other_liabilities) / level
                + investments
                + other_assets
                + fetches,
                deflator=level,
                invested=moved,
                other_assets_value=other_assets + value,
            )
        )

    outlooks = tuple(
        DebtOutlook(
            p.debt.debt_id,
            p.debt.name,
            p.paid_off,
            p.total_interest,
            p.schedule,
            apr=p.debt.apr,
            owed=p.owed,
        )
        for p in paths
    )
    owing = [p for p in paths if p.debt.balance > 0]
    debt_free = (
        max(p.paid_off for p in owing if p.paid_off)
        if owing and all(p.paid_off for p in owing)
        else None
    )
    notes = (
        (
            f"Cash is below zero from the end of {below_zero}: what the regular surplus "
            "doesn't cover, and what is paid from cash, is drawn from cash, never from your "
            "investments, so cash is left below zero rather than investments sold.",
        )
        if below_zero is not None
        else ()
    )
    return MonthlyTimeline(
        tuple(points), outlooks, debt_free, real_return, baseline.surplus_invested, notes
    )


# ── Safe to spend ────────────────────────────────────────────────────────────

#: How far ahead safe-to-spend looks for the next income, and the window it
#: takes when the ledger expects none.
SAFE_LOOKAHEAD_DAYS = 45
SAFE_WINDOW_DAYS = 30
#: The cushion kept back: this share of a usual month's spending. Part of the
#: method, the same for everyone, and said in every answer.
SAFE_CUSHION = Decimal("0.1")


@dataclass(frozen=True)
class SafeToSpend:
    """What is free to spend until money next comes in: the lowest the cash
    gets before then, after what is scheduled and the everyday spending a
    usual month has beyond it, less a cushion."""

    #: Never below zero.
    amount: Decimal
    cash_today: Decimal
    #: The next income's day, or 30 days on when the ledger expects none.
    until: str
    next_income: forecasting.Flow | None
    #: What goes out before then. Money moved between two cash accounts is
    #: neither income nor committed: it never leaves cash.
    committed: tuple[forecasting.Flow, ...]
    forecast: forecasting.Forecast
    #: The everyday spending expected from today to the day before `until`:
    #: a usual month's spending beyond what is scheduled, day by day.
    everyday: Decimal = Decimal(0)
    #: Kept back: `SAFE_CUSHION` of a usual month's spending.
    cushion: Decimal = Decimal(0)
    notes: tuple[str, ...] = ()


def everyday_per_day(baseline: Baseline) -> Decimal:
    """A usual day's spending beyond what is scheduled: the average month's
    spending less the scheduled spending in a month (the next twelve,
    averaged), over a month's days. Scheduled spending is the rhythms booked
    to a spending account and the declared subscriptions; a rhythm that moves
    money to an account that holds it (investments, a debt) is not spending."""
    start = baseline.as_of
    end = start + dt.timedelta(days=365)
    held = {b.account_id for b in baseline.balances}
    cash = {account_id: currency for account_id, (currency, _) in baseline.cash_accounts.items()}
    spending = [r for r in baseline.recurring if r.direction == "out" and r.account_id not in held]
    scheduled = Decimal(0)
    for flow in [
        *forecasting.recurring_flows(spending, cash, start, end),
        *forecasting.declared_flows(baseline.charges, baseline.currency, start, end),
    ]:
        if flow.amount < 0 and not flow.transfer:
            amount = in_base(baseline, flow)
            if amount is not None:
                scheduled -= amount
    monthly = max(baseline.flows.expenses - scheduled / _TWELVE, Decimal(0))
    return monthly * _TWELVE / Decimal(365)


def safe_to_spend(
    baseline: Baseline, changes: Changes | Sequence[forecasting.Flow] = NO_CHANGES
) -> SafeToSpend:
    """Free to spend until payday, from the cash forecast (what is
    scheduled, and the changes' cash flows): from the as-of date until the
    day before the next income the ledger expects (a change's money in is not
    one, so a scenario is measured over the baseline's window), or over 30
    days when it expects none, the lowest the total gets once each day's
    everyday spending so far is out too (`everyday_per_day`), less the
    cushion; never below zero."""
    as_of = baseline.as_of
    currency = baseline.currency
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
    per_day = everyday_per_day(baseline)
    window = [
        v - per_day * ((dt.date.fromisoformat(d) - as_of).days + 1)
        for d, v in result.daily
        if d < until
    ] or [result.today - per_day]
    days = max((dt.date.fromisoformat(until) - as_of).days, 1)
    cushion = _money(baseline.flows.expenses * SAFE_CUSHION, currency)
    if not baseline.flows.months:
        notes.append(
            "No full month of spending yet: only what is scheduled is taken off, with no cushion."
        )
    committed = tuple(f for f in result.flows if f.amount < 0 and not f.transfer and f.date < until)
    return SafeToSpend(
        amount=max(_money(min(window) - cushion, currency), Decimal(0)),
        cash_today=result.today,
        until=until,
        next_income=income,
        committed=committed,
        forecast=result,
        everyday=_money(per_day * days, currency),
        cushion=cushion,
        notes=tuple(dict.fromkeys(notes)),
    )
