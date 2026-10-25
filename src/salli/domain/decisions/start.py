"""
Starting a decision from a template: one result an agent (or a person) can
explain, and record from in one step. Pure; nothing is stored.

`start(baseline, template, answers, built, principles)` takes the options a
template built (`templates.build`) and runs them as any options are run:

- **the comparison** (`comparison.compare`): each option's figures, the
  trade between each two, the sensitivity to the real return, and the
  break-evens, as `POST /v1/scenarios/compare` gives them;
- **the principles**: which of the person's principles the baseline and each
  option keep, break or can't tell, as `POST /v1/principles/check` gives
  them;
- **the time to a cash target**, for a template that asks for one (the
  emergency fund): the month cash, in today's money, first covers the
  target under the baseline and under each option, read from the monthly
  timeline (`engine.cover_target`);
- **when an option draws level**, for a template that asks (rent or buy):
  the first month-end, from the purchase on, from which each option's net
  worth is at least the other's (keeping renting's) at every month-end to
  the horizon, read from the monthly timelines (`comparison.level_from`);
- **what recording needs**: the question (a suggestion, the person's to
  change), each option's scenario with its as-of date, and the labels one
  of which is chosen. Recording stays `record_decision` (or `POST
  /v1/decisions`), with the person's choice, their reasons in their words
  and a review date, and only once they confirm.

Like everything in the decision lab, it never ranks: no option is called
best, recommended or preferred, and nothing is counted or scored.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from salli.domain.baseline import timelines
from salli.domain.baseline.models import Baseline
from salli.domain.decisions import figures as figure_set
from salli.domain.decisions import journal, review
from salli.domain.decisions.templates import Answers, Built, Level, Template, answers_view
from salli.domain.fi import montecarlo
from salli.domain.fi.assumptions import real_return
from salli.domain.scenarios import comparison, engine, views

START_SCHEMA = "salli.decision-start/1"

_HUNDREDTH = Decimal("0.01")

#: What every start says, so the reader knows how to take it.
SAYS = (
    "Salli computed every figure here and ranks none of the options: what matters most is "
    "the person's to weigh. To record what they choose, call record_decision (POST "
    "/v1/decisions) with `record.question` (theirs to change), `record.options`, the label "
    "they chose, their reasons in their own words and a review date, once they confirm."
)


def _months(value: Decimal | None) -> str | None:
    return None if value is None else str(value.quantize(_HUNDREDTH, rounding=ROUND_HALF_UP))


def _cover_view(
    baseline: Baseline,
    target_months: Decimal,
    base: engine.Outlook,
    options: Sequence[tuple[str, engine.Outlook]],
) -> dict[str, Any]:
    readings = [
        (label, engine.cover_target(baseline, base, mine, target_months)) for label, mine in options
    ]
    first = engine.cover_target(baseline, base, base, target_months)
    cur = baseline.currency
    return {
        "target_months": format(target_months, "f"),
        "basis": first.basis,
        "monthly_spending": views.money_text(first.monthly_spending, cur),
        "target": views.money_text(first.target, cur),
        "now": _months(first.now),
        "baseline": {"month": first.reached.baseline, "months": first.months[0]},
        "options": [
            {
                "option": label,
                "month": reading.reached.scenario,
                "months": reading.months[1],
                "delta_months": reading.reached.delta,
            }
            for label, reading in readings
        ],
        "says": (
            "The first month at whose end cash, in today's money, covers the target; "
            "null when it doesn't within 50 years. Cash covers `now` months today."
        ),
    }


def _level_view(
    baseline: Baseline,
    level: Level,
    horizon_years: int,
    options: Sequence[tuple[str, engine.Outlook]],
) -> dict[str, Any]:
    by_label = dict(options)
    against = by_label[level.against].monthly.points
    points = 12 * horizon_years + 2
    last = against[points - 1].month
    cur = baseline.currency
    readings: list[dict[str, Any]] = []
    for label, mine in options:
        if label == level.against:
            continue
        found = comparison.level_from(
            mine.monthly.points[:points], against[:points], level.from_month, last, cur
        )
        other = None if found is None else next(p for p in against if p.month == found.month)
        end_mine, end_other = mine.monthly.points[points - 1], against[points - 1]
        readings.append(
            {
                "option": label,
                "month": None if found is None else found.month,
                "months": None
                if found is None
                else timelines.month_index(found.month) - timelines.month_index(level.from_month),
                "net_worth_then": None
                if found is None or other is None
                else views.money_text(found.net_worth - other.net_worth, cur),
                "net_worth_at_horizon": views.money_text(
                    end_mine.net_worth - end_other.net_worth, cur
                ),
            }
        )
    return {
        "against": level.against,
        "from": level.from_month,
        "to": last,
        "options": readings,
        "says": (
            f"The first month-end from {level.from_month} on from which the option's net worth, "
            f"in today's money, is at least {level.against}'s at every month-end to {last}; "
            "null when it is behind at the horizon. `months` counts from the purchase's month, "
            f"and the net worth figures are the option's less {level.against}'s."
        ),
    }


def _placeholders(results: Sequence[engine.ScenarioResult], built: Built) -> list[str]:
    """What any option's figures rest on: each option's placeholders (the
    first's first), and the template's own."""
    return list(dict.fromkeys([*(p for r in results for p in r.placeholders), *built.placeholders]))


def _odds_view(baseline: Baseline, debt_id: str, years: int) -> dict[str, Any] | None:
    """How often investing beats paying down `debt_id` over `years`, under
    the Monte Carlo: the debt's rate is certain, the return is not."""
    debt = next((d for d in baseline.debts if d.debt_id == debt_id), None)
    if debt is None:
        return None
    applied = baseline.assumptions
    inflation = baseline.inflation
    real_rate = debt.apr if inflation is None else real_return(debt.apr, inflation)
    share = montecarlo.beats(
        applied.real_return.value,
        applied.cma.volatility,
        years * 12,
        real_rate,
        tails=applied.cma.tails,
    )
    return {
        "debt": debt_id,
        "debt_real_rate": f"{real_rate.quantize(Decimal('0.0001')).normalize():f}",
        "months": years * 12,
        "paths": montecarlo.DEFAULT_PATHS,
        "seed": montecarlo.DEFAULT_SEED,
        "invest_beats_paying_down": f"{share.normalize():f}" if share else "0",
        "says": (
            "The share of simulated return paths on which the money invested grows by more, "
            f"over {years} years, than paying down the debt saves at its rate"
            + (" (after your inflation)" if inflation is not None else " (inflation not set)")
            + ". Paying down is certain; investing is not. Not a forecast."
        ),
    }


def start(
    baseline: Baseline,
    template: Template,
    answers: Answers,
    built: Built,
    principles: Sequence[journal.PrincipleInUse] = (),
) -> dict[str, Any]:
    """The template's options compared, checked against the principles and,
    for a cash target, read for when cash reaches it; with what recording
    needs. Stores nothing."""
    scenarios = [o.scenario for o in built.options]
    compared = comparison.compare(baseline, scenarios)
    base = engine.baseline_outlook(baseline)
    evaluated: list[tuple[str, engine.Evaluated, figure_set.Figures]] = []
    for option in built.options:
        _, done = engine.run_with_outlook(baseline, option.scenario, base=base)
        figures = figure_set.compute(
            baseline, done.outlook, base, done.translation.changes.loans, done.translation.tax
        )
        evaluated.append((option.label, done, figures))
    base_figures = figure_set.compute(baseline, base, base)

    def block(figures: figure_set.Figures) -> dict[str, Any]:
        return {
            "figures": figure_set.view(figures),
            "unavailable": dict(figures.missing),
            "results": journal.checks_view(principles, figures),
        }

    as_of = baseline.as_of
    filled = [s.model_copy(update={"as_of": as_of}) for s in scenarios]
    first = compared.options[0]
    return {
        "schema": START_SCHEMA,
        "template": {"id": template.id, "title": template.title},
        "as_of": as_of.isoformat(),
        "currency": baseline.currency,
        "horizon_years": compared.horizon_years,
        "question": built.question,
        "answers": answers_view(template, answers),
        "options": [
            {
                "label": option.label,
                "describes": option.describes,
                "scenario": scenario.model_dump(mode="json", by_alias=True, exclude_none=True),
                "scenario_hash": result.hash,
            }
            for option, scenario, result in zip(
                built.options, filled, compared.options, strict=True
            )
        ],
        "comparison": views.comparison_view(compared),
        "principles": {
            "principles": [p.view() for p in principles],
            "baseline": block(base_figures),
            "options": [
                {"label": label, "scenario_hash": done.result.hash, **block(figures)}
                for label, done, figures in evaluated
            ],
        },
        "cover": None
        if built.cover_months is None
        else _cover_view(
            baseline,
            built.cover_months,
            base,
            [(label, done.outlook) for label, done, _ in evaluated],
        ),
        "level": None
        if built.level is None
        else _level_view(
            baseline,
            built.level,
            compared.horizon_years,
            [(label, done.outlook) for label, done, _ in evaluated],
        ),
        "odds": None
        if built.odds_against_debt is None
        else _odds_view(baseline, built.odds_against_debt, compared.horizon_years),
        "placeholders": _placeholders(compared.options, built),
        "data_as_of": first.data_as_of,
        "is_stale": first.is_stale,
        "notes": [*built.notes, *template.notes],
        "record": {
            "question": built.question,
            "options": [
                s.model_dump(mode="json", by_alias=True, exclude_none=True) for s in filled
            ],
            "labels": [o.label for o in built.options],
            "earliest_review": review.earliest_review(as_of).isoformat(),
        },
        "says": SAYS,
    }
