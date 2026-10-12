"""
Comparing options: `compare(baseline, [scenario × 2..5]) -> Comparison`.
Pure, deterministic; nothing is written.

Salli doesn't rank the options. A comparison reports:

- **Side by side:** each option's figures (`engine.run`), against one
  baseline, evaluated once.
- **The trade:** for each option against each other one, the figures where
  it comes out ahead (`gains`) and behind (`gives_up`), as deltas only: more
  cash, net worth or investments is ahead; fewer debts, less interest, a
  smaller FI number and earlier months are ahead. Never an overall verdict.
- **Sensitivity:** the same options under the conservative and growth real
  returns (the base return less and plus the spread, or the FIRE strategy's
  own three; `fi.assumptions`). Cash earns nothing, so only the monthly
  figures and FI move.
- **Break-evens,** solved exactly by bisection on whole numbers of the
  currency's smallest unit or of a basis point (0.0001), so deterministic;
  or "none in range":
  - the real return at which investing beats paying extra on a debt, where
    one option invests and the other pays a debt down instead: the lowest
    return in the range (-5% to 15%) at which the investing option's net
    worth at the horizon is at least the other's;
  - the most a recurring cost can be, each time, with cash staying at or
    above zero over the next twelve months (`engine.cash_floors`);
  - the rate at which two financing options cost the same: the highest
    rate (0% to 100%) at which an option's loan leaves it with at least the
    other option's net worth at the horizon;
  - the growth at which buying an asset ends level, where an option buys
    one the other doesn't (`asset`, a home): the lowest real growth of its
    value (-5% to 10% a year) at which the option ends the horizon with at
    least the other's net worth.

And a reading, not solved: the first month-end from which one option's net
worth is at least another's at every month-end to the horizon
(`level_from`), read from the monthly timelines as `engine.cover_target`
reads cash.

Options share one as-of date and one horizon, and are named by their label
(or "Option n", by position, without one); labels are distinct. The result
doesn't depend on the order the options come in: each option's figures, its
trade with each other, and the break-evens are the same whichever order.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from salli.domain import canonical
from salli.domain.baseline import fi, timelines
from salli.domain.baseline.models import Baseline
from salli.domain.currency import quantum
from salli.domain.scenarios import schema
from salli.domain.scenarios.engine import (
    BreakEven,
    Figure,
    MonthFigure,
    Outlook,
    ScenarioError,
    ScenarioResult,
    baseline_outlook,
    run,
    search_last_true,
    translate,
)
from salli.domain.taxrules.common import Problem, join_path

MIN_OPTIONS = 2
MAX_OPTIONS = 5
#: The precision rates are solved to: a basis point.
RATE_STEP = Decimal("0.0001")
#: The real returns the debt-or-invest break-even is looked for between: the
#: plausible range of a real return (fi.assumptions.BOUNDS).
RETURN_RANGE = (Decimal("-0.05"), Decimal("0.15"))
#: The loan rates the financing break-even is looked for between.
LOAN_RATE_RANGE = (Decimal(0), Decimal(1))
#: The real growths of an asset's value the growth break-even is looked for
#: between, a year beyond inflation.
ASSET_GROWTH_RANGE = (Decimal("-0.05"), Decimal("0.10"))

Better = Literal["higher", "lower", "earlier"]


@dataclass(frozen=True)
class Delta:
    """One figure where two options differ: this option's value, the other's,
    and this less the other (in months, for a month)."""

    figure: str
    this: Decimal | str | None
    other: Decimal | str | None
    delta: Decimal | int | None


@dataclass(frozen=True)
class Trade:
    option: str
    against: str
    gains: tuple[Delta, ...]
    gives_up: tuple[Delta, ...]


@dataclass(frozen=True)
class Sensitive:
    """An option's long-run figures under one real return."""

    net_worth: Figure
    investments: Figure
    fi_month: MonthFigure
    months_gained: int | None


@dataclass(frozen=True)
class OptionSensitivity:
    option: str
    #: Under the conservative, base and growth real returns.
    by_return: tuple[tuple[str, Sensitive], ...]


