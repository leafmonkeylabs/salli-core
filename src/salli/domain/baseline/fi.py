"""
Financial independence on the monthly timeline. Pure, Decimal, real terms.

FI's date and projections come from the baseline's monthly timeline
(`timelines.monthly`), where cash, investments and debts are kept apart: the
share of each month's regular surplus the user invests (`surplus_invested`;
all of it, as a placeholder, as FI projections conventionally assume) goes
into the investments, which grow at the real return; the rest stays in cash,
which earns an active CMA pack's cash yield or nothing; debts follow their schedules, their payments freed into
the surplus once each is paid off. So FI, the baseline and every scenario
agree: a scenario with no changes has the baseline's FI exactly.

- **The FI number** is a year of the spending to live on, over the safe
  withdrawal rate: the baseline's average monthly spending (and a scenario's spending for good).
  Zero while there is no spending to go by.
- **Gross of tax.** When the user's active tax rules declare an income
  role keyed `withdrawal`, the spending a year is grossed up to what must be
  withdrawn so that, after the tax those rules take on it, the spending is
  left (`gross_up`; the as-of year's rules, level in today's money). The
  tax is marginal: what the rules take on the year's other taxable income
  (guaranteed income streams naming an income role, `taxed_income`) with
  the withdrawal, less what they take on that income alone. Without such a
  role it is not, and `withdrawal_tax` says so.
- **Guaranteed income and spending phases** (`domain/fi/plan.py`): the
  number at a month is built on that month's spending (its phase's, or the
  baseline's, plus a scenario's change) less the guaranteed income paying
  then, so the number can step down when a pension starts (`fi_numbers`).
  Without a plan every month's number is the same.
- **The FI asset base** at a month's end is what could fund withdrawals:
  cash and investments, less debts and other liabilities, in today's money.
  What else is owned (a home) funds none.
- **The FI month** is the first month whose end the base reaches the
  number, searched to 50 years whatever horizon is shown, counted in months
  from the as-of month (0: reached by its end, or already). None while there
  is no number, or when it isn't reached within 50 years.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from salli.domain.baseline import timelines
from salli.domain.baseline.models import Baseline
from salli.domain.debt.engine import month_after
from salli.domain.taxrules.common import RuleSetError
from salli.domain.taxrules.engine import compile_rule_set, evaluate

#: The income role a rule set taxes withdrawals with.
WITHDRAWAL_ROLE = "withdrawal"
_CENT = Decimal("0.01")

#: How far the FI month is looked for: the longest timeline.
FI_YEARS = timelines.MAX_HORIZON_YEARS


def spending(baseline: Baseline) -> Decimal:
    """The monthly spending FI is built on: the baseline's average spending."""
    return baseline.flows.expenses


def _withdrawal_rules(baseline: Baseline) -> Any:
    """The active rules that tax withdrawals: those declaring an income role
    `withdrawal`, in the base currency, the as-of year's (else the latest)."""
    found = [
        r
        for r in baseline.tax.rules
        if r.currency == baseline.currency
        and any(x.key == WITHDRAWAL_ROLE and x.kind == "income" for x in r.document.roles)
    ]
    covering = [r for r in found if r.start <= baseline.as_of <= r.end]
    pool = covering or [r for r in found if r.start <= baseline.as_of] or found
    return max(pool, key=lambda r: r.start) if pool else None


def withdrawal_tax(baseline: Baseline) -> dict[str, Any]:
    """Whether the FI number is grossed up for tax on withdrawals, and with
    which rules: `status` "computed" or "not_computed" (with why)."""
    rules = _withdrawal_rules(baseline)
    if rules is None:
        return {
            "status": "not_computed",
            "rules": None,
            "message": (
                "The FI number is not grossed up for tax: no active tax rules in your "
                f"currency declare an income role `{WITHDRAWAL_ROLE}`. Spending is taken "
                "as what you withdraw."
            ),
        }
    ref = rules.ref
    return {
        "status": "computed",
        "rules": {"rule_set_id": ref.rule_set_id, "version": ref.version, "year": ref.year},
        "message": (
            f"The FI number is grossed up for the tax your rules for {ref.year} take on "
            f"withdrawals (role `{WITHDRAWAL_ROLE}`), level in today's money."
        ),
    }


