"""
The scenario engine: `run(baseline, scenario) -> ScenarioResult`. Pure,
deterministic, Decimal; no model, and nothing written anywhere.

**Translating.** Each change becomes what the baseline's timelines take
(`timelines.Changes`), either part of the regular surplus, which the share
invested (`surplus_invested`) splits between investments and cash as it
does the baseline's own, or a move that goes where it says:

- `one_off`: a move, a cash flow on its day, in that day's money.
- `recurring`: regular, a cash flow on each day its cadence lands on
  (monthly and longer keep the start's day of the month, kept to short
  months), from its start to its end or for good. In today's money: each is
  the amount grown by the user's inflation to its month (nothing, with none
  set), as the baseline's average spending is.
- `income_change`: regular, the same, monthly from its `from` day.
- `loan`: the money borrowed is a move, arriving in cash on its start day;
  it is owed from that month's end and repaid from the month after in level
  payments (`fi.engine.installment_payment`, rounded to the currency's
  smallest unit), the last one clearing it. Its payments are scheduled ones,
  out of the regular surplus, and fixed in their own day's money; once it
  is paid off they are freed.
- `extra_debt_payment`: a move, paid out of cash onto a debt on top of its
  minimum each month from `from`'s month to `to`'s, until it is paid off.
  Debts are first paid in the month after the as-of month; in the as-of
  month itself, it is paid at the month's end, up to what is owed, before
  the schedule starts (`timelines.debt_paths`). The debt's scheduled
  payments it saves join the regular surplus once the debt is gone.
- `invest`: a move, cash out on its day into the investments, which then
  grow at the real return.
- `stop_recurring`: regular, what the ledger's recurring flow would have
  moved, put back on each day it would have fallen, from `from` on. Only a
  flow of income or spending: a transfer between the user's own accounts is
  no part of what they earn or spend.
- `set_aside`: neither: it moves no money of its own, but keeps that much of
  each month's regular surplus in cash from `from`'s month to `to`'s, before
  the share invested is taken from the rest (`timelines.KeptInCash`).

**Tax.** A one-off, a recurring change or an income change with a
`tax_role` is before tax: its amounts also add to that role's total, and a
stopped flow takes its account's role. Each tax year's change in tax, from
the person's active rules (`tax.compute`), is regular: spread over the
year's months from its first tagged amount, a cash flow on each month's last
day (source "tax"). It never moves the FI number. A scenario that tags
nothing has no tax, and every figure as without it.

Every date in a change is on or after the as-of date; every account is a
cash account held in the base currency; every amount fits the currency's
smallest unit. Anything else is a `ScenarioError` with each problem's path.

**Evaluating.** The baseline and the scenario are each evaluated the same
way (`evaluate`): the daily cash timeline (the as-of month and the twelve
after it), safe-to-spend from the cash forecast, and the monthly timeline to
50 years, whatever the horizon shown, so the FI month and the debts' payoff
are found wherever they fall. Every figure is reported as baseline /
scenario / delta.

**The FI number** under a scenario is built on the spending it leaves for
good: the baseline's average, plus recurring costs with no end, less the
spending a stop takes away. A FIRE strategy's target, when it names one,
stays the target.

**Reproducible.** A result records the assumptions (placeholders flagged),
the versions of the FI assumptions and the rule sets, the as-of date, and a
content hash of the scenario (as_of filled in) and the baseline's
fingerprint: the same hash, the same figures.
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from salli.domain import canonical
from salli.domain.baseline import fi, timelines
from salli.domain.baseline.models import Baseline, BaselineDebt, RuleSetRef
from salli.domain.currency import quantum
from salli.domain.debt.engine import month_after
from salli.domain.fi.assumptions import FiAssumptions, assumptions_dict
from salli.domain.fi.engine import installment_payment
from salli.domain.reports import forecast as forecasting
from salli.domain.reports.insights import Recurring as Rhythm
from salli.domain.scenarios import schema
from salli.domain.scenarios import tax as taxes
from salli.domain.taxrules.common import Problem, join_path

#: Bumped whenever the same inputs would give different figures. 2: the
#: share of the regular surplus invested (`surplus_invested`). 3: an extra
#: payment in the as-of month (or a loan's opening month) is paid, at the
#: month's end, rather than dropped.
ENGINE_VERSION = "3"
#: The years the monthly figures are shown at (and the horizon itself).
CHECKPOINT_YEARS = (1, 5, 10, 20)
#: A ledger whose newest entry is older than this is too stale to decide on.
STALE_AFTER_DAYS = 45

#: Months in a recurring flow's period, for its monthly equivalent.
_PER_MONTH: dict[str, Decimal] = {
    "weekly": Decimal(52) / Decimal(12),
    "biweekly": Decimal(26) / Decimal(12),
    "semimonthly": Decimal(2),
    "monthly": Decimal(1),
    "quarterly": Decimal(1) / Decimal(3),
    "yearly": Decimal(1) / Decimal(12),
}
_MONTHS_PER: dict[str, int] = {"monthly": 1, "quarterly": 3, "yearly": 12}


class ScenarioError(ValueError):
    """A scenario that can't be run against this baseline, with every
    problem found in it (not just the first)."""

    def __init__(self, problems: Sequence[Problem]) -> None:
        self.problems = tuple(problems)
        shown = "; ".join(str(p) for p in self.problems[:5])
        more = f" (and {len(self.problems) - 5} more)" if len(self.problems) > 5 else ""
        super().__init__(f"{len(self.problems)} problem(s): {shown}{more}")


# ── Translating changes ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Stopped:
    """A recurring flow a `stop_recurring` stops."""

    payee: str
    cadence: str
    #: Each time, signed (money in positive), in `currency`.
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class AppliedChange:
    """A change as the engine read it: what it is called, and what it does
    that its own fields don't say."""

    index: int
    type: str
    label: str
    #: A loan's (or an extra payment's) debt id.
    debt_id: str | None = None
    #: A loan's monthly payment, in the base currency.
    payment: Decimal | None = None
    #: A loan's first payment's month.
    first_payment: str | None = None
    #: A recurring change's, an income change's or a stop's effect a month,
    #: in today's money and the base currency (money in positive); what a
    #: set-aside keeps in cash a month.
    monthly: Decimal | None = None
    #: Whether it lasts for good (a recurring change or an income change
    #: with no end; a stop).
    for_good: bool | None = None
    stopped: tuple[Stopped, ...] = ()


