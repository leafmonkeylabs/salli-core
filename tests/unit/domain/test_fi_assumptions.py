"""
FI planning assumptions follow the base currency, say where they come from,
and give way to the user's own.

The defaults are round and conservative: each central bank's own inflation
target, one round real return below the long-run record, and the 4% rule. Sri
Lanka keeps exactly the figures Salli always used.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.domain.fi.assumptions import (
    FALLBACK,
    OTHER,
    REGIONAL_DEFAULTS,
    SPREAD,
    Overrides,
    Returns,
    StrategyFigures,
    check_override,
    real_return,
    regional_defaults,
    resolve,
)
from salli.domain.fi.packs.default_v1 import DEFAULT_V1

D = Decimal


def test_sri_lanka_keeps_the_figures_salli_always_used():
    lk = REGIONAL_DEFAULTS["LKR"]
    assert lk.inflation.value == DEFAULT_V1.expected_inflation == D("0.05")
    assert lk.safe_withdrawal_rate.value == DEFAULT_V1.safe_withdrawal_rate == D("0.04")
    returns = lk.returns(lk.inflation.value)
    assert (returns.conservative, returns.base, returns.growth) == (
        D("0.06"),
        D("0.10"),
        D("0.14"),
    )
    assert "Central Bank of Sri Lanka" in lk.inflation.source


@pytest.mark.parametrize(
    ("currency", "inflation"),
    [
        ("USD", "0.02"),
        ("EUR", "0.02"),
        ("GBP", "0.02"),
        ("JPY", "0.02"),
        ("CAD", "0.02"),
        ("AUD", "0.025"),
        ("NZD", "0.02"),
        ("INR", "0.04"),
    ],
)
def test_other_currencies_take_their_central_banks_target(currency, inflation):
    row = regional_defaults(currency)
    assert row.region == currency
    assert row.inflation.value == D(inflation)
    # The base scenario is the round 4% real return, exactly, at that inflation,
    # with the other two 4 points either side of it, nominal.
    returns = row.returns(row.inflation.value)
    assert real_return(returns.base, row.inflation.value) == D("0.04")
    assert returns.growth - returns.base == returns.base - returns.conservative == SPREAD
    assert row.safe_withdrawal_rate.value == D("0.04")


def test_every_figure_says_where_it_comes_from():
    for row in [*REGIONAL_DEFAULTS.values(), FALLBACK]:
        returns = row.returns(row.inflation.value)
        for source in (row.inflation.source, returns.source, row.safe_withdrawal_rate.source):
            assert len(source) > 40
            assert "—" not in source  # read by people, and by the agents
    assert "Bengen" in FALLBACK.safe_withdrawal_rate.source
    assert "Dimson" in REGIONAL_DEFAULTS["USD"].returns(D("0.02")).source


def test_a_currency_without_figures_gets_cautious_placeholders():
    assert regional_defaults("THB") is FALLBACK
    assert regional_defaults(None) is FALLBACK
    assert FALLBACK.region == OTHER
    # Higher than every target in the table: inflation that errs high makes
    # the same nominal return worth less.
    assert FALLBACK.inflation.value == D("0.05")
    assert "Set your own" in FALLBACK.inflation.source


def test_the_currencys_defaults_apply_when_nothing_else_does():
    applied = resolve("usd", Overrides())
    assert applied.region == "USD"
    assert {applied.inflation.origin, applied.real_return.origin} == {"default"}
    assert applied.safe_withdrawal_rate.origin == "default"
    assert applied.real_return.value == D("0.04")


def test_a_strategy_s_returns_and_rate_come_before_the_defaults():
    strategy = StrategyFigures(D("0.035"), Returns(D("0.05"), D("0.09"), D("0.12"), "theirs"))
    applied = resolve("LKR", Overrides(), strategy)
    assert (applied.safe_withdrawal_rate.value, applied.safe_withdrawal_rate.origin) == (
        D("0.035"),
        "strategy",
    )
    assert applied.returns.base == D("0.09") and applied.real_return.origin == "strategy"
    # Inflation is never the strategy's.
    assert applied.inflation.origin == "default"


def test_the_users_own_figures_come_first():
    strategy = StrategyFigures(D("0.035"), Returns(D("0.05"), D("0.09"), D("0.12"), "theirs"))
    own = Overrides(inflation=D("0.03"), real_return=D("0.035"), safe_withdrawal_rate=D("0.03"))
    applied = resolve("LKR", own, strategy)
    assert {
        applied.inflation.origin,
        applied.real_return.origin,
        applied.safe_withdrawal_rate.origin,
    } == {"user"}
    assert applied.inflation.value == D("0.03")
    assert applied.safe_withdrawal_rate.value == D("0.03")
    # Their real return is the base scenario's, exactly; the others sit around it.
    assert applied.real_return.value == D("0.035")
    assert applied.returns.base - applied.returns.conservative == SPREAD


def test_the_users_inflation_turns_the_strategys_returns_real():
    strategy = StrategyFigures(D("0.04"), Returns(D("0.06"), D("0.10"), D("0.14"), "theirs"))
    applied = resolve("LKR", Overrides(inflation=D("0.10")), strategy)
    assert applied.real_return.value == D(0)
    assert applied.scenario_real_returns["base"] == D(0)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("inflation", "5"),
        ("inflation", "-0.5"),
        ("real_return", "4"),
        ("real_return", "0.2"),
        ("safe_withdrawal_rate", "4"),
        ("safe_withdrawal_rate", "0"),
    ],
)
def test_a_percentage_typed_for_a_fraction_is_refused(name, value):
    with pytest.raises(ValueError, match="yearly fraction"):
        check_override(name, D(value))


def test_plausible_figures_are_kept():
    assert check_override("inflation", D("0.03")) == D("0.03")
    assert check_override("real_return", D("-0.01")) == D("-0.01")
    assert check_override("safe_withdrawal_rate", D("0.035")) == D("0.035")
    assert check_override("inflation", None) is None


def test_a_default_real_return_stays_real_whatever_inflation_the_user_sets():
    """4% after inflation is 4% after inflation: setting one's own inflation
    must not quietly lower it."""
    applied = resolve("USD", Overrides(inflation=D("0.03")))
    assert applied.real_return.value == D("0.04")
    assert applied.real_return.origin == "default"


def test_sri_lankas_nominal_defaults_turn_real_at_the_inflation_that_applies():
    """Its defaults are nominal, like a strategy's: a different inflation
    changes what they are worth."""
    applied = resolve("LKR", Overrides(inflation=D("0.10")))
    assert applied.returns.base == D("0.10")
    assert applied.real_return.value == D(0)


def test_a_region_has_either_a_real_return_or_nominal_returns():
    from salli.domain.fi.assumptions import RegionalDefaults

    figure = REGIONAL_DEFAULTS["USD"].inflation
    with pytest.raises(ValueError, match="not both"):
        RegionalDefaults("XXX", "x", figure, figure)