@dataclass(frozen=True)
class Comparison:
    as_of: str
    horizon_years: int
    currency: str
    #: The options' labels, in the order given.
    labels: tuple[str, ...]
    options: tuple[ScenarioResult, ...]
    trade: tuple[Trade, ...]
    #: The real returns sensitivity uses: conservative, base and growth.
    real_returns: tuple[tuple[str, Decimal], ...]
    sensitivity: tuple[OptionSensitivity, ...]
    break_evens: tuple[BreakEven, ...]


# ── The options ──────────────────────────────────────────────────────────────


def _check(baseline: Baseline, scenarios: Sequence[schema.Scenario]) -> list[str]:
    problems: list[Problem] = []
    if not MIN_OPTIONS <= len(scenarios) <= MAX_OPTIONS:
        problems.append(
            Problem(
                "options", f"compares {MIN_OPTIONS} to {MAX_OPTIONS} options, not {len(scenarios)}"
            )
        )
        raise ScenarioError(problems)
    labels = [s.label or f"Option {i + 1}" for i, s in enumerate(scenarios)]
    seen: dict[str, int] = {}
    for i, label in enumerate(labels):
        if label in seen:
            problems.append(
                Problem(
                    join_path("options", i, "label"),
                    f"{label!r} is already option {seen[label] + 1}'s: give each option its own label",
                )
            )
        seen.setdefault(label, i)
    horizon = scenarios[0].horizon_years
    for i, s in enumerate(scenarios):
        if s.as_of is not None and s.as_of != baseline.as_of:
            problems.append(
                Problem(
                    join_path("options", i, "as_of"),
                    f"is not the comparison's as-of date ({baseline.as_of}): options share one",
                )
            )
        if s.horizon_years != horizon:
            problems.append(
                Problem(
                    join_path("options", i, "horizon_years"),
                    f"is {s.horizon_years}, the first option's is {horizon}: options are "
                    "compared over one horizon",
                )
            )
    if problems:
        raise ScenarioError(problems)
    return labels


def _labelled(scenario: schema.Scenario, label: str) -> schema.Scenario:
    return scenario if scenario.label == label else scenario.model_copy(update={"label": label})


# ── The trade ────────────────────────────────────────────────────────────────


def headline(result: ScenarioResult) -> list[tuple[str, Better, Decimal | str | None]]:
    """The figures the trade weighs, with which way is ahead, under the
    scenario."""
    out: list[tuple[str, Better, Decimal | str | None]] = []

    def add(name: str, better: Better, value: Decimal | str | None) -> None:
        out.append((name, better, value))

    add("cash.lowest", "higher", result.cash.lowest.scenario)
    add("cash.safe_to_spend", "higher", result.cash.safe_to_spend.scenario)
    add("resilience.lowest", "higher", result.resilience.lowest.scenario)
    for c in result.monthly:
        at = f"monthly.{c.years}y"
        add(f"{at}.net_worth", "higher", c.net_worth.scenario)
        add(f"{at}.cash", "higher", c.cash.scenario)
        add(f"{at}.investments", "higher", c.investments.scenario)
        add(f"{at}.other_assets", "higher", c.other_assets.scenario)
        add(f"{at}.debts", "lower", c.debts.scenario)
    add("debts.total_interest", "lower", result.debts.total_interest.scenario)
    add("debts.debt_free", "earlier", result.debts.debt_free.scenario)
    add("fi.fi_number", "lower", result.fi.fi_number.scenario)
    add("fi.fi_month", "earlier", result.fi.fi_month.scenario)
    return out


def _versus(
    name: str, better: Better, this: Decimal | str | None, other: Decimal | str | None
) -> tuple[int, Delta] | None:
    """(1 ahead, -1 behind) and the delta, or None where they are the same."""
    if this == other:
        return None
    if better == "earlier":
        # A month within 50 years is ahead of none.
        if this is None or other is None:
            return (1 if other is None else -1), Delta(name, this, other, None)
        assert isinstance(this, str) and isinstance(other, str)
        months = timelines.month_index(this) - timelines.month_index(other)
        return (1 if months < 0 else -1), Delta(name, this, other, months)
    if this is None or other is None:
        return None
    assert isinstance(this, Decimal) and isinstance(other, Decimal)
    delta = this - other
    ahead = delta > 0 if better == "higher" else delta < 0
    return (1 if ahead else -1), Delta(name, this, other, delta)


