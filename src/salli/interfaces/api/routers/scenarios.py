"""
Scenarios — `/v1/scenarios/run` and `/v1/scenarios/compare`.

The decision lab's what-ifs (domain/scenarios, docs/scenarios.md): a
`salli.scenario/1` document is the baseline plus changes, and Salli reports
every figure under the baseline and under the scenario, with the delta. A
comparison puts two to five options side by side, with the trade between
each two, their sensitivity to the real return and the break-evens. Salli
never ranks them.

Both store nothing. Every account and debt a change names must be the
caller's own: anything else is 404 not found, the same for one that doesn't
exist and one that is someone else's. A document Salli can't run is a 422
problem whose `detail` lists each problem with its path.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from salli.domain.scenarios.schema import Scenario
from salli.interfaces.api.contract import Amount, CurrencyCode, DecimalOut
from salli.interfaces.api.deps import AppServices, CurrentUser
from salli.interfaces.api.routers.fi import FiAssumptions

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

Month = str  # "YYYY-MM"
Day = str  # "YYYY-MM-DD"

_NOT_FOUND = {
    404: {"description": "An account, a debt or a holding a change names is not one of yours"},
}


class AmountFigure(BaseModel):
    """A money figure under the baseline and under the scenario, and the
    scenario less the baseline."""

    baseline: Amount | None
    scenario: Amount | None
    delta: Amount | None


class MonthsFigure(BaseModel):
    """Months of spending covered ("8.29"), under each, and the delta."""

    baseline: DecimalOut | None
    scenario: DecimalOut | None
    delta: DecimalOut | None


class MonthFigure(BaseModel):
    """A calendar month under each (null: not within 50 years), and how many
    months later the scenario's is (negative: sooner)."""

    baseline: Month | None
    scenario: Month | None
    delta_months: int | None


class DayFigure(BaseModel):
    baseline: Day
    scenario: Day
    delta_days: int


class ScenarioStopped(BaseModel):
    """A recurring flow a stop stops: each time, signed."""

    payee: str
    cadence: str
    amount: Amount
    currency: CurrencyCode


class ScenarioPriceBasis(BaseModel):
    """The price a trade rests on: the holding's last price recorded on or
    before the as-of date. Salli forecasts no price: a trade in a later
    month is at it grown at your real return and inflation (`grown`)."""

    date: Day
    #: "user" for a close you recorded; "trade" for one of the holding's own.
    source: str
    #: As recorded, per unit, in the holding's currency.
    price: DecimalOut
    grown: bool
    #: Older than 45 days before the as-of date.
    stale: bool


class ScenarioLotSold(BaseModel):
    """The part of one lot a sale sells."""

    lot_id: str
    opened_on: Day
    units: DecimalOut
    #: In the holding's currency, and in the base currency at the rate it
    #: was bought at.
    cost: Amount
    cost_base: Amount


class ScenarioHoldingTrade(BaseModel):
    """An invest into one of your holdings, or a sale of one: the holding as
    you named it, the units at its price, the fees, and a sale's lots and
    realised gain. Native figures are in the holding's currency; `*_base`
    ones in your base currency (a sale at the as-of rate, each lot at the
    rate it was bought at). There is no expected return per holding: the
    investments grow at your one real return."""

    holding_id: str
    symbol: str
    name: str
    currency: CurrencyCode
    #: Base currency per unit of the holding's, for the as-of date.
    fx_rate: DecimalOut
    units: DecimalOut
    #: Per unit at the trade, in the holding's currency.
    price: DecimalOut
    price_basis: ScenarioPriceBasis
    #: False when you gave no fees: none are counted.
    fees_given: bool
    #: In the base currency.
    fees: Amount
    #: An invest: what the units cost (the amount less fees). A sale: the
    #: proceeds (units × price), before fees.
    value: Amount
    value_base: Amount
    #: A sale's: what the lots it sells cost, and the gain it realises
    #: (proceeds − fees − cost). Null for an invest.
    cost: Amount | None
    cost_base: Amount | None
    gain: Amount | None
    gain_base: Amount | None
    lots: list[ScenarioLotSold]
    #: The lot an invest opens, which a later sale can name.
    lot_id: str | None
    #: The investment account the holding sits in: a sale comes out of it.
    account_id: str | None