@dataclass(frozen=True)
class Translation:
    changes: timelines.Changes
    applied: tuple[AppliedChange, ...]
    #: The monthly spending the scenario's FI number is built on.
    spending: Decimal
    notes: tuple[str, ...] = ()
    #: The change in each tax year's tax (its parts are among the regular
    #: flows of `changes`).
    tax: taxes.TaxOutcome = taxes.NO_TAX


def _month_end(month: str) -> dt.date:
    """The last day of a calendar month ("YYYY-MM")."""
    year, number = int(month[:4]), int(month[5:7])
    return dt.date(year, number, calendar.monthrange(year, number)[1])


def _on(year: int, month: int, day: int) -> dt.date:
    """`day` of the month `month` (counted on past December), kept to it."""
    total = month - 1
    year, month = year + total // 12, total % 12 + 1
    return dt.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def occurrences(start: dt.date, cadence: str, last: dt.date) -> list[dt.date]:
    """The days a `cadence` lands on from `start` to `last`: every seven days,
    or every one, three or twelve months on the start's day of the month
    (kept to a short month, and back to it after)."""
    out: list[dt.date] = []
    if cadence == "weekly":
        day = start
        while day <= last:
            out.append(day)
            day += dt.timedelta(days=7)
        return out
    step = _MONTHS_PER[cadence]
    k = 0
    while (day := _on(start.year, start.month + k * step, start.day)) <= last:
        out.append(day)
        k += 1
    return out


def _decimals_ok(amount: Decimal, currency: str) -> bool:
    """Whether `amount` is a whole number of the currency's smallest unit
    ("2400.000" is, in euros; "2400.005" isn't)."""
    return amount == amount.quantize(quantum(currency, strict=False))


