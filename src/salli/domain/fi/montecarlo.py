"""
The odds of a plan: a seeded Monte Carlo on the baseline's monthly timeline
(docs/baseline.md#the-odds). Pure, Decimal, in real terms; no model computes
or chooses any of it.

Each path draws a month's real return for the investments from a Student-t
distribution (fatter tails than a normal's: crashes and booms more often)
with the portfolio's expected yearly real return over twelve and its yearly
volatility over √12 (the active capital-market assumptions' mix, or the
labelled placeholder pack), scaled so its volatility is that one; its
degrees of freedom are the pack's (`degrees_of_freedom`, else the labelled
placeholder `cma.TAILS`). Draws come from Python's seeded generator, each
written to nine places as a Decimal, so the same seed gives the same figures
everywhere.

- **Building up**, to the retirement month: the investments grow at the
  path's returns and take what the timeline moves into them; cash, debts
  and other liabilities follow the timeline (they don't depend on markets).
- **Drawing down**, after it: the asset base is one pool at the path's
  returns, less each month's withdrawal: that month's spending to fund
  (`fi.need`, its phase's less guaranteed income) grossed up for tax on
  withdrawals beside the taxable guaranteed income paying then. A path succeeds when the pool never falls below zero by the
  horizon.
- **Odds of reaching**: the share of paths whose asset base reaches that
  month's FI number within the horizon, building up all the way.
- **Percentile paths**: the 10th, 50th and 90th percentile of the asset base
  across paths at each whole year.
- **A horizon-derived withdrawal rate**: for each path, the highest constant
  real withdrawal a year, as a share of the pool at retirement, that lasts
  the years drawn down (exactly 12 / Σₖ 1/Gₖ, Gₖ the growth to month k); the
  rate is the one that share of paths at the success level sustain.
- **Guardrails** (optional): a spending band. Each year after retirement, a
  withdrawal rate above the starting one by more than the band cuts spending
  by `adjust`; below it by more than the band raises it by `adjust`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from salli.domain.baseline import fi, timelines
from salli.domain.baseline.models import Baseline
from salli.domain.currency import quantize
from salli.domain.fi import cma
from salli.domain.fi.returns import (
    DEFAULT_PATHS,
    DEFAULT_SEED,
    DEFAULT_SUCCESS,
    DRAWDOWN_YEARS,
    ReturnSource,
    student_t,
)

MAX_PATHS = 5000
_TWELVE = Decimal(12)
_FLOOR = Decimal("-0.95")
_PERCENTILES = (Decimal("0.1"), Decimal("0.5"), Decimal("0.9"))


@dataclass(frozen=True)
class Guardrails:
    #: How far (a fraction of the starting rate) the withdrawal rate may
    #: move before spending is cut or raised.
    band: Decimal = Decimal("0.2")
    #: By how much (a fraction) spending is cut or raised.
    adjust: Decimal = Decimal("0.1")


@dataclass(frozen=True)
class YearBand:
    year: int
    p10: Decimal
    p50: Decimal
    p90: Decimal


@dataclass(frozen=True)
class GuardrailOdds:
    success: Decimal
    #: The share of paths that cut spending at least once.
    cut: Decimal
    #: The 10th percentile of the lowest spending reached, as a share of planned.
    low_spending_p10: Decimal


@dataclass(frozen=True)
class Odds:
    paths: int
    seed: int
    mean: Decimal
    volatility: Decimal
    horizon_months: int
    #: Months from the as-of month to retirement; None: building up only.
    retire: int | None
    #: The share of paths that never run out by the horizon; None without a
    #: retirement month.
    success: Decimal | None
    #: The share of paths that reach the FI number within the horizon.
    reach: Decimal
    years: tuple[YearBand, ...]
    #: The withdrawal rate sustained by `success_level` of paths over the
    #: years drawn down.
    horizon_rate: Decimal
    rate_years: int
    success_level: Decimal
    guardrails: GuardrailOdds | None = None


def draws(
    mean: Decimal,
    volatility: Decimal,
    months: int,
    paths: int,
    seed: int,
    tails: Decimal = cma.TAILS,
) -> list[list[Decimal]]:
    """`paths` sequences of `months` monthly real returns from a Student-t
    (`returns.student_t`)."""
    return student_t(mean, volatility, months, paths, seed, tails)


def _quantile(values: Sequence[Decimal], p: Decimal) -> Decimal:
    ordered = sorted(values)
    return ordered[int(p * (len(ordered) - 1))]


def _share(count: int, total: int) -> Decimal:
    return (Decimal(count) / Decimal(total)).quantize(Decimal("0.0001"))


def sustainable_rate(returns: Sequence[Decimal]) -> Decimal:
    """The highest constant yearly withdrawal, as a share of the starting
    pool, that `returns` (monthly, withdrawn at each month's end) sustain."""
    growth, total = Decimal(1), Decimal(0)
    for r in returns:
        growth *= Decimal(1) + r
        total += Decimal(1) / growth
    return _TWELVE / total if total > 0 else Decimal(0)


def run(
    baseline: Baseline,
    timeline: timelines.MonthlyTimeline,
    *,
    horizon_months: int,
    retire: int | None,
    mean: Decimal,
    volatility: Decimal,
    monthly_spending: Decimal | None = None,
    paths: int = DEFAULT_PATHS,
    seed: int = DEFAULT_SEED,
    success_level: Decimal = DEFAULT_SUCCESS,
    guardrails: Guardrails | None = None,
    tails: Decimal = cma.TAILS,
    source: ReturnSource | None = None,
) -> Odds:
    """The odds on `timeline` (a monthly timeline at least `horizon_months`
    long) for `paths` paths from `seed` (see the module)."""
    if not 1 <= paths <= MAX_PATHS:
        raise ValueError(f"paths is from 1 to {MAX_PATHS}")
    points = timeline.points
    horizon = min(horizon_months, len(points) - 1)
    if retire is not None and not 0 <= retire < horizon:
        raise ValueError("The retirement month must fall within the horizon")
    numbers = fi.fi_numbers(baseline, points, monthly_spending)
    held_out = fi.reserve(baseline)
    spend = fi.spending(baseline) if monthly_spending is None else monthly_spending
    levels = {p.month: p.deflator for p in points[1:]}
    # Each month's withdrawal, in today's money, grossed up for tax.
    withdrawals = [
        fi.gross_up(
            baseline,
            fi.need(baseline, p.month, spend, levels) * _TWELVE,
            fi.taxed_income(baseline, p.month, levels),
        )
        / _TWELVE
        for p in points[: horizon + 1]
    ]
    returns = (
        draws(mean, volatility, horizon, paths, seed, tails)
        if source is None
        else source.monthly(horizon, paths, seed)
    )

    reached = survived = 0
    by_year: list[list[Decimal]] = [[] for _ in range(horizon // 12 + 1)]
    rates: list[Decimal] = []
    guarded: list[tuple[bool, bool, Decimal]] = []
    for path in returns:
        investments = points[0].investments
        base = fi.asset_base(points[0], held_out)
        by_year[0].append(base)
        hit = base >= numbers[0] > 0
        pool: Decimal | None = None
        alive = True
        for t in range(1, horizon + 1):
            r = path[t - 1]
            point = points[t]
            investments = investments * (Decimal(1) + r) + point.invested / point.deflator
            if not hit and numbers[t] > 0:
                hit = fi.asset_base(point, held_out) - point.investments + investments >= numbers[t]
            if retire is None or t <= retire + 1:
                base = fi.asset_base(point, held_out) - point.investments + investments
                if retire is not None and t == retire + 1:
                    pool = base
            else:
                assert pool is not None
                pool = pool * (Decimal(1) + r) - withdrawals[t]
                base = pool
                if pool < 0:
                    alive = False
            if t % 12 == 0:
                by_year[t // 12].append(base)
        reached += hit
        survived += alive
        start = (retire + 1) if retire is not None else 0
        rates.append(sustainable_rate(path[start:]))
        if guardrails is not None and retire is not None and pool is not None:
            guarded.append(
                _guarded(path, retire, horizon, points, withdrawals, guardrails, held_out)
            )

    level = success_level
    years = tuple(
        YearBand(k, *(_quantile(values, p) for p in _PERCENTILES))
        for k, values in enumerate(by_year)
        if values
    )
    rails = None
    if guarded:
        rails = GuardrailOdds(
            success=_share(sum(ok for ok, _, _ in guarded), len(guarded)),
            cut=_share(sum(cut for _, cut, _ in guarded), len(guarded)),
            low_spending_p10=_quantile([low for _, _, low in guarded], Decimal("0.1")).quantize(
                Decimal("0.0001")
            ),
        )
    return Odds(
        paths=paths,
        seed=seed,
        mean=mean,
        volatility=volatility,
        horizon_months=horizon,
        retire=retire,
        success=None if retire is None else _share(survived, paths),
        reach=_share(reached, paths),
        years=years,
        horizon_rate=_quantile(rates, Decimal(1) - level).quantize(Decimal("0.0001")),
        rate_years=(horizon - (retire + 1 if retire is not None else 0)) // 12,
        success_level=level,
        guardrails=rails,
    )


def _guarded(
    path: Sequence[Decimal],
    retire: int,
    horizon: int,
    points: Sequence[timelines.MonthPoint],
    withdrawals: Sequence[Decimal],
    rails: Guardrails,
    held_out: Decimal,
) -> tuple[bool, bool, Decimal]:
    """One path drawn down with guardrails: whether it lasts, whether it
    cut spending, and the lowest share of planned spending it reached."""
    held = points[0].investments
    for t in range(1, retire + 2):
        point = points[t]
        held = held * (Decimal(1) + path[t - 1]) + point.invested / point.deflator
    pool = fi.asset_base(points[retire + 1], held_out) - points[retire + 1].investments + held
    factor = low = Decimal(1)
    start_rate: Decimal | None = None
    cut = False
    for t in range(retire + 2, horizon + 1):
        if (t - retire - 2) % 12 == 0 and pool > 0 and withdrawals[t] > 0:
            rate = withdrawals[t] * factor * _TWELVE / pool
            if start_rate is None:
                start_rate = rate
            elif rate > start_rate * (Decimal(1) + rails.band):
                factor *= Decimal(1) - rails.adjust
                cut = True
            elif rate < start_rate * (Decimal(1) - rails.band):
                factor *= Decimal(1) + rails.adjust
            low = min(low, factor)
        pool = pool * (Decimal(1) + path[t - 1]) - withdrawals[t] * factor
        if pool < 0:
            return False, cut, low
    return True, cut, low


def beats(
    mean: Decimal,
    volatility: Decimal,
    months: int,
    yearly_rate: Decimal,
    *,
    paths: int = DEFAULT_PATHS,
    seed: int = DEFAULT_SEED,
    tails: Decimal = cma.TAILS,
    source: ReturnSource | None = None,
) -> Decimal:
    """The share of paths on which money invested for `months` grows by more
    than paying down a debt at `yearly_rate` (real, compounded monthly) saves.
    Only the growth at the end matters here, so each path draws a year's
    return at a time (mean `mean`, volatility `volatility`), the months past
    the last whole year at their share of one."""
    if months <= 0:
        return Decimal(0)
    target = (Decimal(1) + yearly_rate / _TWELVE) ** months
    years, rest = divmod(months, 12)
    wins = 0
    if source is not None and source.method == "bootstrap":
        # Each year the growth of twelve resampled months.
        yearly = [
            [_compound(path[12 * k : 12 * k + 12]) for k in range(years + 1)]
            for path in source.monthly(12 * (years + 1), paths, seed)
        ]
    else:
        yearly = draws(mean * _TWELVE, volatility * _TWELVE.sqrt(), years + 1, paths, seed, tails)
    for path in yearly:
        growth = Decimal(1)
        for r in path[:years]:
            growth *= Decimal(1) + r
        if rest:
            growth *= Decimal(1) + path[years] * Decimal(rest) / _TWELVE
        wins += growth > target
    return _share(wins, paths)


def _compound(months: Sequence[Decimal]) -> Decimal:
    growth = Decimal(1)
    for r in months:
        growth *= Decimal(1) + r
    return growth - 1


# ── As the API answers ───────────────────────────────────────────────────────


def source_says(source: ReturnSource) -> str:
    """Where the odds' returns come from, in a sentence."""
    where = {
        "user": "your own return and volatility",
        "pack": "your capital-market assumptions' mix (its return and volatility)",
        "placeholder": "the placeholder pack's return and volatility",
    }[source.origin]
    how = (
        "resampling a year's window of the pack's monthly history at a time"
        if source.method == "bootstrap"
        else "Student-t draws"
    )
    fee = (
        f", less your holdings' weighted expense ratio of {source.expense_ratio.normalize():f}"
        if source.expense_ratio
        else ""
    )
    return f"Returns from {where}{fee}, by {how}."


def _months_between(first: str, last: str) -> int:
    return (int(last[:4]) - int(first[:4])) * 12 + int(last[5:7]) - int(first[5:7])


def plan_odds(
    baseline: Baseline,
    *,
    changes: timelines.Changes = timelines.NO_CHANGES,
    monthly_spending: Decimal | None = None,
    retire_month: str | None = None,
    horizon_years: int = timelines.MAX_HORIZON_YEARS,
    paths: int = DEFAULT_PATHS,
    seed: int = DEFAULT_SEED,
    success_level: Decimal = DEFAULT_SUCCESS,
    guardrails: Guardrails | None = None,
) -> dict[str, object]:
    """The odds of the baseline's plan (with a scenario's `changes` and
    spending), retiring in `retire_month` ("YYYY-MM"; the FI month when
    None), to `horizon_years`: the figures every surface shows. A
    ValueError for a retirement month outside the horizon."""
    timeline = fi.full_timeline(baseline, changes)
    outlook = fi.outlook(baseline, timeline, monthly_spending)
    first = baseline.as_of.isoformat()[:7]
    horizon = timelines.horizon_months(horizon_years) - 1
    retire = outlook.months if retire_month is None else _months_between(first, retire_month)
    if retire is not None and not 0 <= retire < horizon:
        if retire_month is not None:
            raise ValueError(f"retire_month must fall from {first} to before the horizon's end")
        retire = None
    applied = baseline.assumptions
    pack = applied.cma
    source = applied.odds
    odds = run(
        baseline,
        timeline,
        horizon_months=horizon,
        retire=retire,
        mean=source.mean,
        volatility=source.volatility,
        monthly_spending=monthly_spending,
        paths=paths,
        seed=seed,
        success_level=success_level,
        guardrails=guardrails,
        tails=source.tails,
        source=source,
    )
    currency = baseline.currency

    def money(value: Decimal) -> str:
        return str(quantize(value, currency, strict=False))

    def share(value: Decimal) -> str:
        return f"{value.normalize():f}" if value else "0"

    placeholders = [
        *baseline.placeholders,
        *(["volatility"] if source.origin == "placeholder" else []),
        *(
            ["degrees_of_freedom"]
            if source.method == "student_t" and pack.degrees_of_freedom is None
            else []
        ),
    ]
    return {
        "currency": currency,
        "as_of": baseline.as_of.isoformat(),
        "paths": odds.paths,
        "seed": odds.seed,
        "horizon_years": horizon_years,
        "real_return": share(odds.mean),
        "volatility": share(odds.volatility.quantize(Decimal("0.0001"))),
        "returns": {
            "origin": source.origin,
            "method": source.method,
            "expense_ratio": share(source.expense_ratio),
            "says": source_says(source),
        },
        "cma": cma.summary(pack),
        "fi_number": money(outlook.fi_number),
        "fi_month": outlook.month,
        "retire_month": None if retire is None else fi.fi_month(baseline, retire),
        "success": None if odds.success is None else share(odds.success),
        "reach": share(odds.reach),
        "withdrawal_rate": {
            "applied": share(applied.safe_withdrawal_rate.value),
            "origin": applied.safe_withdrawal_rate.origin,
            "applied_years": None
            if applied.safe_withdrawal_rate.origin == "user"
            else DRAWDOWN_YEARS,
            "horizon_derived": share(odds.horizon_rate),
            "years": odds.rate_years,
            "success_level": share(success_level),
        },
        "guardrails": None
        if guardrails is None or odds.guardrails is None
        else {
            "band": share(guardrails.band),
            "adjust": share(guardrails.adjust),
            "success": share(odds.guardrails.success),
            "cut": share(odds.guardrails.cut),
            "low_spending_p10": share(odds.guardrails.low_spending_p10),
        },
        "percentiles": [
            {"year": y.year, "p10": money(y.p10), "p50": money(y.p50), "p90": money(y.p90)}
            for y in odds.years
        ],
        "withdrawal_tax": fi.withdrawal_tax(baseline),
        "placeholders": placeholders,
        "message": (
            "Odds from a seeded simulation of returns, not a forecast: "
            + (
                "some figures are placeholders (`placeholders`). "
                if placeholders
                else "on your own assumptions. "
            )
            + "The same seed always gives the same figures."
        ),
    }