def gross_up(
    baseline: Baseline, annual: Decimal, other: Mapping[str, Decimal] | None = None
) -> Decimal:
    """What must be withdrawn in a year so that `annual` is left after the
    tax the withdrawal rules take on it beside `other` (the year's other
    taxable income by income role, `taxed_income`): the tax on both less the
    tax on `other` alone. `annual` itself without such rules (or if they
    fail). To the cent; memoised on the baseline's tax cache."""
    rules = _withdrawal_rules(baseline)
    if rules is None or annual <= 0:
        return annual
    declared = {x.key for x in rules.document.roles if x.kind == "income"}
    beside = {k: v for k, v in (other or {}).items() if k in declared and v > 0}
    memo = baseline.tax.memo
    key = ("gross_up", rules.ref.content_hash, annual, tuple(sorted(beside.items())))
    if key in memo:
        return memo[key]
    compiled = memo.get(("compiled", rules.ref.content_hash))
    try:
        if compiled is None:
            compiled = compile_rule_set(rules.document)
            memo[("compiled", rules.ref.content_hash)] = compiled

        def tax(withdrawn: Decimal) -> Decimal:
            roles = {**beside, WITHDRAWAL_ROLE: beside.get(WITHDRAWAL_ROLE, 0) + withdrawn}
            return max(evaluate(compiled, roles).net, Decimal(0))

        alone = tax(Decimal(0))

        def left(gross: Decimal) -> Decimal:
            return gross - max(tax(gross) - alone, Decimal(0))

        low, high = annual, annual * 2
        if left(low) >= annual:  # untaxed: nothing to gross up
            high = low
        while left(high) < annual and high < annual * 100:
            high *= 2
        while high - low > _CENT:
            mid = ((low + high) / 2).quantize(_CENT)
            if mid in (low, high):
                break
            if left(mid) >= annual:
                high = mid
            else:
                low = mid
        result = high
    except RuleSetError:
        result = annual
    memo[key] = result
    return result


def fi_number(baseline: Baseline, monthly_spending: Decimal | None = None) -> Decimal:
    """12 × `monthly_spending` (the baseline's, `spending`, when None), less
    the guaranteed income paying in the as-of month, grossed up for tax on
    withdrawals, over the safe withdrawal rate; zero without spending or a
    rate. The as-of month's figure of `fi_numbers`."""
    spend = spending(baseline) if monthly_spending is None else monthly_spending
    month = baseline.as_of.isoformat()[:7]
    return _number(baseline, need(baseline, month, spend, {}), taxed_income(baseline, month, {}))


def _number(
    baseline: Baseline, monthly_need: Decimal, other: Mapping[str, Decimal] | None = None
) -> Decimal:
    swr = baseline.assumptions.safe_withdrawal_rate.value
    annual = monthly_need * 12
    return gross_up(baseline, annual, other) / swr if annual > 0 and swr > 0 else Decimal(0)


def taxed_income(
    baseline: Baseline, month: str, levels: Mapping[str, Decimal]
) -> dict[str, Decimal]:
    """A year at `month`'s rate of the guaranteed income paying then that
    names an income role (`tax_role`), by role, in today's money: what the
    withdrawal is taxed beside. `levels` as for `need`."""
    out: dict[str, Decimal] = {}
    for stream in baseline.plan.streams:
        if stream.tax_role and month >= stream.start:
            level = levels.get(month, Decimal(1))
            real = stream.real_at(level, levels.get(stream.start, Decimal(1)))
            out[stream.tax_role] = out.get(stream.tax_role, Decimal(0)) + real * 12
    return out