@dataclass
class _Translator:
    baseline: Baseline
    scenario: schema.Scenario
    #: The last day flows are made for.
    until: dt.date
    problems: list[Problem] = field(default_factory=list[Problem])
    notes: list[str] = field(default_factory=list[str])

    def __post_init__(self) -> None:
        months = timelines.periods(self.baseline.as_of, timelines.horizon_months(fi.FI_YEARS))
        self.levels = {
            p.month: level
            for p, level in zip(months, timelines.deflators(self.baseline, months), strict=True)
        }
        #: The 50-year timeline's last day: tagged amounts are gathered to it
        #: whatever `until` is, since a year's tax rests on the whole year.
        self.last = months[-1].end
        self.end = min(self.until, self.last)
        self.cash = self.baseline.cash_accounts
        self.balances = {b.account_id: b for b in self.baseline.balances}
        self.tagged: list[taxes.Tagged] = []
        self.tags: list[tuple[str, str]] = []

    @property
    def currency(self) -> str:
        return self.baseline.currency

    def problem(self, path: str, message: str) -> None:
        self.problems.append(Problem(path, message))

    def money(self, value: Decimal, currency: str | None = None) -> Decimal:
        return value.quantize(quantum(currency or self.currency), rounding=ROUND_HALF_UP)

    def today_money(self, amount: Decimal, day: dt.date, currency: str | None = None) -> Decimal:
        """`amount` in today's money, in `day`'s own money."""
        level = self.levels.get(day.isoformat()[:7], Decimal(1))
        return self.money(amount * level, currency)

    # ── checks ───────────────────────────────────────────────────────────

    def date(self, path: str, day: dt.date) -> None:
        if day < self.baseline.as_of:
            self.problem(
                path,
                f"is before the as-of date ({self.baseline.as_of.isoformat()}): a scenario "
                "changes what comes next",
            )

    def amount(self, path: str, value: Decimal) -> None:
        if not _decimals_ok(value, self.currency):
            self.problem(
                path,
                f"has more decimals than {self.currency}'s smallest unit "
                f"({quantum(self.currency, strict=False)})",
            )

    def account(self, path: str, account_id: str | None) -> str | None:
        """The cash account a change moves (None: the cash total)."""
        if account_id is None:
            return None
        balance = self.balances.get(account_id)
        if balance is None:
            self.problem(path, f"{account_id!r} is not one of your accounts")
            return None
        if account_id not in self.cash or balance.role == "liability":
            self.problem(
                path,
                f"{balance.name} is not one of your cash accounts, so a change can't move "
                "it: name a cash account, or leave the account out to move your cash total",
            )
            return None
        if balance.currency != self.currency:
            self.problem(
                path,
                f"{balance.name} is held in {balance.currency}; a change's amounts are in "
                f"your base currency ({self.currency}), so it moves an account held in it",
            )
            return None
        return account_id

    # ── changes ──────────────────────────────────────────────────────────

    def flow(
        self, day: dt.date, account: str | None, amount: Decimal, label: str
    ) -> forecasting.Flow:
        return forecasting.Flow(day.isoformat(), account, amount, self.currency, label, "change")

    def translate(self) -> Translation:
        flows: list[forecasting.Flow] = []
        regular: list[forecasting.Flow] = []
        invested: list[tuple[str, Decimal]] = []
        loans: list[BaselineDebt] = []
        extra: list[timelines.ExtraPayment] = []
        kept: list[timelines.KeptInCash] = []
        applied: list[AppliedChange] = []
        spending = Decimal(0)  # the change in spending for good, a month
        debts = {d.debt_id: d for d in self.baseline.debts}
        if self.scenario.as_of is not None and self.scenario.as_of != self.baseline.as_of:
            self.problem("as_of", f"is not the baseline's as-of date ({self.baseline.as_of})")

        for i, change in enumerate(self.scenario.changes):
            at = join_path("changes", i)

            def here(name: str, at: str = at) -> str:
                return join_path(at, name)

            match change:
                case schema.OneOffChange():
                    self.date(here("date"), change.date)
                    self.amount(here("amount"), change.amount)
                    account = self.account(here("account"), change.account)
                    if change.date <= self.end:
                        flows.append(
                            self.flow(change.date, account, self.money(change.amount), change.label)
                        )
                    if change.tax_role is not None:
                        self.tag(here("tax_role"), change.tax_role)
                        if change.date <= self.last:
                            self.tagged.append(
                                taxes.Tagged(
                                    i, change.tax_role, change.date, self.money(change.amount)
                                )
                            )
                    applied.append(AppliedChange(i, change.type, change.label))
                case schema.RecurringChange():
                    self.date(here("start"), change.start)
                    self.amount(here("amount"), change.amount)
                    account = self.account(here("account"), change.account)
                    last = min(change.end or self.end, self.end)
                    for day in occurrences(change.start, change.cadence, last):
                        regular.append(
                            self.flow(
                                day, account, self.today_money(change.amount, day), change.label
                            )
                        )
                    if change.tax_role is not None:
                        self.tag(here("tax_role"), change.tax_role)
                        through = min(change.end or self.last, self.last)
                        self.tagged += [
                            taxes.Tagged(
                                i, change.tax_role, day, self.today_money(change.amount, day)
                            )
                            for day in occurrences(change.start, change.cadence, through)
                        ]
                    monthly = change.amount * _PER_MONTH[change.cadence]
                    if change.end is None and change.amount < 0:
                        spending -= monthly
                    applied.append(
                        AppliedChange(
                            i,
                            change.type,
                            change.label,
                            monthly=monthly,
                            for_good=change.end is None,
                        )
                    )
                case schema.IncomeChange():
                    self.date(here("from"), change.from_)
                    self.amount(here("monthly"), change.monthly)
                    last = min(change.to or self.end, self.end)
                    for day in occurrences(change.from_, "monthly", last):
                        regular.append(
                            self.flow(
                                day, None, self.today_money(change.monthly, day), change.label
                            )
                        )
                    if change.tax_role is not None:
                        self.tag(here("tax_role"), change.tax_role)
                        through = min(change.to or self.last, self.last)
                        self.tagged += [
                            taxes.Tagged(
                                i, change.tax_role, day, self.today_money(change.monthly, day)
                            )
                            for day in occurrences(change.from_, "monthly", through)
                        ]
                    applied.append(
                        AppliedChange(
                            i,
                            change.type,
                            change.label,
                            monthly=change.monthly,
                            for_good=change.to is None,
                        )
                    )
                case schema.LoanChange():
                    self.date(here("start"), change.start)
                    self.amount(here("principal"), change.principal)
                    account = self.account(here("into"), change.into)
                    payment = self.money(
                        installment_payment(
                            change.principal, change.annual_rate, change.term_months
                        )
                    )
                    opened = change.start.isoformat()[:7]
                    first = month_after(opened, 1)
                    debt_id = f"scenario-loan-{i + 1}"
                    if change.start <= self.end:
                        flows.append(
                            self.flow(
                                change.start, account, self.money(change.principal), change.label
                            )
                        )
                    loans.append(
                        BaselineDebt(
                            debt_id=debt_id,
                            name=change.label,
                            apr=change.annual_rate,
                            minimum_payment=payment,
                            balance=self.money(change.principal),
                            source="scenario",
                            account_id=None,
                            already_paid=Decimal(0),
                            opened=opened,
                            first_payment=first,
                            term_months=change.term_months,
                        )
                    )
                    applied.append(
                        AppliedChange(
                            i,
                            change.type,
                            change.label,
                            debt_id=debt_id,
                            payment=payment,
                            first_payment=first,
                        )
                    )
                case schema.ExtraDebtPaymentChange():
                    self.date(here("from"), change.from_)
                    self.amount(here("monthly"), change.monthly)
                    debt = debts.get(change.debt)
                    if debt is None:
                        self.problem(here("debt"), f"{change.debt!r} is not one of your debts")
                    label = change.label or f"Extra on {debt.name if debt else change.debt}"
                    extra.append(
                        timelines.ExtraPayment(
                            change.debt,
                            change.from_.isoformat()[:7],
                            change.to.isoformat()[:7] if change.to else None,
                            self.money(change.monthly),
                        )
                    )
                    applied.append(AppliedChange(i, change.type, label, debt_id=change.debt))
                case schema.InvestChange():
                    self.date(here("date"), change.date)
                    self.amount(here("amount"), change.amount)
                    account = self.account(here("from"), change.from_)
                    if change.date <= self.end:
                        flows.append(
                            self.flow(
                                change.date, account, -self.money(change.amount), change.label
                            )
                        )
                        invested.append((change.date.isoformat(), self.money(change.amount)))
                    applied.append(AppliedChange(i, change.type, change.label))
                case schema.SetAsideChange():
                    self.date(here("from"), change.from_)
                    self.amount(here("monthly"), change.monthly)
                    kept.append(
                        timelines.KeptInCash(
                            change.from_.isoformat()[:7],
                            change.to.isoformat()[:7] if change.to else None,
                            self.money(change.monthly),
                        )
                    )
                    applied.append(
                        AppliedChange(
                            i,
                            change.type,
                            change.label or "Set aside in cash",
                            monthly=self.money(change.monthly),
                            for_good=change.to is None,
                        )
                    )
                case schema.StopRecurringChange():
                    self.date(here("from"), change.from_)
                    stop, stopped, less = self.stop(here("key"), change, i)
                    regular.extend(stop)
                    spending -= less
                    applied.append(
                        AppliedChange(
                            i,
                            change.type,
                            change.label
                            or f"Stop {', '.join(s.payee for s in stopped) or change.key}",
                            monthly=sum((self._monthly_in_base(s) for s in stopped), Decimal(0))
                            * -1,
                            for_good=True,
                            stopped=stopped,
                        )
                    )

        tax_answers = dict(self.scenario.tax.answers) if self.scenario.tax else {}
        self.problems += taxes.check_tags(self.baseline.tax, self.tags)
        self.problems += taxes.check_answers(self.baseline.tax, tax_answers)
        if self.problems:
            raise ScenarioError(self.problems)
        outcome = taxes.compute(
            self.baseline.tax,
            as_of=self.baseline.as_of,
            base=self.currency,
            levels=self.levels,
            inflation=self.baseline.inflation,
            tagged=self.tagged,
            answers=tax_answers,
            last=self.last,
            until=self.end if self.end < self.last else None,
        )
        last_day = self.end.isoformat()
        for year in outcome.years:
            for month, part in year.parts:
                day = _month_end(month)
                if part and day.isoformat() <= last_day:
                    regular.append(
                        forecasting.Flow(
                            day.isoformat(),
                            None,
                            -part,
                            self.currency,
                            f"Change in tax for {year.label}",
                            "tax",
                        )
                    )
        base = fi.spending(self.baseline)
        target = self.baseline.strategy.target_monthly_expenses if self.baseline.strategy else None
        scenario_spending = (
            base if target is not None and target > 0 else max(base + spending, Decimal(0))
        )
        return Translation(
            timelines.Changes(
                flows=tuple(flows),
                invested=tuple(invested),
                loans=tuple(loans),
                extra=tuple(extra),
                regular=tuple(regular),
                kept=tuple(kept),
            ),
            tuple(applied),
            scenario_spending,
            tuple(dict.fromkeys(self.notes)),
            outcome,
        )

    def tag(self, path: str, role: str) -> None:
        """A change tagged with a tax role, checked against the rules."""
        self.tags.append((path, role))

    def _monthly_in_base(self, s: Stopped) -> Decimal:
        rate = Decimal(1)
        if s.currency != self.currency:
            rate = next(
                (r.rate for r in self.baseline.rates if r.currency == s.currency), None
            ) or Decimal(0)
        return s.amount * rate * _PER_MONTH.get(s.cadence, Decimal(1))

    def stop(
        self, path: str, change: schema.StopRecurringChange, index: int
    ) -> tuple[list[forecasting.Flow], tuple[Stopped, ...], Decimal]:
        """The flows that put back what the recurring flows with this key
        would have moved, what they are, and the spending a month it takes
        away (in the base currency). A flow whose account carries a tax role
        the active rules declare as income or deduction comes off that role
        (`tagged`), to the end of the timeline."""
        found = [r for r in self.baseline.recurring if r.key == change.key]
        if not found:
            self.problem(
                path,
                f"No recurring flow has the key {change.key!r}: GET /v1/insights/recurring "
                "(`salli insights recurring`) lists them with their keys",
            )
            return [], (), Decimal(0)
        flowing = [r for r in found if r.account_id not in self.balances]
        if not flowing:
            names = ", ".join(sorted({r.payee for r in found}))
            self.problem(
                path,
                f"{names} moves money between your own accounts, which is no part of what "
                "you earn or spend: stopping it changes nothing here (how much of your "
                "surplus is invested is your surplus_invested assumption; to move a sum, "
                "add an invest change)",
            )
            return [], (), Decimal(0)
        flows: list[forecasting.Flow] = []
        stopped: list[Stopped] = []
        less = Decimal(0)
        kinds = taxes.kinds_of(self.baseline.tax)
        last = self.end.isoformat()
        for r in flowing:
            stop = self._stop_one(r, change)
            if stop is None:
                continue
            flows.extend(f for f in stop[0] if f.date <= last)
            stopped.append(stop[1])
            role = self.baseline.tax.account_roles.get(r.account_id)
            if role is not None and kinds.get(role, set()) & set(taxes.TAGGABLE_KINDS):
                for f in stop[0]:
                    value = timelines.in_base(self.baseline, f)
                    if value is not None:
                        self.tagged.append(
                            taxes.Tagged(index, role, dt.date.fromisoformat(f.date), value)
                        )
            if r.direction == "out":
                less += self._monthly_in_base(
                    Stopped(r.payee, r.cadence, -stop[1].amount, stop[1].currency)
                )
        return flows, tuple(stopped), less

    def _stop_one(
        self, r: Rhythm, change: schema.StopRecurringChange
    ) -> tuple[list[forecasting.Flow], Stopped] | None:
        account = r.money_account_id if r.money_account_id in self.cash else None
        currency = self.cash[account][0] if account else r.currency
        amount = r.money_amount if account else None
        if amount is None:
            amount = r.typical_amount if r.currency == currency else None
        if amount is None:
            self.notes.append(f"{r.payee}: its amount in {currency} can't be known; not stopped")
            return None
        sign = Decimal(1) if r.direction == "in" else Decimal(-1)
        each = sign * amount
        if account is None and currency != self.currency:
            rate = next((x.rate for x in self.baseline.rates if x.currency == currency), None)
            if rate is None:
                self.notes.append(f"{r.payee}: no {currency} rate; not stopped")
                return None
            each, currency = each * rate, self.currency
        due = dt.date.fromisoformat(r.next_expected)
        days = forecasting.schedule(due, r.cadence, r.anchor_days, self.baseline.as_of, self.last)
        flows = [
            forecasting.Flow(
                day.isoformat(),
                account,
                -self.today_money(each, day, currency),
                currency,
                change.label or f"Stop {r.payee}",
                "change",
            )
            for day in days
            if day >= change.from_
        ]
        return flows, Stopped(r.payee, r.cadence, self.money(each, currency), currency)


