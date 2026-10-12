"""
Tax-aware scenarios: the change in each tax year's tax a scenario makes,
computed with the person's own active rules. Pure, deterministic, Decimal;
no model (docs/scenarios.md, "Tax"; the phase 3 design, section 1).

**What is taxed.** A change may carry a tax role (`tax_role`, a role of kind
`income` or `deduction` in the person's rules): its amounts then also add to
that role's total, so they are before tax. Money in adds to an income role
(a cut subtracts); money out adds to a deduction role (a refund subtracts).
A stopped ledger flow (`stop_recurring`) takes its account's role, so a stop
takes the flow off that role. Nothing else is taxed: investment growth is
not, and the person's real return is after the tax they pay on it.

**A year's role totals.** For each tax year the scenario touches, from the
one containing the as-of date, each role the rules declare is projected
twice, for the baseline and for the scenario:

    projected = actual to the as-of date
              + the rest of the year at the role's monthly average
              + the scenario's tagged amounts dated in the year (scenario only)

The actual is the postings on the role's accounts from the year's start to
the as-of date, at each entry date's rate into the rules' currency
(`taxrules.inputs.total_roles`). The average is the baseline's
(`BaselineTax.average`), in today's money, so each month's is grown to that
month's own money by the person's inflation; the rest of the as-of month is
its share of days after the as-of date. A dated amount belongs to the year
containing its day; a month's average to the year containing the month's
last day. Projected and tagged amounts are converted at the as-of date's
rate. Each total is in that year's own money, and is rounded to the rules'
currency.

**The change in tax.** Both sets of totals go through the rules
(`taxrules.engine.evaluate`, with the scenario's answers), and the change is
the scenario's `net` less the baseline's: what would be withheld more, or
settled, since withholding is projected from history and a tagged raise
doesn't change it. It is spread equally over the months from the month of
the year's first tagged amount to the year's last month, each part rounded
to the base currency's smallest unit and the last taking what rounding
left, as a regular flow on its month's last day: so it moves the regular
surplus, the share invested, cash and FI as a recurring cost would. It never
moves the FI number: tax on a salary is not spending to live on.

**Years no active rules cover** carry the latest active rules forward, with
every amount in them held level in today's money: the year's totals are
deflated by the person's inflation over the years carried (a twelfth of it
a month, compounded, as the timelines deflate), evaluated, and the result
grown back. Labelled `tax_rules_carried_forward`. A year with its own
active rules always uses them.

**Not computed.** Only active rules compute. With none (no residency, no
rule set, none activated), or a year whose rules don't declare a tagged
role, a question with no answer and no default, a missing rate, or rules
that fail on the totals, that year's tagged amounts flow before tax, and the
result says why (`status` "not_computed", `reason`).

Evaluations are memoised on the baseline (`BaselineTax.memo`) by the rules'
content hash, the totals, the answers and the years carried, so the
break-evens' bisections, which rerun the translation many times, evaluate
each distinct year once.
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from salli.domain.baseline.models import BaselineTax, RuleSetRef, TaxRules
from salli.domain.currency import quantum
from salli.domain.taxrules.common import Problem, RuleSetError, join_path
from salli.domain.taxrules.engine import CompiledRuleSet, compile_rule_set, evaluate
from salli.domain.taxrules.expr import Value
from salli.domain.taxrules.inputs import total_roles
from salli.domain.taxrules.schema import answer_value

#: The role kinds a change may be tagged with: money has a natural direction
#: for them. Withholding is projected from history; `other` has none.
TAGGABLE_KINDS = ("income", "deduction")

Status = Literal["computed", "not_computed", "none"]

_TWELVE = Decimal(12)
_YEAR = re.compile(r"^[0-9]{4}$")


# ── What a scenario adds to a role ───────────────────────────────────────────


@dataclass(frozen=True)
class Tagged:
    """A cash amount a change moves that counts towards a role: on its day,
    in that day's own money, in the base currency, money in positive."""

    #: The change it comes from, by index.
    change: int
    role: str
    day: dt.date
    amount: Decimal