def need(baseline: Baseline, month: str, spend: Decimal, levels: dict[str, Decimal]) -> Decimal:
    """The monthly spending to fund from the asset base in `month`, in
    today's money, before tax: the phase's spending (or the baseline's)
    plus a scenario's change (`spend` less the baseline's spending), less
    the guaranteed income paying in it; never below zero. `levels` are the
    timeline's deflators by month (1 where missing)."""
    plan = baseline.plan
    phase = plan.phase_spending(month)
    total = spend if phase is None else phase + (spend - spending(baseline))
    for stream in plan.streams:
        if month >= stream.start:
            level = levels.get(month, Decimal(1))
            total -= stream.real_at(level, levels.get(stream.start, Decimal(1)))
    return max(total, Decimal(0))


def fi_numbers(
    baseline: Baseline,
    points: Sequence[timelines.MonthPoint],
    monthly_spending: Decimal | None = None,
) -> list[Decimal]:
    """The FI number at each of a monthly timeline's points (see the module)."""
    spend = spending(baseline) if monthly_spending is None else monthly_spending
    if baseline.plan.empty:
        return [fi_number(baseline, spend)] * len(points)
    levels = {p.month: p.deflator for p in points[1:]}
    return [
        _number(
            baseline,
            need(baseline, p.month, spend, levels),
            taxed_income(baseline, p.month, levels),
        )
        for p in points
    ]


def asset_base(point: timelines.MonthPoint) -> Decimal:
    """What could fund withdrawals at a point, in today's money."""
    return point.cash + point.investments - point.debts - point.other_liabilities


def months_to_fi(
    points: Sequence[timelines.MonthPoint], number: Decimal | Sequence[Decimal]
) -> int | None:
    """Months from the as-of month to the first month-end at which the asset
    base reaches `number` (one, or one per point, `fi_numbers`): 0 when it
    already has (the as-of point) or does by the as-of month's end. `points`
    are a monthly timeline's."""
    numbers = [number] * len(points) if isinstance(number, Decimal) else list(number)
    if not points or numbers[0] <= 0:
        return None
    if asset_base(points[0]) >= numbers[0]:
        return 0
    for i, point in enumerate(points[1:]):
        if numbers[i + 1] > 0 and asset_base(point) >= numbers[i + 1]:
            return i
    return None


def fi_month(baseline: Baseline, months: int | None) -> str | None:
    """The calendar month ("YYYY-MM") `months` after the as-of month."""
    return None if months is None else month_after(baseline.as_of.isoformat()[:7], months)


def year_points(points: Sequence[timelines.MonthPoint], years: int) -> list[timelines.MonthPoint]:
    """The as-of point, then the point at each whole year on (the end of the
    month 12 × k months after the as-of month), to `years`."""
    return [
        points[0],
        *(points[12 * k + 1] for k in range(1, years + 1) if 12 * k + 1 < len(points)),
    ]


@dataclass(frozen=True)
class FiOutlook:
    """When FI is reached on one monthly timeline."""

    fi_number: Decimal
    #: Months from the as-of month, and the month; None when not reached
    #: within 50 years, or there is no number yet.
    months: int | None
    month: str | None
    #: The real return the timeline's investments grew at.
    real_return: Decimal


def outlook(
    baseline: Baseline,
    timeline: timelines.MonthlyTimeline,
    monthly_spending: Decimal | None = None,
) -> FiOutlook:
    """FI on `timeline` (a monthly timeline to 50 years, for the FI month to
    be found wherever it falls), with `monthly_spending` (the baseline's when
    None): the month the asset base reaches that month's number."""
    numbers = fi_numbers(baseline, timeline.points, monthly_spending)
    months = months_to_fi(timeline.points, numbers)
    return FiOutlook(numbers[0], months, fi_month(baseline, months), timeline.real_return)


def full_timeline(
    baseline: Baseline,
    changes: timelines.Changes = timelines.NO_CHANGES,
    *,
    real_return: Decimal | None = None,
) -> timelines.MonthlyTimeline:
    """The monthly timeline to 50 years: what the FI month and the debts'
    payoff are read from, whatever horizon is shown."""
    return timelines.monthly(baseline, FI_YEARS, changes, real_return=real_return)