def translate(
    baseline: Baseline, scenario: schema.Scenario, *, until: dt.date | None = None
) -> Translation:
    """The scenario's changes as the timelines take them (see the module),
    with flows made to `until` (the 50-year timeline's end when None).
    ScenarioError with every problem found."""
    return _Translator(baseline, scenario, until or dt.date.max).translate()


# ── Evaluating ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Outlook:
    """The baseline, or a scenario, on both timelines."""

    cash: timelines.CashTimeline
    safe: timelines.SafeToSpend
    #: To 50 years.
    monthly: timelines.MonthlyTimeline
    fi: fi.FiOutlook
    spending: Decimal


def evaluate(
    baseline: Baseline,
    changes: timelines.Changes,
    spending: Decimal,
    *,
    real_return: Decimal | None = None,
) -> Outlook:
    monthly = fi.full_timeline(baseline, changes, real_return=real_return)
    return Outlook(
        cash=timelines.daily(baseline, changes),
        safe=timelines.safe_to_spend(baseline, changes),
        monthly=monthly,
        fi=fi.outlook(baseline, monthly, fi.fi_number(baseline, spending)),
        spending=spending,
    )


def baseline_outlook(baseline: Baseline) -> Outlook:
    return evaluate(baseline, timelines.NO_CHANGES, fi.spending(baseline))


