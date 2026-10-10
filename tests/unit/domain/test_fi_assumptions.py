"""
FI planning assumptions are in real terms, with one neutral placeholder that is
always labelled as one, and give way to what the user (or their agent) sets,
each figure with its source.

There is no table by country or currency: whatever the user's currency or
residency, the placeholders are the same round figures, and inflation has none
at all.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

import salli.domain.fi.assumptions as assumptions
from salli.domain.fi.assumptions import (
    NAMES,
    PLACEHOLDERS,
    SCENARIO_SPREAD,
    OwnAssumptions,
    OwnFigure,
    Scenarios,
    StrategyFigures,
    check_consistent,
    check_value,
    nominal_return,
    own_figure,
    real_return,
    resolve,
)

D = Decimal


def _own(**figures: str) -> OwnAssumptions:
    return OwnAssumptions(
        **{name: own_figure(name, value, f"source of {name}") for name, value in figures.items()}
    )


# ── The placeholders ─────────────────────────────────────────────────────────


def test_there_is_no_table_by_country_or_currency():
    names = {name.upper() for name in vars(assumptions)}
    assert not names & {"REGIONAL_DEFAULTS", "FALLBACK", "OTHER", "RETURNS", "OVERRIDES"}
    # Only the real return and the withdrawal rate have a placeholder.
    assert set(PLACEHOLDERS) == {"real_return", "safe_withdrawal_rate"}


def test_the_placeholders_are_round_neutral_and_say_they_are_placeholders():
    assert PLACEHOLDERS["real_return"].value == D("0.04")
    assert PLACEHOLDERS["safe_withdrawal_rate"].value == D("0.04")
    for placeholder in PLACEHOLDERS.values():
        assert placeholder.source.startswith("Placeholder:")
        assert "Set your own" in placeholder.source
        assert "—" not in placeholder.source  # read by people, and by the agents


def test_with_nothing_set_placeholders_stand_in_and_say_so():
    applied = resolve(OwnAssumptions())
    assert applied.status == "placeholder"
    assert applied.placeholders == ("real_return", "safe_withdrawal_rate")
    assert applied.real_return.origin == applied.safe_withdrawal_rate.origin == "placeholder"
    assert applied.real_return.value == D("0.04")
    assert applied.safe_withdrawal_rate.value == D("0.04")
    # No inflation is ever assumed: everything is in today's money.
    assert applied.inflation is None
    assert applied.nominal_returns is None
    assert "placeholder assumptions for the real return and the safe withdrawal rate" in (
        applied.message
    )
    assert "today's money" in applied.message


def test_the_scenarios_sit_a_spread_either_side_of_the_base_in_real_terms():
    applied = resolve(OwnAssumptions())
    assert applied.real_returns == Scenarios(D("0.02"), D("0.04"), D("0.06"))
    assert D("0.02") == SCENARIO_SPREAD


# ── The user's own ───────────────────────────────────────────────────────────


def test_the_users_own_figures_come_first_with_their_sources():
    strategy = StrategyFigures(D("0.035"), Scenarios(D("0.01"), D("0.03"), D("0.05")))
    own = OwnAssumptions(
        real_return=own_figure("real_return", "0.035", "https://example.org/returns", "a note"),
        safe_withdrawal_rate=own_figure("safe_withdrawal_rate", "0.03"),
    )
    applied = resolve(own, strategy)
    assert applied.status == "user"
    assert applied.placeholders == ()
    assert applied.real_return.value == D("0.035")
    assert applied.real_return.origin == "user"
    assert applied.real_return.source == "https://example.org/returns"
    assert applied.real_return.note == "a note"
    # A figure set without a source says so, rather than inventing one.
    assert applied.safe_withdrawal_rate.source == "Set by you; no source given."
    assert applied.real_returns == Scenarios(D("0.015"), D("0.035"), D("0.055"))
    assert applied.message.startswith("Using your own assumptions.")


def test_setting_only_one_figure_leaves_the_other_a_placeholder():
    applied = resolve(_own(real_return="0.05"))
    assert applied.status == "placeholder"
    assert applied.placeholders == ("safe_withdrawal_rate",)
    assert "for the safe withdrawal rate:" in applied.message


def test_inflation_brings_nominal_figures_and_leaves_the_real_return_real():
    """4% after inflation is 4% after inflation: setting one's own inflation
    adds nominal figures, and never quietly changes the real ones."""
    applied = resolve(_own(inflation="0.03"))
    assert applied.real_return.value == D("0.04")
    assert applied.real_return.origin == "placeholder"
    assert applied.inflation is not None and applied.inflation.value == D("0.03")
    # (1.04 × 1.03) − 1 = 0.0712, and likewise for the other two.
    assert applied.nominal_returns == Scenarios(D("0.0506"), D("0.0712"), D("0.0918"))
    assert "today's money" not in applied.message


def test_a_nominal_return_becomes_real_with_the_users_inflation():
    applied = resolve(_own(nominal_return="0.07", inflation="0.02"))
    # (1.07 / 1.02) − 1
    assert applied.real_return.value == D("1.07") / D("1.02") - 1
    assert applied.real_return.origin == "user"
    assert "nominal return of 0.07 less your inflation of 0.02" in applied.real_return.source
    assert "source of nominal_return" in applied.real_return.source
    assert applied.nominal_return is not None and applied.nominal_return.value == D("0.07")
    assert applied.nominal_returns is not None
    assert applied.nominal_returns.base == nominal_return(applied.real_return.value, D("0.02"))


def test_a_nominal_return_without_inflation_is_never_used():
    """check_consistent keeps it from being stored; were it there anyway, the
    placeholder stands in rather than a guessed inflation."""
    applied = resolve(OwnAssumptions(nominal_return=OwnFigure(D("0.07"))))
    assert applied.real_return.origin == "placeholder"
    assert applied.nominal_return is None


def test_a_strategy_s_figures_come_before_the_placeholders():
    strategy = StrategyFigures(D("0.035"), Scenarios(D("0.01"), D("0.03"), D("0.05")), version=3)
    applied = resolve(OwnAssumptions(), strategy)
    assert applied.status == "user"
    assert (applied.safe_withdrawal_rate.value, applied.safe_withdrawal_rate.origin) == (
        D("0.035"),
        "strategy",
    )
    assert applied.real_returns == strategy.real_returns
    assert applied.real_return.origin == "strategy"
    assert "version 3" in applied.real_return.source


def test_a_strategy_without_real_returns_gives_only_its_withdrawal_rate():
    applied = resolve(OwnAssumptions(), StrategyFigures(D("0.035")))
    assert applied.safe_withdrawal_rate.origin == "strategy"
    assert applied.real_return.origin == "placeholder"
    assert applied.placeholders == ("real_return",)


# ── Checking what the user sets ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("inflation", "5"),
        ("inflation", "-0.5"),
        ("nominal_return", "7"),
        ("real_return", "4"),
        ("real_return", "0.2"),
        ("safe_withdrawal_rate", "4"),
        ("safe_withdrawal_rate", "0"),
    ],
)
def test_a_percentage_typed_for_a_fraction_is_refused(name, value):
    with pytest.raises(ValueError, match="yearly fraction"):
        check_value(name, value)


@pytest.mark.parametrize("value", [0.03, True, "three", "NaN", "Infinity", None])
def test_anything_but_a_decimal_is_refused(value):
    with pytest.raises(ValueError):
        check_value("inflation", value)


def test_plausible_figures_are_kept_exactly():
    assert check_value("inflation", "0.0325") == D("0.0325")
    assert check_value("real_return", "-0.01") == D("-0.01")
    assert check_value("safe_withdrawal_rate", "0.0350") == D("0.035")
    assert check_value("inflation", "0") == D(0)
    with pytest.raises(ValueError, match="Not an FI assumption"):
        check_value("region", "0.03")


def test_a_source_and_a_note_are_tidied_and_bounded():
    figure = own_figure("inflation", "0.03", "  https://example.org/cpi \n", "  ")
    assert (figure.source, figure.note) == ("https://example.org/cpi", None)
    with pytest.raises(ValueError, match="source"):
        own_figure("inflation", "0.03", "x" * 501)
    with pytest.raises(ValueError, match="note"):
        own_figure("inflation", "0.03", None, "x" * 1001)


def test_real_and_nominal_returns_are_not_set_together():
    with pytest.raises(ValueError, match="not both"):
        check_consistent(_own(real_return="0.04", nominal_return="0.06", inflation="0.02"))
    with pytest.raises(ValueError, match="needs your inflation"):
        check_consistent(_own(nominal_return="0.06"))
    check_consistent(_own(nominal_return="0.06", inflation="0.02"))


def test_changes_apply_and_clear_and_are_checked_together():
    own = _own(inflation="0.02")
    updated = own.changed({"nominal_return": own_figure("nominal_return", "0.06")})
    assert updated.nominal_return is not None and updated.inflation is not None
    # Clearing inflation would orphan the nominal return.
    with pytest.raises(ValueError, match="needs your inflation"):
        updated.changed({"inflation": None})
    assert updated.changed({"nominal_return": None, "inflation": None}) == OwnAssumptions()
    with pytest.raises(ValueError, match="Not FI assumptions"):
        own.changed({"region": None})


def test_stored_figures_round_trip_and_are_read_leniently():
    own = OwnAssumptions(
        inflation=own_figure("inflation", "0.025", "https://example.org", "target", "2026-10-11"),
        real_return=own_figure("real_return", "0.035"),
    )
    stored = own.as_stored()
    assert stored == {
        "real_return": {"value": "0.035"},
        "inflation": {
            "value": "0.025",
            "source": "https://example.org",
            "note": "target",
            "set_at": "2026-10-11",
        },
    }
    assert OwnAssumptions.from_stored(stored) == own
    # A malformed entry is left out rather than making the rest unreadable.
    assert (
        OwnAssumptions.from_stored(
            {"inflation": {"value": "5"}, "real_return": "0.03", "region": {"value": "0.02"}}
        )
        == OwnAssumptions()
    )
    assert OwnAssumptions.from_stored(None) == OwnAssumptions()
    assert set(NAMES) == {"real_return", "nominal_return", "inflation", "safe_withdrawal_rate"}


def test_the_fisher_relation_both_ways():
    assert real_return(D("0.10"), D("0.05")).quantize(D("0.0001")) == D("0.0476")
    assert real_return(D("0.10"), D("0")) == D("0.10")
    assert nominal_return(D("0.04"), D("0.03")) == D("0.0712")
    assert real_return(nominal_return(D("0.04"), D("0.03")), D("0.03")) == D("0.04")
