"""
The investment policy statement (`salli.ips/1`) and the drift report against
it. Pure: a document and a portfolio's values in, a report out.

A policy is the person's own: a target share of the portfolio for each asset
class with a band either side, a rebalancing rule (when a class leaves its
band, on a calendar, or both), the horizon in years, objectives and
constraints in their words, and the day to review it. It is stored as
versions and never changed (application/services/investment_policy_service.py).

The drift report says, for every class in the policy or held, its share now,
its target and band, how far it has drifted, whether it is outside its band,
and the amount that would bring it to its target. It says what the policy
says; it never chooses a target, a class or a security.
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from salli.domain.risk.capacity import EQUITY_BANDS
from salli.domain.risk.models import RiskCategory

#: The asset class whose share is held to the risk profile's band.
EQUITY = "equity"

_Share = Annotated[Decimal, Field(ge=0, le=1)]


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_class: Annotated[str, Field(min_length=1, max_length=40)]
    target: _Share
    #: How far either side of the target the share may move before the
    #: class is outside its band.
    band: _Share = Decimal("0.05")


class Rebalancing(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    #: "bands": when a class leaves its band; "calendar": every
    #: `every_months`; "both": whichever comes first.
    rule: Literal["bands", "calendar", "both"] = "bands"
    every_months: Annotated[int, Field(ge=1, le=120)] | None = None

    @model_validator(mode="after")
    def _calendar_needs_months(self) -> Rebalancing:
        if self.rule != "bands" and self.every_months is None:
            raise ValueError("A calendar rebalancing rule needs every_months")
        return self


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_: Literal["salli.ips/1"] = Field(default="salli.ips/1", alias="schema")
    targets: Annotated[list[Target], Field(min_length=1, max_length=40)]
    rebalancing: Rebalancing = Rebalancing()
    horizon_years: Annotated[int, Field(ge=0, le=100)] | None = None
    objectives: Annotated[str, Field(max_length=2000)] = ""
    constraints: Annotated[str, Field(max_length=2000)] = ""
    review_on: dt.date | None = None

    @model_validator(mode="after")
    def _targets_add_up(self) -> Policy:
        classes = [t.asset_class for t in self.targets]
        if len(set(classes)) != len(classes):
            raise ValueError("Each asset class has one target")
        if sum((t.target for t in self.targets), Decimal(0)) != 1:
            raise ValueError("The targets add up to 1 (100% of the portfolio)")
        return self

    def document(self) -> dict[str, object]:
        return self.model_dump(mode="json", by_alias=True)


def _q4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def drift(
    policy: Policy,
    values: dict[str, Decimal],
    *,
    adopted_on: dt.date,
    today: dt.date,
    money_quantum: Decimal = Decimal("0.01"),
) -> dict[str, object]:
    """`values` is each asset class's value now, in the base currency."""
    total = sum(values.values(), Decimal(0))
    targets = {t.asset_class: t for t in policy.targets}
    classes: list[dict[str, object]] = []
    outside_any = False
    for asset_class in [*targets, *sorted(set(values) - set(targets))]:
        t = targets.get(asset_class)
        target = t.target if t else Decimal(0)
        band = t.band if t else Decimal(0)
        value = values.get(asset_class, Decimal(0))
        share = value / total if total > 0 else Decimal(0)
        moved = share - target
        outside = total > 0 and abs(moved) > band
        outside_any = outside_any or outside
        classes.append(
            {
                "asset_class": asset_class,
                "value": (value).quantize(money_quantum, rounding=ROUND_HALF_UP),
                "current_pct": _q4(share),
                "target_pct": target,
                "band": band,
                "drift_pct": _q4(moved),
                "outside_band": outside,
                "to_target": (target * total - value).quantize(
                    money_quantum, rounding=ROUND_HALF_UP
                ),
                "in_policy": t is not None,
            }
        )
    rule = policy.rebalancing
    calendar_due = False
    if rule.rule != "bands" and rule.every_months is not None:
        months = (today.year - adopted_on.year) * 12 + today.month - adopted_on.month
        calendar_due = months >= rule.every_months
    rebalance_due = (rule.rule != "calendar" and outside_any) or calendar_due
    return {
        "total_value": total.quantize(money_quantum, rounding=ROUND_HALF_UP),
        "classes": classes,
        "rebalance_due": rebalance_due,
        "review_due": policy.review_on is not None and policy.review_on <= today,
    }


def equity_check(policy: Policy, profile: RiskCategory) -> dict[str, object]:
    """Whether the policy's equity target is within the risk profile's band."""
    target = next((t.target for t in policy.targets if t.asset_class == EQUITY), Decimal(0))
    ceiling = EQUITY_BANDS[profile]
    return {
        "equity_target": target,
        "profile": profile,
        "profile_equity_max": ceiling,
        "above_profile": target > ceiling,
    }