# ── Results ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Figure:
    """A figure under the baseline and under the scenario."""

    baseline: Decimal | None
    scenario: Decimal | None

    @property
    def delta(self) -> Decimal | None:
        if self.baseline is None or self.scenario is None:
            return None
        return self.scenario - self.baseline


@dataclass(frozen=True)
class MonthFigure:
    """A calendar month ("YYYY-MM") under each; the delta in months (later
    is positive). None where it doesn't fall within 50 years."""

    baseline: str | None
    scenario: str | None

    @property
    def delta(self) -> int | None:
        if self.baseline is None or self.scenario is None:
            return None
        return timelines.month_index(self.scenario) - timelines.month_index(self.baseline)


@dataclass(frozen=True)
class DayFigure:
    """A day under each; the delta in days."""

    baseline: str
    scenario: str

    @property
    def delta(self) -> int:
        return (dt.date.fromisoformat(self.scenario) - dt.date.fromisoformat(self.baseline)).days


@dataclass(frozen=True)
class AccountCash:
    account_id: str
    name: str
    currency: str
    #: The lowest it gets in the next twelve months, in its own currency.
    lowest: Figure
    lowest_date: DayFigure
    below_zero: tuple[bool, bool]


@dataclass(frozen=True)
class CashResult:
    start: str
    end: str
    #: The cash total at its lowest, and when.
    lowest: Figure
    lowest_date: DayFigure
    #: At the end of the twelfth month after the as-of month.
    at_end: Figure
    safe_to_spend: Figure
    #: Safe-to-spend's window ends the day before this (the baseline's).
    safe_until: str
    #: Each cash account held in the bank (not a card), at its lowest.
    accounts: tuple[AccountCash, ...]


@dataclass(frozen=True)
class Checkpoint:
    """The monthly timeline a whole number of years on, in today's money."""

    years: int
    month: str
    date: str
    net_worth: Figure
    cash: Figure
    investments: Figure
    debts: Figure


@dataclass(frozen=True)
class DebtResult:
    debt_id: str
    name: str
    source: Literal["account", "declared", "scenario"]
    paid_off: MonthFigure
    total_interest: Figure


@dataclass(frozen=True)
class DebtsResult:
    items: tuple[DebtResult, ...]
    total_interest: Figure
    debt_free: MonthFigure


@dataclass(frozen=True)
class Resilience:
    """Months of spending the cash covers: at its lowest in the next twelve
    months, and at their end."""

    #: "essential" when spending carries need tags, else "all"; None without
    #: spending to go by.
    basis: Literal["essential", "all"] | None
    monthly_spending: Decimal | None
    lowest: Figure
    at_end: Figure


