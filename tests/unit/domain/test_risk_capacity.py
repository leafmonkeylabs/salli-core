"""Risk capacity beside tolerance, and the investment policy's drift report."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from pydantic import ValidationError

from salli.domain.portfolio import policy as ips
from salli.domain.risk import capacity


def test_capacity_scores_the_four_measures_and_scales_over_those_present():
    strong = capacity.compute(Decimal(8), Decimal("0.05"), 20, Decimal("0.05"))
    assert (strong.score, strong.category, strong.missing) == (100, "aggressive", ())
    thin = capacity.compute(Decimal("0.5"), Decimal("0.6"), 1, Decimal("0.5"))
    assert (thin.score, thin.category) == (0, "conservative")
    # Without a horizon: three measures, 15 + 25 + 18 of 75.
    partial = capacity.compute(Decimal(4), Decimal("0.02"), None, Decimal("0.15"))
    assert partial.missing == ("horizon",) and partial.score == 77


def test_income_variation_needs_three_months():
    assert capacity.income_variation([Decimal(100), Decimal(100)]) is None
    assert capacity.income_variation([Decimal(100)] * 3) == 0


def test_the_profile_is_the_lower_of_tolerance_and_capacity():
    assert capacity.profile("aggressive", "balanced") == "balanced"
    assert capacity.profile("conservative", "aggressive") == "conservative"
    assert capacity.profile(None, "balanced") == "balanced"


POLICY = {
    "targets": [
        {"asset_class": "equity", "target": "0.6", "band": "0.05"},
        {"asset_class": "bond", "target": "0.4", "band": "0.05"},
    ],
    "rebalancing": {"rule": "both", "every_months": 12},
    "horizon_years": 15,
    "review_on": "2027-01-01",
}


def test_a_policy_needs_targets_that_add_up():
    with pytest.raises(ValidationError, match="add up to 1"):
        ips.Policy.model_validate({"targets": [{"asset_class": "equity", "target": "0.5"}]})
    with pytest.raises(ValidationError, match="every_months"):
        ips.Policy.model_validate({**POLICY, "rebalancing": {"rule": "calendar"}})


def test_drift_against_the_policy_with_bands_and_the_rebalancing_rule():
    policy = ips.Policy.model_validate(POLICY)
    report = ips.drift(
        policy,
        {"equity": Decimal(7000), "bond": Decimal(2500), "cash": Decimal(500)},
        adopted_on=dt.date(2026, 1, 15),
        today=dt.date(2026, 10, 25),
    )
    classes = {c["asset_class"]: c for c in report["classes"]}  # type: ignore[index]
    assert classes["equity"]["drift_pct"] == Decimal("0.1000")
    assert classes["equity"]["outside_band"] is True
    assert classes["equity"]["to_target"] == Decimal("-1000.00")
    assert classes["cash"]["in_policy"] is False
    assert report["rebalance_due"] is True and report["review_due"] is False
    inside = ips.drift(
        policy,
        {"equity": Decimal(6200), "bond": Decimal(3800)},
        adopted_on=dt.date(2026, 1, 15),
        today=dt.date(2027, 1, 15),
    )
    # Inside the bands, but a year has passed and the review date has come.
    assert inside["rebalance_due"] is True and inside["review_due"] is True


def test_an_equity_target_above_the_profiles_band_is_flagged():
    policy = ips.Policy.model_validate(POLICY)
    assert ips.equity_check(policy, "balanced")["above_profile"] is False
    assert ips.equity_check(policy, "conservative")["above_profile"] is True
