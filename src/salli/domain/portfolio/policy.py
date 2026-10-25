"""
The investment policy statement (`salli.ips/1`) and the drift report against
it. Pure: a document and a portfolio's values in, a report out.

A policy is the person's own: a target share of the portfolio for each asset
class with a band either side, a rebalancing rule (when a class leaves its
band, on a calendar, or both), the horizon in years, objectives and
constraints in their words, and the day to review it. It is stored as
versions and never changed (application/services/investment_policy_service.py).

Asset classes come from one controlled taxonomy (`TAXONOMY`): a class and
its sub-classes ("equity", "equity.international"). A policy may target a
class or its sub-classes; a holding's value counts toward its own class, or
toward its parent where the policy targets the parent (`roll_up`). A fund the
person tags with an allocation (its look-through, `check_allocation`) counts
across those classes in those shares.

The drift report says, for every class in the policy or held, its share now,
its target and band, how far it has drifted, whether it is outside its band,
and the amount that would bring it to its target. It says what the policy
says; it never chooses a target, a class or a security.
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from salli.domain.risk.capacity import EQUITY_BANDS
from salli.domain.risk.models import RiskCategory

#: The controlled asset-class taxonomy: each class and its sub-classes.
TAXONOMY: dict[str, tuple[str, ...]] = {
    "equity": ("equity.domestic", "equity.international", "equity.emerging"),
    "fixed_income": (
        "fixed_income.government",
        "fixed_income.corporate",
        "fixed_income.inflation_linked",
    ),
    "cash": (),
    "property": ("property.direct", "property.listed"),
    "commodities": (),
    "alternatives": (),
    "other": (),
}
ASSET_CLASSES: tuple[str, ...] = tuple(
    c for parent, subs in TAXONOMY.items() for c in (parent, *subs)
)
AssetClass = Literal[
    "equity",
    "equity.domestic",
    "equity.international",
    "equity.emerging",
    "fixed_income",
    "fixed_income.government",
    "fixed_income.corporate",
    "fixed_income.inflation_linked",
    "cash",
    "property",
    "property.direct",
    "property.listed",
    "commodities",
    "alternatives",
    "other",
]

#: The asset class whose share is held to the risk profile's band.
EQUITY = "equity"


def parent(asset_class: str) -> str:
    return asset_class.split(".", 1)[0]


def roll_up(asset_class: str, targeted: set[str]) -> str:
    """The class a value counts toward: its own where targeted, else its
    parent where that is, else its own."""
    if asset_class in targeted or parent(asset_class) not in targeted:
        return asset_class
    return parent(asset_class)


def check_allocation(raw: object) -> dict[str, Decimal] | None:
    """A holding's look-through allocation (taxonomy class → share, summing
    to 1), checked; a ValueError otherwise. None clears it."""
    if raw is None:
        return None
    if not isinstance(raw, dict) or not raw:
        raise ValueError("allocation is an object of asset class → share, summing to 1")
    out: dict[str, Decimal] = {}
    for key, value in cast("dict[object, object]", raw).items():
        if key not in ASSET_CLASSES:
            raise ValueError(f"{key!r} is not an asset class: one of {', '.join(ASSET_CLASSES)}")
        try:
            share = Decimal(str(value)) if isinstance(value, str | Decimal) else Decimal(-1)
        except ArithmeticError:
            share = Decimal(-1)
        if not share.is_finite() or not 0 <= share <= 1:
            raise ValueError(f"allocation.{key} is a share from 0 to 1, as a string")
        out[str(key)] = share
    if sum(out.values(), Decimal(0)) != 1:
        raise ValueError("The allocation's shares add up to 1")
    return out


_Share = Annotated[Decimal, Field(ge=0, le=1)]


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_class: AssetClass
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
    #: Why the equity target may sit above the risk profile's band: needed,
    #: and stored with the version, when it does.
    override_reason: Annotated[str, Field(min_length=1, max_length=1000)] | None = None

    @model_validator(mode="after")
    def _targets_add_up(self) -> Policy:
        classes = [t.asset_class for t in self.targets]
        if len(set(classes)) != len(classes):
            raise ValueError("Each asset class has one target")
        if any(c != parent(c) and parent(c) in classes for c in classes):
            raise ValueError("Target a class or its sub-classes, not both")
        if sum((t.target for t in self.targets), Decimal(0)) != 1:
            raise ValueError("The targets add up to 1 (100% of the portfolio)")
        return self

    def document(self) -> dict[str, object]:
        # Without an override, as versions before it were stored.
        return self.model_dump(
            mode="json",
            by_alias=True,
            exclude=None if self.override_reason else {"override_reason"},
        )


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
    targets = {t.asset_class: t for t in policy.targets}
    rolled: dict[str, Decimal] = {}
    for asset_class, value in values.items():
        key = roll_up(asset_class, set(targets))
        rolled[key] = rolled.get(key, Decimal(0)) + value
    values = rolled
    total = sum(values.values(), Decimal(0))
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
    target = sum((t.target for t in policy.targets if parent(t.asset_class) == EQUITY), Decimal(0))
    ceiling = EQUITY_BANDS[profile]
    return {
        "equity_target": target,
        "profile": profile,
        "profile_equity_max": ceiling,
        "above_profile": target > ceiling,
        "override_reason": policy.override_reason,
    }


def lots_to_sell(
    amount: Decimal, lots: list[dict[str, Any]], money_quantum: Decimal
) -> tuple[list[dict[str, Any]], Decimal]:
    """Which open lots, sold, raise `amount` with the least realised gain:
    losses first, then the smallest gain for each unit of money raised, a
    lot sold in part when it is more than is left. Each lot is a dict with
    `value` and `cost` (both in the base currency) and `quantity`; the rest
    is passed through. Returns the lots with what of each is sold, and the
    realised gain. Figures only: which lots, never whether to sell."""
    picked: list[dict[str, Any]] = []
    left, gain = amount, Decimal(0)

    def ratio(lot: dict[str, Any]) -> Decimal:
        value: Decimal = lot["value"]
        return (value - lot["cost"]) / value if value > 0 else Decimal(0)

    for lot in sorted((x for x in lots if x["value"] > 0), key=ratio):
        if left <= 0:
            break
        share = min(Decimal(1), left / lot["value"])
        proceeds = (lot["value"] * share).quantize(money_quantum, rounding=ROUND_HALF_UP)
        realised = ((lot["value"] - lot["cost"]) * share).quantize(
            money_quantum, rounding=ROUND_HALF_UP
        )
        picked.append(
            {
                **{k: v for k, v in lot.items() if k not in ("value", "cost", "quantity")},
                "quantity": lot["quantity"] * share,
                "proceeds": proceeds,
                "realised_gain": realised,
            }
        )
        left -= proceeds
        gain += realised
    return picked, gain