@dataclass(frozen=True)
class FiResult:
    fi_number: Figure
    #: The monthly spending each FI number is built on.
    monthly_spending: Figure
    fi_month: MonthFigure
    #: Months sooner (positive) or later (negative) than the baseline's.
    months_gained: int | None


@dataclass(frozen=True)
class BreakEven:
    """A value at which the answer changes, solved exactly, or none within
    the range searched."""

    kind: Literal["recurring_cash_floor", "invest_vs_debt_return", "loan_rate"]
    #: The option or options it concerns, by label.
    options: tuple[str, ...]
    #: The option and change it varies, when it varies one.
    option: str | None
    change: int | None
    status: Literal["found", "none_in_range"]
    value: Decimal | None
    low: Decimal
    high: Decimal
    #: Where the search found no break-even: which option is ahead across
    #: the whole range, by label.
    ahead: str | None = None


@dataclass(frozen=True)
class Versions:
    schema: str
    engine: str
    #: A content hash of the FI assumptions that applied.
    fi_assumptions: str
    fire_strategy: int | None
    rule_sets: tuple[RuleSetRef, ...]


@dataclass(frozen=True)
class TaxResult:
    """A scenario's tax (`tax.TaxOutcome`), with its change over the horizon
    in today's money."""

    outcome: taxes.TaxOutcome
    #: The change in tax over the horizon, every month's part deflated to
    #: today's money (more tax positive); None when no tax is computed.
    total_change: Decimal | None

    @property
    def status(self) -> taxes.Status:
        return self.outcome.status


@dataclass(frozen=True)
class ScenarioResult:
    label: str | None
    as_of: dt.date
    horizon_years: int
    currency: str
    #: The content hash of the inputs: the scenario (as_of filled in) and
    #: the baseline's fingerprint.
    hash: str
    baseline_fingerprint: str
    #: The scenario as run, with its as_of.
    scenario: schema.Scenario
    changes: tuple[AppliedChange, ...]
    cash: CashResult
    monthly: tuple[Checkpoint, ...]
    debts: DebtsResult
    resilience: Resilience
    fi: FiResult
    break_evens: tuple[BreakEven, ...]
    tax: TaxResult
    assumptions: FiAssumptions
    placeholders: tuple[str, ...]
    versions: Versions
    #: The newest ledger entry on or before the as-of date, and whether it
    #: is older than `STALE_AFTER_DAYS`.
    data_as_of: str | None
    is_stale: bool
    notes: tuple[str, ...]


def content_hash(baseline: Baseline, scenario: schema.Scenario) -> str:
    """The hash of the canonical inputs: the scenario with its as_of (keys in
    any order, amounts however they were written) and the baseline's
    fingerprint."""
    filled = scenario.model_copy(update={"as_of": baseline.as_of})
    return canonical.digest(
        {
            "engine": ENGINE_VERSION,
            "scenario": schema.hashable(filled),
            "baseline": baseline.fingerprint,
        }
    )


def checkpoint_years(horizon_years: int) -> list[int]:
    return sorted({y for y in (*CHECKPOINT_YEARS, horizon_years) if y <= horizon_years})


def _cash(baseline: Baseline, base: Outlook, mine: Outlook) -> CashResult:
    b, s = base.cash.forecast, mine.cash.forecast
    b_accounts = {a.account_id: a for a in b.accounts}
    s_accounts = {a.account_id: a for a in s.accounts}
    accounts = tuple(
        AccountCash(
            account_id=x.account_id,
            name=x.name,
            currency=x.currency,
            lowest=Figure(b_accounts[x.account_id].lowest, s_accounts[x.account_id].lowest),
            lowest_date=DayFigure(
                b_accounts[x.account_id].lowest_date, s_accounts[x.account_id].lowest_date
            ),
            below_zero=(
                b_accounts[x.account_id].lowest < 0,
                s_accounts[x.account_id].lowest < 0,
            ),
        )
        for x in baseline.balances
        if x.role == "cash" and x.account_id in b_accounts and x.account_id in s_accounts
    )
    return CashResult(
        start=b.start,
        end=b.end,
        lowest=Figure(b.lowest, s.lowest),
        lowest_date=DayFigure(b.lowest_date, s.lowest_date),
        at_end=Figure(b.end_balance, s.end_balance),
        safe_to_spend=Figure(base.safe.amount, mine.safe.amount),
        safe_until=base.safe.until,
        accounts=accounts,
    )


def _checkpoints(horizon_years: int, base: Outlook, mine: Outlook) -> tuple[Checkpoint, ...]:
    out: list[Checkpoint] = []
    for years in checkpoint_years(horizon_years):
        b, s = base.monthly.points[12 * years + 1], mine.monthly.points[12 * years + 1]
        out.append(
            Checkpoint(
                years=years,
                month=b.month,
                date=b.date,
                net_worth=Figure(b.net_worth, s.net_worth),
                cash=Figure(b.cash, s.cash),
                investments=Figure(b.investments, s.investments),
                debts=Figure(b.debts, s.debts),
            )
        )
    return tuple(out)