def trade(results: Sequence[ScenarioResult], labels: Sequence[str]) -> list[Trade]:
    """Each option against each other one: where it is ahead and behind."""
    figures = [headline(r) for r in results]
    out: list[Trade] = []
    for i, mine in enumerate(figures):
        for j, theirs in enumerate(figures):
            if i == j:
                continue
            gains: list[Delta] = []
            gives_up: list[Delta] = []
            for (name, better, this), (_, _, other) in zip(mine, theirs, strict=True):
                found = _versus(name, better, this, other)
                if found is None:
                    continue
                (gains if found[0] > 0 else gives_up).append(found[1])
            out.append(Trade(labels[i], labels[j], tuple(gains), tuple(gives_up)))
    return out


# ── Sensitivity ──────────────────────────────────────────────────────────────


def sensitivity(
    baseline: Baseline,
    translated: Sequence[tuple[timelines.Changes, Decimal]],
    labels: Sequence[str],
    horizon_years: int,
) -> tuple[tuple[tuple[str, Decimal], ...], list[OptionSensitivity]]:
    """Each option's net worth and investments at the horizon and its FI
    month, against the baseline's, under each of the three real returns."""
    returns = tuple(baseline.assumptions.real_returns.as_dict().items())
    at = 12 * horizon_years + 1
    base_number = fi.fi_number(baseline)
    bases = {name: fi.full_timeline(baseline, real_return=rate) for name, rate in returns}
    out: list[OptionSensitivity] = []
    for (changes, spending), label in zip(translated, labels, strict=True):
        number = fi.fi_number(baseline, spending)
        rows: list[tuple[str, Sensitive]] = []
        for name, rate in returns:
            base, mine = bases[name], fi.full_timeline(baseline, changes, real_return=rate)
            b_fi = fi.months_to_fi(base.points, base_number)
            s_fi = fi.months_to_fi(mine.points, number)
            rows.append(
                (
                    name,
                    Sensitive(
                        net_worth=Figure(base.points[at].net_worth, mine.points[at].net_worth),
                        investments=Figure(
                            base.points[at].investments, mine.points[at].investments
                        ),
                        fi_month=MonthFigure(
                            fi.fi_month(baseline, b_fi), fi.fi_month(baseline, s_fi)
                        ),
                        months_gained=None if b_fi is None or s_fi is None else b_fi - s_fi,
                    ),
                )
            )
        out.append(OptionSensitivity(label, tuple(rows)))
    return returns, out


# ── Break-evens between two options ──────────────────────────────────────────


def _distinct(mine: schema.Scenario, theirs: schema.Scenario) -> list[tuple[int, schema.Change]]:
    """The changes in `mine` that `theirs` doesn't have, with their index."""
    others = {canonical.dumps(c) for c in theirs.changes}
    return [(i, c) for i, c in enumerate(mine.changes) if canonical.dumps(c) not in others]


def _steps(low: Decimal, high: Decimal) -> int:
    return int((high - low) / RATE_STEP)


def _net_worth(
    baseline: Baseline,
    scenario: schema.Scenario,
    *,
    real_return: Decimal | None = None,
) -> Decimal:
    """Net worth at the scenario's horizon, in today's money."""
    months = timelines.periods(baseline.as_of, timelines.horizon_months(scenario.horizon_years))
    changes = translate(baseline, scenario, until=months[-1].end).changes
    timeline = timelines.monthly(baseline, scenario.horizon_years, changes, real_return=real_return)
    return timeline.points[-1].net_worth