def role_amount(kind: str, cash: Decimal) -> Decimal:
    """What a cash amount (money in positive) adds to a role of `kind`:
    money in to an income role, money out to a deduction role."""
    return cash if kind == "income" else -cash


# ── Years ────────────────────────────────────────────────────────────────────


def _shift(day: dt.date, years: int) -> dt.date:
    """The same day `years` later, 28 February for a 29th in a common year."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def _shifted_label(rules: TaxRules, years: int, start: dt.date, end: dt.date) -> str:
    label = rules.document.year.label
    if _YEAR.fullmatch(label) and int(label) == rules.start.year:
        return str(rules.start.year + years)
    return f"{start.isoformat()} to {end.isoformat()}"


def _pick(candidates: Sequence[TaxRules]) -> TaxRules | None:
    """The rules among `candidates` (one year's, in one country) that compute
    the person's tax: the only one, or the national one (no region) when a
    region's are beside it; None when that can't be told."""
    if len(candidates) == 1:
        return candidates[0]
    national = [c for c in candidates if c.ref.region is None]
    return national[0] if len(national) == 1 else None


@dataclass(frozen=True)
class YearPlan:
    """One tax year: its dates, and the rules that compute it."""

    label: str
    start: dt.date
    end: dt.date
    rules: TaxRules | None
    #: How many years the rules are carried forward from their own; 0 for a
    #: year with its own active rules.
    carried: int = 0
    #: Why no rules compute it, when none do.
    reason: str | None = None

    def contains(self, day: dt.date) -> bool:
        return self.start <= day <= self.end


def plan(tax: BaselineTax, as_of: dt.date, last: dt.date) -> list[YearPlan]:
    """The tax years from the one containing `as_of` to the one containing
    `last`: each with its own active rules, or the latest before it carried
    forward a whole number of years. Empty without active rules."""
    rules = list(tax.rules)
    if not rules:
        return []
    years: list[YearPlan] = []
    day = as_of
    while day <= last:
        first = not years
        covering = [r for r in rules if r.start <= day <= r.end]
        if covering:
            chosen = _pick(covering)
            own = chosen or covering[0]
            start = own.start if first else max(own.start, day)
            years.append(
                YearPlan(
                    own.document.year.label,
                    start,
                    own.end,
                    chosen,
                    0,
                    None
                    if chosen is not None
                    else (
                        f"you have active rules for more than one region for "
                        f"{own.document.year.label} "
                        f"({', '.join(sorted(r.ref.region or '(national)' for r in covering))}), "
                        "and Salli can't tell which compute your tax"
                    ),
                )
            )
            day = own.end + dt.timedelta(days=1)
            continue
        before = [r for r in rules if r.start <= day]
        if before:
            newest = max(r.start for r in before)
            latest = [r for r in before if r.start == newest]
            chosen = _pick(latest)
            base = chosen or latest[0]
            k = 1
            while _shift(base.end, k) < day:
                k += 1
            shifted_start, end = _shift(base.start, k), _shift(base.end, k)
            start = shifted_start if first else day
            years.append(
                YearPlan(
                    _shifted_label(base, k, shifted_start, end),
                    start,
                    end,
                    chosen,
                    k,
                    None
                    if chosen is not None
                    else (
                        "you have active rules for more than one region, and Salli can't tell "
                        "which compute your tax"
                    ),
                )
            )
            day = end + dt.timedelta(days=1)
            continue
        # Active rules only for years still to come: nothing to carry forward.
        upcoming = min(rules, key=lambda r: r.start)
        end = upcoming.start - dt.timedelta(days=1)
        years.append(
            YearPlan(
                f"{day.isoformat()} to {end.isoformat()}",
                day,
                end,
                None,
                0,
                f"your active tax rules begin with {upcoming.document.year.label} "
                f"({upcoming.start.isoformat()}), so none cover {day.isoformat()}",
            )
        )
        day = upcoming.start
    return years


# ── Results ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RoleTotal:
    """A role's total for one tax year, in the rules' currency and that
    year's own money."""

    key: str
    kind: str
    label: str
    #: Posted from the year's start to the as-of date.
    actual: Decimal
    #: The actual, and the rest of the year at the role's monthly average:
    #: the baseline's total.
    projected: Decimal
    #: The projected total and the scenario's tagged amounts.
    scenario: Decimal


@dataclass(frozen=True)
class YearTax:
    """One tax year's change in tax under a scenario."""

    label: str
    start: dt.date
    end: dt.date
    #: The rules that computed it (None when none could).
    rules: RuleSetRef | None
    #: Whether they are an earlier year's rules carried forward, level in
    #: today's money.
    carried_forward: bool
    #: The rules' currency, which the totals and `net` are in.
    currency: str | None
    status: Literal["computed", "not_computed"]
    reason: str | None
    #: The roles the scenario touches.
    roles: tuple[RoleTotal, ...]
    #: The year's `net` (after credits) under the baseline and the scenario,
    #: in the rules' currency.
    net_baseline: Decimal | None
    net_scenario: Decimal | None
    #: The change in the year's tax in the base currency (more tax is
    #: positive), nominal; None when not computed.
    change: Decimal | None
    #: How the change comes out of cash: (month, amount) in the base
    #: currency, each month's part, more tax positive.
    parts: tuple[tuple[str, Decimal], ...] = ()


@dataclass(frozen=True)
class TaxOutcome:
    """A scenario's tax: what its translation adds to the timelines, and
    what the result reports."""

    status: Status
    reason: str | None = None
    #: Each tax year with tagged amounts, the as-of date's first.
    years: tuple[YearTax, ...] = ()
    #: Whether any year's tax was computed with rules carried forward.
    carried_forward: bool = False
    #: The as-of date's tax year, by its label.
    as_of_year: str | None = None
    #: Why later years aren't computed, beside `reason` (the first's).
    notes: tuple[str, ...] = ()

    @property
    def this_year(self) -> YearTax | None:
        """The as-of date's tax year, when the scenario touches it."""
        return next((y for y in self.years if y.label == self.as_of_year), None)

    @property
    def change_this_year(self) -> Decimal | None:
        """The change in the as-of date's tax year's tax, in the base
        currency: 0 when nothing in that year is tagged; None when it is but
        its tax isn't computed, or there are no rules to tell."""
        if self.status == "not_computed" and not self.years:
            return None  # no rules to say which tax year anything falls in
        year = self.this_year
        if year is None:
            return Decimal(0)
        return year.change

    @property
    def parts(self) -> tuple[tuple[str, Decimal], ...]:
        return tuple(p for y in self.years for p in y.parts)


NO_TAX = TaxOutcome("none")


# ── Computing ────────────────────────────────────────────────────────────────


@dataclass
class _Context:
    tax: BaselineTax
    as_of: dt.date
    base: str
    #: Each month's price level ("YYYY-MM" → its own money over today's).
    levels: Mapping[str, Decimal]
    inflation: Decimal
    answers: Mapping[str, str | bool]
    compiled: dict[str, CompiledRuleSet] = field(default_factory=dict[str, CompiledRuleSet])

    def compile(self, rules: TaxRules) -> CompiledRuleSet:
        key = rules.ref.content_hash
        found = self.compiled.get(key)
        if found is None:
            memo = self.tax.memo
            found = memo.get(("compiled", key))
            if found is None:
                found = compile_rule_set(rules.document)
                memo[("compiled", key)] = found
            self.compiled[key] = found
        return found


def _money(value: Decimal, currency: str) -> Decimal:
    return value.quantize(quantum(currency, strict=False), rounding=ROUND_HALF_UP)


def _month_end(month: str) -> dt.date:
    year, number = int(month[:4]), int(month[5:7])
    return dt.date(year, number, calendar.monthrange(year, number)[1])


def _months_between(first: str, last: str) -> list[str]:
    out: list[str] = []
    year, number = int(first[:4]), int(first[5:7])
    while f"{year:04d}-{number:02d}" <= last:
        out.append(f"{year:04d}-{number:02d}")
        number += 1
        if number > 12:
            year, number = year + 1, 1
    return out


def _rest_of_month(as_of: dt.date) -> Decimal:
    """The share of the as-of month after the as-of date."""
    days = calendar.monthrange(as_of.year, as_of.month)[1]
    return Decimal(days - as_of.day) / Decimal(days)


def _rate(ctx: _Context, currency: str, day: str) -> Decimal | None:
    if currency == ctx.base:
        return Decimal(1)
    return ctx.tax.rates.get(currency, {}).get(day)


def _no_rate(ctx: _Context, currency: str, day: str) -> str:
    return (
        f"Salli has no {ctx.base}→{currency} exchange rate for {day}, so it can't convert "
        f"your amounts into your rules' currency: try again when a rate is published"
    )


def _projected_average(ctx: _Context, year: YearPlan, role: str, horizon: Sequence[str]) -> Decimal:
    """The rest of the year at the role's monthly average, in the base
    currency and each month's own money: the as-of month's rest by its share
    of days after the as-of date, then each full month whose last day falls
    in the year."""
    average = ctx.tax.average.get(role, Decimal(0))
    if average == 0:
        return Decimal(0)
    total = Decimal(0)
    as_of_month = ctx.as_of.isoformat()[:7]
    for month in horizon:
        end = _month_end(month)
        if end > year.end:
            break
        if not year.contains(end):
            continue
        share = _rest_of_month(ctx.as_of) if month == as_of_month else Decimal(1)
        total += average * ctx.levels.get(month, Decimal(1)) * share
    return total


def _evaluate(
    ctx: _Context,
    rules: TaxRules,
    totals: Mapping[str, Decimal],
    answers: Mapping[str, Value],
    carried: int,
) -> Decimal:
    """The rules' `net` on `totals` (in the year's own money), carried
    forward `carried` years when they are an earlier year's: the totals
    deflated to the rules' year's money, evaluated, and the net grown back.
    Memoised. RuleSetError when the rules fail."""
    currency = rules.currency
    factor = (Decimal(1) + ctx.inflation / _TWELVE) ** (12 * carried) if carried else Decimal(1)
    deflated = {k: _money(v / factor, currency) for k, v in totals.items()}
    key = (
        "net",
        rules.ref.content_hash,
        tuple(sorted(deflated.items())),
        tuple(sorted((k, str(v)) for k, v in answers.items())),
    )
    memo = ctx.tax.memo
    if key in memo:
        net = memo[key]
    else:
        try:
            net = evaluate(ctx.compile(rules), deflated, answers).net
        except RuleSetError as error:
            memo[key] = error
            raise
        memo[key] = net
    if isinstance(net, RuleSetError):
        raise net
    assert isinstance(net, Decimal)
    return _money(net * factor, currency)


def _answers(ctx: _Context, rules: TaxRules) -> tuple[dict[str, Value], list[str]]:
    """The scenario's answers to these rules' questions, typed, and the
    questions they need an answer to and have none."""
    out: dict[str, Value] = {}
    missing: list[str] = []
    for q in rules.document.questions:
        if q.key in ctx.answers:
            try:
                out[q.key] = answer_value(q, ctx.answers[q.key])
            except ValueError:
                missing.append(f"{q.label} (`{q.key}`)")
        elif q.default is None:
            missing.append(f"{q.label} (`{q.key}`)")
    return out, missing


def _split(change: Decimal, months: Sequence[str], currency: str) -> list[tuple[str, Decimal]]:
    """`change` equally over `months`, each part rounded to the currency's
    smallest unit and the last taking what rounding left."""
    n = len(months)
    if n == 0:
        return []
    each = _money(change / Decimal(n), currency)
    parts = [(m, each) for m in months[:-1]]
    parts.append((months[-1], change - each * (n - 1)))
    return parts


def _year(
    ctx: _Context,
    year: YearPlan,
    tagged: Sequence[Tagged],
    horizon: Sequence[str],
) -> YearTax:
    rules = year.rules
    touched = sorted({t.role for t in tagged})

    def not_computed(reason: str, currency: str | None = None) -> YearTax:
        return YearTax(
            year.label,
            year.start,
            year.end,
            rules.ref if rules else None,
            bool(year.carried),
            currency,
            "not_computed",
            f"Tax for {year.label} isn't computed: {reason}",
            (),
            None,
            None,
            None,
        )

    if rules is None:
        return not_computed(year.reason or "no active rules cover it")
    declared = {r.key: r for r in rules.document.roles}
    unknown = [role for role in touched if role not in declared]
    if unknown:
        return not_computed(
            f"{', '.join(unknown)} {'is not a role' if len(unknown) == 1 else 'are not roles'} "
            f"of your rules for {rules.document.year.label}: tag a role they declare, or add "
            "it to them",
            rules.currency,
        )
    currency = rules.currency
    as_of = ctx.as_of.isoformat()
    rate = _rate(ctx, currency, as_of)
    if rate is None:
        return not_computed(_no_rate(ctx, currency, as_of), currency)
    answers, missing = _answers(ctx, rules)
    if missing:
        return not_computed(
            f"your rules for {rules.document.year.label} need an answer to "
            f"{', '.join(missing)}: give it in the scenario's tax.answers",
            currency,
        )

    # Actual to the as-of date, at each entry date's rate.
    roles = list(declared)
    actual: Mapping[str, Decimal] = dict.fromkeys(roles, Decimal(0))
    if year.contains(ctx.as_of):
        start, end = year.start.isoformat(), as_of
        postings = [
            p for p in ctx.tax.postings if start <= p.entry_date <= end and p.role in declared
        ]
        rates = ctx.tax.rates.get(currency, {})
        try:
            actual = total_roles(postings, roles, ctx.base, currency, rates).totals
        except KeyError as missing_day:
            return not_computed(_no_rate(ctx, currency, str(missing_day.args[0])), currency)

    baseline: dict[str, Decimal] = {}
    scenario: dict[str, Decimal] = {}
    for role in roles:
        rest = _money(_projected_average(ctx, year, role, horizon) * rate, currency)
        baseline[role] = actual[role] + rest
        added = sum(
            (role_amount(declared[role].kind, t.amount) for t in tagged if t.role == role),
            Decimal(0),
        )
        scenario[role] = baseline[role] + _money(added * rate, currency)
    try:
        net_b = _evaluate(ctx, rules, baseline, answers, year.carried)
        net_s = _evaluate(ctx, rules, scenario, answers, year.carried)
    except RuleSetError as error:
        problems = "; ".join(str(p) for p in error.problems) or str(error)
        return not_computed(
            f"your rules for {rules.document.year.label} can't be applied: {problems}", currency
        )
    change = _money((net_s - net_b) / rate, ctx.base)
    first = min(t.day for t in tagged).isoformat()[:7]
    months = _months_between(first, year.end.isoformat()[:7])
    return YearTax(
        year.label,
        year.start,
        year.end,
        rules.ref,
        bool(year.carried),
        currency,
        "computed",
        None,
        tuple(
            RoleTotal(
                role,
                declared[role].kind,
                declared[role].label,
                actual[role],
                baseline[role],
                scenario[role],
            )
            for role in touched
        ),
        net_b,
        net_s,
        change,
        tuple(_split(change, months, ctx.base)),
    )


def kinds_of(tax: BaselineTax) -> dict[str, set[str]]:
    """Each role the active rules declare, and the kinds they give it."""
    out: dict[str, set[str]] = defaultdict(set)
    for rules in tax.rules:
        for role in rules.document.roles:
            out[role.key].add(role.kind)
    return out


def check_tags(tax: BaselineTax, tags: Sequence[tuple[str, str]]) -> list[Problem]:
    """Problems with each (path, role) a change tags: a role the active
    rules declare as a kind that can't be tagged (withholding, other)."""
    kinds = kinds_of(tax)
    problems: list[Problem] = []
    for path, role in tags:
        wrong = sorted(kinds.get(role, set()) - set(TAGGABLE_KINDS))
        if wrong:
            problems.append(
                Problem(
                    path,
                    f"{role} is a role of kind {wrong[0]} in your tax rules: only income and "
                    "deduction roles can be tagged (a cash amount has no natural direction "
                    "for the others; withholding is projected from your ledger)",
                )
            )
    return problems


def check_answers(tax: BaselineTax, answers: Mapping[str, str | bool]) -> list[Problem]:
    """Problems with the scenario's answers: one no active rules ask, or one
    that doesn't fit the question (checked as a computation checks it)."""
    if not tax.rules or not answers:
        return []
    problems: list[Problem] = []
    for key, value in sorted(answers.items()):
        path = join_path("tax", "answers", key)
        asked = [q for rules in tax.rules for q in rules.document.questions if q.key == key]
        if not asked:
            problems.append(Problem(path, f"{key!r} is not a question of your active tax rules"))
            continue
        for question in asked:
            try:
                answer_value(question, value)
            except ValueError as error:
                problems.append(Problem(path, str(error)))
                break
    return problems


def compute(
    tax: BaselineTax,
    *,
    as_of: dt.date,
    base: str,
    levels: Mapping[str, Decimal],
    inflation: Decimal | None,
    tagged: Sequence[Tagged],
    answers: Mapping[str, str | bool],
    last: dt.date,
    until: dt.date | None = None,
) -> TaxOutcome:
    """The change in each tax year's tax the `tagged` amounts make, and the
    months it comes out of cash in (see the module). `levels` are each
    month's price level from the as-of month; `last` the monthly timeline's
    last day; `until`: years starting after it are left out (a break-even
    that reads only the next months)."""
    if not tagged:
        return NO_TAX
    if not tax.rules:
        return TaxOutcome(
            "not_computed",
            tax.unavailable
            or "You have no active tax rules, so tagged amounts are counted before tax.",
        )
    ctx = _Context(tax, as_of, base, levels, inflation or Decimal(0), answers)
    horizon = sorted(levels)
    end = max(t.day for t in tagged)
    years: list[YearTax] = []
    plans = plan(tax, as_of, min(end, last))
    for year in plans:
        if until is not None and year.start > until:
            break
        mine = [t for t in tagged if year.contains(t.day)]
        if not mine:
            continue
        result = _year(ctx, year, mine, horizon)
        if result.parts:
            result = _within(result, last)
        years.append(result)
    failed = [y for y in years if y.status == "not_computed"]
    status: Status = "not_computed" if failed else "computed"
    return TaxOutcome(
        status,
        failed[0].reason if failed else None,
        tuple(years),
        any(y.carried_forward and y.status == "computed" for y in years),
        plans[0].label if plans else None,
        tuple(y.reason for y in failed[1:] if y.reason),
    )


def _within(year: YearTax, last: dt.date) -> YearTax:
    """The year with only the parts that fall within the timeline."""
    cut = last.isoformat()[:7]
    kept = tuple(p for p in year.parts if p[0] <= cut)
    if len(kept) == len(year.parts):
        return year
    return YearTax(
        year.label,
        year.start,
        year.end,
        year.rules,
        year.carried_forward,
        year.currency,
        year.status,
        year.reason,
        year.roles,
        year.net_baseline,
        year.net_scenario,
        year.change,
        kept,
    )


__all__ = [
    "NO_TAX",
    "TAGGABLE_KINDS",
    "RoleTotal",
    "Tagged",
    "TaxOutcome",
    "YearPlan",
    "YearTax",
    "check_answers",
    "check_tags",
    "compute",
    "kinds_of",
    "plan",
    "role_amount",
]