def _debts(baseline: Baseline, base: Outlook, mine: Outlook) -> DebtsResult:
    """Each debt's payoff month and interest under each: the baseline's
    debts, then the scenario's loans (owed nothing, and no interest, under
    the baseline)."""
    before = {d.debt_id: d for d in base.monthly.debts}
    sources: dict[str, Literal["account", "declared", "scenario"]] = {
        d.debt_id: d.source for d in baseline.debts
    }
    items: list[DebtResult] = []
    for d in mine.monthly.debts:
        was = before.get(d.debt_id)
        items.append(
            DebtResult(
                debt_id=d.debt_id,
                name=d.name,
                source=sources.get(d.debt_id, "scenario"),
                paid_off=MonthFigure(was.paid_off if was else None, d.paid_off),
                total_interest=Figure(was.total_interest if was else Decimal(0), d.total_interest),
            )
        )
    return DebtsResult(
        items=tuple(items),
        total_interest=Figure(
            sum((d.total_interest for d in base.monthly.debts), Decimal(0)),
            sum((d.total_interest for d in mine.monthly.debts), Decimal(0)),
        ),
        debt_free=MonthFigure(base.monthly.debt_free, mine.monthly.debt_free),
    )


def spending_basis(
    baseline: Baseline,
) -> tuple[Literal["essential", "all"], Decimal] | tuple[None, None]:
    """The monthly spending emergency-fund months are counted in: essential
    spending when the spending carries need tags, all of it otherwise; none
    without spending to go by."""
    flows = baseline.flows
    if flows.essential is not None and flows.essential > 0:
        return "essential", flows.essential
    if flows.expenses > 0:
        return "all", flows.expenses
    return None, None


def _resilience(baseline: Baseline, base: Outlook, mine: Outlook) -> Resilience:
    basis, spend = spending_basis(baseline)
    if basis is None or spend is None:
        return Resilience(None, None, Figure(None, None), Figure(None, None))

    def months(value: Decimal) -> Decimal:
        return value / spend

    return Resilience(
        basis=basis,
        monthly_spending=spend,
        lowest=Figure(months(base.cash.forecast.lowest), months(mine.cash.forecast.lowest)),
        at_end=Figure(
            months(base.cash.forecast.end_balance), months(mine.cash.forecast.end_balance)
        ),
    )


def _fi(base: Outlook, mine: Outlook) -> FiResult:
    gained = (
        base.fi.months - mine.fi.months
        if base.fi.months is not None and mine.fi.months is not None
        else None
    )
    return FiResult(
        fi_number=Figure(base.fi.fi_number, mine.fi.fi_number),
        monthly_spending=Figure(base.spending, mine.spending),
        fi_month=MonthFigure(base.fi.month, mine.fi.month),
        months_gained=gained,
    )


# ── Cash covering a target ───────────────────────────────────────────────────


@dataclass(frozen=True)
class CoverTarget:
    """When cash comes to cover a number of months of spending, under the
    baseline and under a scenario: read from the monthly timeline, never
    worked out from a rate of saving."""

    target_months: Decimal
    #: The spending counted in (resilience's): "essential" when tagged,
    #: "all" otherwise; None without spending to go by.
    basis: Literal["essential", "all"] | None
    monthly_spending: Decimal | None
    #: The target in cash: `target_months` of that spending (as shown, to
    #: the currency's smallest unit), in today's money.
    target: Decimal | None
    #: The months the cash covers on the as-of date.
    now: Decimal | None
    #: The first month at whose end cash, in today's money, is at or above
    #: the target (the as-of month when it already is); None when it isn't
    #: within 50 years, or there is no spending to count in.
    reached: MonthFigure
    #: The same in months from the as-of month (0: already, or by its end).
    months: tuple[int | None, int | None]


def months_to_cover(
    points: Sequence[timelines.MonthPoint], target: Decimal, currency: str
) -> int | None:
    """Months from the as-of month to the first month-end at which cash, in
    today's money and to the currency's smallest unit, is at least `target`:
    0 when it is already (the as-of point) or is by the as-of month's end."""
    if not points:
        return None
    q = quantum(currency)
    if points[0].cash.quantize(q, rounding=ROUND_HALF_UP) >= target:
        return 0
    for i, point in enumerate(points[1:]):
        if point.cash.quantize(q, rounding=ROUND_HALF_UP) >= target:
            return i
    return None


def cover_target(
    baseline: Baseline, base: Outlook, mine: Outlook, target_months: Decimal
) -> CoverTarget:
    """When cash covers `target_months` of spending under the baseline
    (`base`) and under a scenario (`mine`), each on its own monthly timeline
    to 50 years. The target is in today's money, as the timeline's cash is,
    so inflation doesn't move it."""
    basis, spend = spending_basis(baseline)
    if basis is None or spend is None:
        return CoverTarget(
            target_months, None, None, None, None, MonthFigure(None, None), (None, None)
        )
    q = quantum(baseline.currency)
    # Of the monthly spending as shown, so the target is the product of the
    # two figures a reader sees.
    shown = spend.quantize(q, rounding=ROUND_HALF_UP)
    target = (target_months * shown).quantize(q, rounding=ROUND_HALF_UP)
    b = months_to_cover(base.monthly.points, target, baseline.currency)
    s = months_to_cover(mine.monthly.points, target, baseline.currency)
    return CoverTarget(
        target_months=target_months,
        basis=basis,
        monthly_spending=shown,
        target=target,
        now=baseline.cash / spend,
        reached=MonthFigure(fi.fi_month(baseline, b), fi.fi_month(baseline, s)),
        months=(b, s),
    )


def versions(baseline: Baseline) -> Versions:
    return Versions(
        schema=schema.SCHEMA_ID,
        engine=ENGINE_VERSION,
        fi_assumptions=canonical.digest(assumptions_dict(baseline.assumptions)),
        fire_strategy=baseline.strategy.version if baseline.strategy else None,
        rule_sets=baseline.rule_sets,
    )


# ── Break-evens on one scenario ──────────────────────────────────────────────