def invest_vs_debt(
    baseline: Baseline, invest: tuple[str, schema.Scenario], debt: tuple[str, schema.Scenario]
) -> BreakEven:
    """The lowest real return (to a basis point, from -5% to 15%) at which the
    investing option's net worth at the horizon is at least the other's."""
    low, high = RETURN_RANGE

    def rate(n: int) -> Decimal:
        return low + RATE_STEP * n

    def investing_behind(n: int) -> bool:
        r = rate(n)
        return _net_worth(baseline, invest[1], real_return=r) < _net_worth(
            baseline, debt[1], real_return=r
        )

    last_behind = search_last_true(0, _steps(low, high), investing_behind)
    pair = tuple(sorted((invest[0], debt[0])))
    if last_behind is None:
        return BreakEven(
            "invest_vs_debt_return",
            pair,
            invest[0],
            None,
            "none_in_range",
            None,
            low,
            high,
            invest[0],
        )
    if last_behind == _steps(low, high):
        return BreakEven(
            "invest_vs_debt_return",
            pair,
            invest[0],
            None,
            "none_in_range",
            None,
            low,
            high,
            debt[0],
        )
    return BreakEven(
        "invest_vs_debt_return", pair, invest[0], None, "found", rate(last_behind + 1), low, high
    )


def loan_rate(
    baseline: Baseline,
    option: tuple[str, schema.Scenario],
    index: int,
    other: tuple[str, schema.Scenario],
) -> BreakEven:
    """The highest rate (to a basis point, from 0% to 100%) at which `option`'s
    loan (its change `index`) leaves it with at least `other`'s net worth at
    the horizon: where the two cost the same."""
    low, high = LOAN_RATE_RANGE
    target = _net_worth(baseline, other[1])
    loan = option[1].changes[index]
    assert isinstance(loan, schema.LoanChange)

    def costs_no_more(n: int) -> bool:
        changes = list(option[1].changes)
        changes[index] = loan.model_copy(update={"annual_rate": low + RATE_STEP * n})
        trial = option[1].model_copy(update={"changes": changes})
        return _net_worth(baseline, trial) >= target

    found = search_last_true(0, _steps(low, high), costs_no_more)
    pair = tuple(sorted((option[0], other[0])))
    if found is None:
        return BreakEven(
            "loan_rate", pair, option[0], index, "none_in_range", None, low, high, other[0]
        )
    if found == _steps(low, high):
        return BreakEven(
            "loan_rate", pair, option[0], index, "none_in_range", None, low, high, option[0]
        )
    return BreakEven(
        "loan_rate", pair, option[0], index, "found", low + RATE_STEP * found, low, high
    )


def asset_growth(
    baseline: Baseline,
    option: tuple[str, schema.Scenario],
    index: int,
    other: tuple[str, schema.Scenario],
) -> BreakEven:
    """The lowest real growth (to a basis point, from -5% to 10% a year) of
    the value of `option`'s asset (its change `index`) at which `option`
    ends the horizon with at least `other`'s net worth. A higher growth
    never lowers the option's net worth, so bisection finds it exactly."""
    low, high = ASSET_GROWTH_RANGE
    target = _net_worth(baseline, other[1])
    asset = option[1].changes[index]
    assert isinstance(asset, schema.AssetChange)

    def behind(n: int) -> bool:
        changes = list(option[1].changes)
        changes[index] = asset.model_copy(update={"real_growth": low + RATE_STEP * n})
        trial = option[1].model_copy(update={"changes": changes})
        return _net_worth(baseline, trial) < target

    steps = _steps(low, high)
    last_behind = search_last_true(0, steps, behind)
    pair = tuple(sorted((option[0], other[0])))
    if last_behind is None:
        return BreakEven(
            "asset_growth", pair, option[0], index, "none_in_range", None, low, high, option[0]
        )
    if last_behind == steps:
        return BreakEven(
            "asset_growth", pair, option[0], index, "none_in_range", None, low, high, other[0]
        )
    return BreakEven(
        "asset_growth",
        pair,
        option[0],
        index,
        "found",
        low + RATE_STEP * (last_behind + 1),
        low,
        high,
    )