class ScenarioChange(BaseModel):
    """A change as Salli read it."""

    index: int
    type: Literal[
        "one_off",
        "recurring",
        "income_change",
        "loan",
        "extra_debt_payment",
        "invest",
        "stop_recurring",
        "set_aside",
        "sell",
        "asset",
    ]
    label: str
    #: A loan's id in the debts below, or an extra payment's debt.
    debt_id: str | None
    #: A loan's monthly payment.
    payment: Amount | None
    #: A loan's first payment's month.
    first_payment: Month | None
    #: A recurring change's, an income change's or a stop's effect a month,
    #: in today's money (money in positive); what a set-aside keeps in cash
    #: a month.
    monthly: Amount | None
    #: Whether it lasts for good.
    for_good: bool | None
    stopped: list[ScenarioStopped]
    #: An invest into one of your holdings, or a sale.
    holding: ScenarioHoldingTrade | None = None


class ScenarioBelowZero(BaseModel):
    baseline: bool
    scenario: bool


class ScenarioAccountCash(BaseModel):
    """A cash account at its lowest over the next twelve months, in its own
    currency."""

    account_id: str
    name: str
    currency: CurrencyCode
    lowest: AmountFigure
    lowest_date: DayFigure
    below_zero: ScenarioBelowZero


class ScenarioAccountsBelowZero(BaseModel):
    baseline: list[str]
    scenario: list[str]


class ScenarioCash(BaseModel):
    """Cash over the as-of month and the twelve after it, in each day's money."""

    start: Day
    end: Day
    #: The cash total at its lowest, and when.
    lowest: AmountFigure
    lowest_date: DayFigure
    #: At `end`.
    at_end: AmountFigure
    #: What could go out on the as-of date without cash dropping below zero
    #: before money next comes in.
    safe_to_spend: AmountFigure
    #: Safe-to-spend's window ends the day before this.
    safe_until: Day
    accounts: list[ScenarioAccountCash]
    #: The accounts that go below zero, by id.
    below_zero: ScenarioAccountsBelowZero


class ScenarioCheckpoint(BaseModel):
    """The monthly timeline a whole number of years on, in today's money."""

    years: int
    month: Month
    date: Day
    net_worth: AmountFigure
    cash: AmountFigure
    investments: AmountFigure
    debts: AmountFigure
    #: Other assets as net worth counts them: an asset the scenario buys at
    #: its value less its selling costs (what it would fetch).
    other_assets: AmountFigure
    #: The same before selling costs: what the assets are worth.
    other_assets_value: AmountFigure


class ScenarioDebt(BaseModel):
    debt_id: str
    name: str
    #: "scenario" for a loan the scenario takes out.
    source: Literal["account", "declared", "scenario"]
    paid_off: MonthFigure
    total_interest: AmountFigure


class ScenarioDebts(BaseModel):
    items: list[ScenarioDebt]
    total_interest: AmountFigure
    #: The month the last debt is paid off.
    debt_free: MonthFigure


class ScenarioResilience(BaseModel):
    """Months of spending the cash covers, at its lowest over the next
    twelve months and at their end."""

    #: "essential": over essential spending (need-tagged); "all": over all
    #: spending; null without spending to go by.
    basis: Literal["essential", "all"] | None
    monthly_spending: Amount | None
    lowest: MonthsFigure
    at_end: MonthsFigure


class ScenarioFi(BaseModel):
    fi_number: AmountFigure
    #: The monthly spending each FI number is built on.
    monthly_spending: AmountFigure
    fi_month: MonthFigure
    #: Months sooner (positive) or later (negative) than the baseline's.
    months_gained: int | None


class ScenarioBreakEven(BaseModel):
    """A value at which the answer changes, solved exactly, or none in range."""

    kind: Literal["recurring_cash_floor", "invest_vs_debt_return", "loan_rate", "asset_growth"]
    options: list[str]
    #: The option it varies (or, for invest_vs_debt_return, the one that invests;
    #: for asset_growth, the one that buys the asset).
    option: str | None
    #: The change it varies, by index in that option.
    change: int | None
    status: Literal["found", "none_in_range"]
    #: "amount" (the base currency) or "rate" (a yearly fraction).
    unit: Literal["amount", "rate"]
    value: DecimalOut | None
    low: DecimalOut
    high: DecimalOut
    #: With none in range: the option ahead across the whole range.
    ahead: str | None
    #: What it means, in a sentence.
    says: str