def search_last_true(low: int, high: int, holds: Callable[[int], bool]) -> int | None:
    """The largest n in [low, high] for which `holds(n)`, when `holds` is
    true up to some n and false after it (None when false at `low`): by
    bisection on whole numbers, so exact and deterministic."""
    if not holds(low):
        return None
    if holds(high):
        return high
    lo, hi = low, high  # holds(lo), not holds(hi)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if holds(mid):
            lo = mid
        else:
            hi = mid
    return lo


def cash_floors(
    baseline: Baseline, scenario: schema.Scenario, mine: Outlook, label: str
) -> list[BreakEven]:
    """For each recurring cost in a scenario whose cash goes below zero in the
    next twelve months: the most it could be, each time, with cash staying
    at or above zero (to the currency's smallest unit), or none in range when
    cash goes below zero even without it."""
    if mine.cash.forecast.lowest >= 0:
        return []
    q = quantum(baseline.currency)
    window_end = dt.date.fromisoformat(mine.cash.forecast.end)
    out: list[BreakEven] = []
    for i, change in enumerate(scenario.changes):
        if not isinstance(change, schema.RecurringChange) or change.amount >= 0:
            continue
        top = int(-change.amount / q)

        def stays_above(minor: int, i: int = i, change: schema.RecurringChange = change) -> bool:
            altered = list(scenario.changes)
            altered[i] = change.model_copy(update={"amount": -q * minor})
            trial = scenario.model_copy(update={"changes": altered})
            changes = translate(baseline, trial, until=window_end).changes
            return timelines.daily(baseline, changes).forecast.lowest >= 0

        found = search_last_true(0, top, stays_above)
        out.append(
            BreakEven(
                kind="recurring_cash_floor",
                options=(label,),
                option=label,
                change=i,
                status="none_in_range" if found is None else "found",
                value=None if found is None else q * found,
                low=Decimal(0),
                high=-change.amount,
            )
        )
    return out


# ── Running ──────────────────────────────────────────────────────────────────


def run(
    baseline: Baseline, scenario: schema.Scenario, *, base: Outlook | None = None
) -> ScenarioResult:
    """The scenario against the baseline: every figure under each, and the
    delta. `base` is the baseline's own outlook, when the caller has it
    already (a comparison evaluates it once). Writes nothing."""
    return run_with_outlook(baseline, scenario, base=base)[0]


@dataclass(frozen=True)
class Evaluated:
    """A scenario's result, and what it was read from: the scenario's own
    outlook on both timelines and how its changes were translated (for
    figures the result doesn't carry: a decision's principles and
    projection, domain/decisions)."""

    result: ScenarioResult
    outlook: Outlook
    translation: Translation


def _tax(outcome: taxes.TaxOutcome, mine: Outlook, horizon_years: int) -> TaxResult:
    if outcome.status == "none":
        return TaxResult(outcome, Decimal(0))
    if not any(y.status == "computed" for y in outcome.years):
        return TaxResult(outcome, None)
    points = mine.monthly.points[1 : 12 * horizon_years + 2]
    levels = {p.month: p.deflator for p in points}
    total = sum(
        (part / levels[month] for month, part in outcome.parts if month in levels),
        Decimal(0),
    )
    return TaxResult(outcome, total)


def placeholders(baseline: Baseline, outcome: taxes.TaxOutcome) -> tuple[str, ...]:
    """The baseline's placeholders, and the scenario's tax: "tax" when it
    isn't computed (tagged amounts then count before tax), and
    "tax_rules_carried_forward" when a year's tax rests on an earlier year's
    rules."""
    return (
        *baseline.placeholders,
        *(("tax",) if outcome.status == "not_computed" else ()),
        *(("tax_rules_carried_forward",) if outcome.carried_forward else ()),
    )


def run_with_outlook(
    baseline: Baseline, scenario: schema.Scenario, *, base: Outlook | None = None
) -> tuple[ScenarioResult, Evaluated]:
    """`run`, and the outlook and translation its figures come from."""
    translation = translate(baseline, scenario)
    base = base or baseline_outlook(baseline)
    mine = evaluate(baseline, translation.changes, translation.spending)
    label = scenario.label or "Scenario"
    latest = baseline.latest_entry
    stale = (
        latest is None or (baseline.as_of - dt.date.fromisoformat(latest)).days > STALE_AFTER_DAYS
    )
    filled = scenario.model_copy(update={"as_of": baseline.as_of})
    result = ScenarioResult(
        label=scenario.label,
        as_of=baseline.as_of,
        horizon_years=scenario.horizon_years,
        currency=baseline.currency,
        hash=content_hash(baseline, scenario),
        baseline_fingerprint=baseline.fingerprint,
        scenario=filled,
        changes=translation.applied,
        cash=_cash(baseline, base, mine),
        monthly=_checkpoints(scenario.horizon_years, base, mine),
        debts=_debts(baseline, base, mine),
        resilience=_resilience(baseline, base, mine),
        fi=_fi(base, mine),
        break_evens=tuple(cash_floors(baseline, scenario, mine, label)),
        tax=_tax(translation.tax, mine, scenario.horizon_years),
        assumptions=baseline.assumptions,
        placeholders=placeholders(baseline, translation.tax),
        versions=versions(baseline),
        data_as_of=latest,
        is_stale=stale,
        notes=tuple(
            dict.fromkeys(
                [
                    *baseline.notes,
                    *mine.cash.notes,
                    *mine.monthly.notes,
                    *translation.notes,
                    *translation.tax.notes,
                ]
            )
        ),
    )
    return result, Evaluated(result, mine, translation)