def level_from(
    mine: Sequence[timelines.MonthPoint],
    other: Sequence[timelines.MonthPoint],
    first: str,
    last: str,
    currency: str,
) -> timelines.MonthPoint | None:
    """Of `mine` (a monthly timeline), the first month-end from the month
    `first` ("YYYY-MM") on from which its net worth is at least `other`'s at
    every month-end to the month `last`, each in today's money to the
    currency's smallest unit: read, not solved. None when it is behind at
    `last`'s end (or `first` is after `last`)."""
    q = quantum(currency)

    def at_least(a: timelines.MonthPoint, b: timelines.MonthPoint) -> bool:
        return a.net_worth.quantize(q, rounding=ROUND_HALF_UP) >= b.net_worth.quantize(
            q, rounding=ROUND_HALF_UP
        )

    # Month-ends only: the first point is the as-of date itself.
    pairs = [(a, b) for a, b in zip(mine[1:], other[1:], strict=True) if first <= a.month <= last]
    found: timelines.MonthPoint | None = None
    for a, b in reversed(pairs):
        if not at_least(a, b):
            break
        found = a
    return found


def pairwise(baseline: Baseline, options: Sequence[tuple[str, schema.Scenario]]) -> list[BreakEven]:
    """The break-evens between each two options that differ the way each one
    needs."""
    out: list[BreakEven] = []
    ordered = sorted(options, key=lambda o: o[0])
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            a_only, b_only = _distinct(a[1], b[1]), _distinct(b[1], a[1])

            def has(changes: list[tuple[int, schema.Change]], kind: type) -> bool:
                return any(isinstance(c, kind) for _, c in changes)

            if has(a_only, schema.InvestChange) and has(b_only, schema.ExtraDebtPaymentChange):
                out.append(invest_vs_debt(baseline, a, b))
            elif has(b_only, schema.InvestChange) and has(a_only, schema.ExtraDebtPaymentChange):
                out.append(invest_vs_debt(baseline, b, a))
            for mine, theirs, distinct in ((a, b, a_only), (b, a, b_only)):
                loans = [i for i, c in distinct if isinstance(c, schema.LoanChange)]
                if len(loans) == 1:
                    out.append(loan_rate(baseline, mine, loans[0], theirs))
                assets = [i for i, c in distinct if isinstance(c, schema.AssetChange)]
                if len(assets) == 1:
                    out.append(asset_growth(baseline, mine, assets[0], theirs))
    return out


def _order(b: BreakEven) -> tuple[str, tuple[str, ...], str, int]:
    return (b.kind, b.options, b.option or "", -1 if b.change is None else b.change)


# ── Comparing ────────────────────────────────────────────────────────────────


def compare(baseline: Baseline, scenarios: Sequence[schema.Scenario]) -> Comparison:
    """The options side by side, the trade between each two, their
    sensitivity to the real return, and the break-evens (see the module).
    ScenarioError with every problem found."""
    labels = _check(baseline, scenarios)
    options = [_labelled(s, label) for s, label in zip(scenarios, labels, strict=True)]
    problems: list[Problem] = []
    for i, s in enumerate(options):
        try:
            translate(baseline, s)
        except ScenarioError as error:
            problems += [
                Problem(join_path("options", i, p.path), p.message) for p in error.problems
            ]
    if problems:
        raise ScenarioError(problems)

    base: Outlook = baseline_outlook(baseline)
    results = [run(baseline, s, base=base) for s in options]
    translated = [(t.changes, t.spending) for t in (translate(baseline, s) for s in options)]
    horizon = options[0].horizon_years
    returns, sensitive = sensitivity(baseline, translated, labels, horizon)
    floors = [b for r in results for b in r.break_evens]
    between = pairwise(baseline, list(zip(labels, options, strict=True)))
    return Comparison(
        as_of=baseline.as_of.isoformat(),
        horizon_years=horizon,
        currency=baseline.currency,
        labels=tuple(labels),
        options=tuple(results),
        trade=tuple(trade(results, labels)),
        real_returns=returns,
        sensitivity=tuple(sensitive),
        break_evens=tuple(sorted([*floors, *between], key=_order)),
    )


__all__ = [
    "ASSET_GROWTH_RANGE",
    "LOAN_RATE_RANGE",
    "MAX_OPTIONS",
    "MIN_OPTIONS",
    "RATE_STEP",
    "RETURN_RANGE",
    "Comparison",
    "Delta",
    "OptionSensitivity",
    "Sensitive",
    "Trade",
    "asset_growth",
    "compare",
    "headline",
    "invest_vs_debt",
    "level_from",
    "loan_rate",
    "pairwise",
    "sensitivity",
    "trade",
]