class ScenarioRuleSet(BaseModel):
    country: str
    region: str | None
    year: str
    rule_set_id: str
    version: int
    content_hash: str


class ScenarioTaxRules(ScenarioRuleSet):
    """The active rules that computed a tax year."""

    #: True when they are an earlier year's rules carried forward, every
    #: amount in them level in today's money (no active rules of the year's
    #: own): labelled `tax_rules_carried_forward`.
    carried_forward: bool


class ScenarioTaxRole(BaseModel):
    """A role the scenario touches, for one tax year, in the rules'
    currency and that year's own money."""

    key: str
    kind: str
    label: str
    #: Posted from the year's start to the as-of date.
    actual: Amount
    #: The actual and the rest of the year at the role's monthly average:
    #: the baseline's total.
    projected: Amount
    #: The projected total and the scenario's tagged amounts.
    scenario: Amount


class ScenarioTaxPart(BaseModel):
    """The month's part of the year's change in tax, out of cash at the
    month's end (more tax positive)."""

    month: Month
    amount: Amount


class ScenarioTaxYear(BaseModel):
    """One tax year the scenario touches."""

    year: str
    start: Day
    end: Day
    status: Literal["computed", "not_computed"]
    #: Why it isn't computed, and what to do.
    reason: str | None
    rules: ScenarioTaxRules | None
    #: The rules' currency: the roles' totals and `net` are in it.
    currency: CurrencyCode | None
    roles: list[ScenarioTaxRole]
    #: The year's net tax (after credits) under each, in the rules' currency.
    net: AmountFigure
    #: The change in the year's tax, in your base currency (more tax
    #: positive), in its own money.
    change: Amount | None
    monthly: list[ScenarioTaxPart]


class ScenarioTaxOutcome(BaseModel):
    """The change in tax a scenario's changes tagged with a tax role make,
    computed with your active tax rules. Investment growth isn't taxed: set
    your real return after the tax you pay on it."""

    #: "computed"; "not_computed" (tagged amounts then count before tax, and
    #: "tax" is among the placeholders); "none" (nothing tagged).
    status: Literal["computed", "not_computed", "none"]
    reason: str | None
    #: The first two tax years touched, and those of the monthly checkpoints.
    years: list[ScenarioTaxYear]
    #: The as-of date's tax year, when the scenario touches it.
    this_year: ScenarioTaxYear | None
    #: The change in the as-of date's tax year's tax, in your base currency:
    #: 0 when nothing in it is tagged; null when it isn't computed.
    change_this_year: Amount | None
    #: The change in tax over the horizon, in today's money.
    total_change: Amount | None
    #: Whether any year was computed with rules carried forward.
    carried_forward: bool


class ScenarioVersions(BaseModel):
    schema_: str = Field(alias="schema")
    engine: str
    #: A content hash of the FI assumptions that applied.
    fi_assumptions: str
    fire_strategy: int | None
    #: The active tax rule sets covering the as-of date.
    rule_sets: list[ScenarioRuleSet]


class TimelineDay(BaseModel):
    """Cash, all accounts together, at the end of a day, under the baseline
    and under the scenario, in that day's own money."""

    date: Day
    baseline: Amount
    scenario: Amount


class TimelineMonth(BaseModel):
    """The monthly timeline at one point (the as-of date, then each month's
    end), in today's money."""

    month: str
    date: Day
    cash: AmountFigure
    net_worth: AmountFigure


class ScenarioTimeline(BaseModel):
    """Both timelines the figures are read from, under the baseline and
    under the scenario, for drawing them: every day of the cash forecast
    (the as-of month and the twelve after it), and the monthly timeline from
    the as-of date to the horizon."""

    daily: list[TimelineDay]
    monthly: list[TimelineMonth]


class ScenarioRun(BaseModel):
    """A scenario's figures under the baseline and under the scenario."""

    schema_: Literal["salli.scenario/1"] = Field(alias="schema")
    label: str | None
    as_of: Day
    horizon_years: int
    currency: CurrencyCode
    #: A content hash of the inputs (the scenario with its as-of date, and
    #: the baseline's fingerprint): the same hash, the same figures.
    hash: str
    baseline_fingerprint: str
    #: The scenario as run, its as-of date filled in.
    scenario: Scenario
    changes: list[ScenarioChange]
    cash: ScenarioCash
    monthly: list[ScenarioCheckpoint]
    debts: ScenarioDebts
    resilience: ScenarioResilience
    fi: ScenarioFi
    break_evens: list[ScenarioBreakEven]
    tax: ScenarioTaxOutcome
    #: The FI assumptions the figures rest on, and where each came from.
    assumptions: FiAssumptions
    #: Which figures rest on placeholders: FI's assumptions, inflation, the
    #: tax ("tax": not computed, so tagged amounts count before tax), tax
    #: rules carried forward to years with none of their own, and an asset
    #: with no growth of its own ("asset_growth": 0 beyond inflation).
    placeholders: list[
        Literal[
            "real_return",
            "safe_withdrawal_rate",
            "surplus_invested",
            "inflation",
            "tax",
            "tax_rules_carried_forward",
            "asset_growth",
        ]
    ]
    versions: ScenarioVersions
    #: The newest ledger entry on or before the as-of date.
    data_as_of: Day | None
    #: Older than 45 days: bring the ledger up to date before deciding.
    is_stale: bool
    notes: list[str]
    #: Both timelines, only when asked for (`?timeline=true`); null otherwise.
    timeline: ScenarioTimeline | None = None


class TradeDelta(BaseModel):
    """A figure where two options differ: this option's, the other's, and
    this less the other (in months, for a month)."""

    figure: str
    unit: Literal["amount", "months_of_spending", "month"]
    this: str | None
    other: str | None
    delta: str | int | None


class ScenarioTrade(BaseModel):
    """What `option` gains and gives up against `against`."""

    option: str
    against: str
    gains: list[TradeDelta]
    gives_up: list[TradeDelta]


class SensitiveFigures(BaseModel):
    net_worth: AmountFigure
    investments: AmountFigure
    fi_month: MonthFigure
    months_gained: int | None


class OptionSensitivity(BaseModel):
    option: str
    conservative: SensitiveFigures
    base: SensitiveFigures
    growth: SensitiveFigures


class SensitivityReturns(BaseModel):
    conservative: DecimalOut
    base: DecimalOut
    growth: DecimalOut


class ScenarioSensitivity(BaseModel):
    """The options at the horizon under each real return."""

    real_returns: SensitivityReturns
    options: list[OptionSensitivity]


class ScenarioComparison(BaseModel):
    """Options side by side: never ranked."""

    as_of: Day
    horizon_years: int
    currency: CurrencyCode
    labels: list[str]
    options: list[ScenarioRun]
    trade: list[ScenarioTrade]
    sensitivity: ScenarioSensitivity
    break_evens: list[ScenarioBreakEven]


class CompareOptions(BaseModel):
    """The options to compare: two to five scenarios with one as-of date and
    one horizon, each with its own label."""

    options: Annotated[list[Scenario], Field(min_length=2, max_length=5)]


_TIMELINE = Query(
    False,
    description=(
        "Include both timelines, the baseline's and the scenario's: every day of the "
        "cash forecast and every point of the monthly timeline to the horizon"
    ),
)


@router.post("/run", responses=_NOT_FOUND)  # type: ignore[arg-type]
async def run_scenario(
    body: Scenario, user_id: CurrentUser, svc: AppServices, timeline: bool = _TIMELINE
) -> ScenarioRun:
    """Run a scenario on your baseline: cash over the next twelve months, the
    monthly figures at 1, 5, 10 and 20 years and the horizon, debts,
    resilience and FI, each under the baseline and the scenario with the
    delta; with `timeline`, the timelines they are read from. Stores
    nothing."""
    return ScenarioRun.model_validate(await svc.scenarios.run(user_id, body, timeline=timeline))


@router.post("/compare", responses=_NOT_FOUND)  # type: ignore[arg-type]
async def compare_scenarios(
    body: CompareOptions, user_id: CurrentUser, svc: AppServices, timeline: bool = _TIMELINE
) -> ScenarioComparison:
    """Compare two to five options side by side: each one's figures, what
    each gains and gives up against the others, their sensitivity to the
    real return, and the break-evens; with `timeline`, each option's
    timelines. Never a ranking. Stores nothing."""
    return ScenarioComparison.model_validate(
        await svc.scenarios.compare(user_id, body.options, timeline=timeline)
    )
