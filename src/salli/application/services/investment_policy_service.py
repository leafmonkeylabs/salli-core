"""
InvestmentPolicyService — the person's investment policy statement (stored as
versions, never changed), the drift report against it, and the risk profile
shown beside it: the questionnaire's tolerance, the capacity the baseline
shows, the lower of the two (domain/risk/capacity.py), and the need beside
it. A policy whose equity target is above the profile's band is adopted only
with an override and its reason, stored with the version.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from decimal import Decimal
from typing import Any, cast

from salli.application.services.baseline_service import BaselineService
from salli.application.services.portfolio_service import PortfolioService
from salli.domain.baseline import fi
from salli.domain.currency import quantum
from salli.domain.portfolio import policy as ips
from salli.domain.risk import capacity
from salli.domain.risk.models import RiskCategory

ZERO = Decimal(0)


def _figure(value: Decimal | None) -> str | None:
    return None if value is None else str(value.quantize(Decimal("0.01")))


class InvestmentPolicyService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        portfolio: PortfolioService,
        baselines: BaselineService,
        today: Callable[[], dt.date] = dt.date.today,
    ) -> None:
        self._uow_factory = uow_factory
        self._portfolio = portfolio
        self._baselines = baselines
        self._today = today

    async def versions(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return await uow.investment_policies.list(user_id)

    async def current(self, user_id: str) -> dict[str, Any] | None:
        versions = await self.versions(user_id)
        return versions[-1] if versions else None

    async def adopt(self, user_id: str, content: dict[str, Any]) -> dict[str, Any]:
        """Store `content` as the next version (pydantic's ValidationError,
        a 422, when it isn't a policy)."""
        policy = ips.Policy.model_validate(content)
        risk = await self.risk_profile(user_id, policy.horizon_years)
        check = ips.equity_check(policy, risk["profile"])
        if check["above_profile"] and not policy.override_reason:
            raise ValueError(
                f"The equity target ({check['equity_target']}) is above your risk profile's "
                f"band ({check['profile_equity_max']}, {risk['profile']}): give override_reason "
                "to adopt it anyway, and it is stored with this version"
            )
        document = policy.document()
        async with self._uow_factory() as uow:
            return await uow.investment_policies.add(user_id, document)

    async def risk_profile(self, user_id: str, horizon_years: int | None = None) -> dict[str, Any]:
        """Tolerance (the questionnaire's, if answered), capacity (from the
        baseline: emergency months, income stability, horizon, debt
        service), and the profile: the lower of the two."""
        async with self._uow_factory() as uow:
            profile: dict[str, Any] = await uow.user_profiles.get(user_id) or {}
        baseline = await self._baselines.build(user_id)
        flows = baseline.flows
        expenses, income = flows.expenses, flows.income
        emergency = baseline.liquid / expenses if expenses > 0 else None
        payments = sum(
            (d.minimum_payment for d in baseline.debts if d.source != "scenario" and d.balance > 0),
            Decimal(0),
        )
        service = payments / income if income > 0 else None
        variation = capacity.income_variation([m.income for m in flows.by_month])
        horizon = horizon_years if horizon_years is not None else profile.get("risk_horizon_years")
        dependents = profile.get("dependents_count")
        result = capacity.compute(emergency, variation, horizon, service, dependents)
        tolerance = cast(RiskCategory | None, profile.get("risk_category"))
        chosen = capacity.profile(tolerance, result.category)
        # Need: the return the asset base and the monthly saving require to
        # reach the FI number within the horizon.
        investments = sum((b.owned for b in baseline.balances if b.role == "investment"), ZERO)
        start = baseline.liquid + investments - baseline.total_liabilities - fi.reserve(baseline)
        saving = max(flows.surplus, Decimal(0)) * baseline.surplus_invested
        required = (
            capacity.required_return(start, saving, fi.fi_number(baseline), horizon)
            if horizon
            else None
        )
        need = capacity.need_category(required) if horizon else None
        return {
            "tolerance": {"score": profile.get("risk_score"), "category": tolerance},
            "capacity": {
                "score": result.score,
                "category": result.category,
                "breakdown": result.breakdown,
                "missing": list(result.missing),
                "emergency_months": _figure(emergency),
                "income_variation": _figure(variation),
                "horizon_years": horizon,
                "debt_service_ratio": _figure(service),
            },
            "need": {
                "required_return": None if required is None else str(required),
                "category": need,
                "above_profile": need is not None and capacity.above(need, chosen),
                "says": "The yearly real return your asset base and monthly saving need to "
                "reach your FI number within the horizon; null when no horizon is set or "
                "none up to 20% does. Shown beside the profile, never folded into it.",
            },
            "profile": chosen,
            "equity_max": str(capacity.EQUITY_BANDS[chosen]),
        }

    async def drift(self, user_id: str) -> dict[str, Any] | None:
        """The portfolio against the policy in force, with the risk profile
        beside it; None when there is no policy."""
        current = await self.current(user_id)
        if current is None:
            return None
        policy = ips.Policy.model_validate(current["content"])
        summary = await self._portfolio.get_summary(user_id)
        holdings = await self._portfolio.list_holdings(user_id)
        values: dict[str, Decimal] = {}
        for h in holdings:
            value = Decimal(h["current_value"])
            # A fund the person tagged counts across its classes.
            for asset_class, share in (h.get("allocation") or {h["asset_class"]: "1"}).items():
                values[asset_class] = values.get(asset_class, Decimal(0)) + value * Decimal(share)
        adopted = dt.date.fromisoformat(str(current["created_at"])[:10])
        report = ips.drift(
            policy,
            values,
            adopted_on=adopted,
            today=self._today(),
            money_quantum=quantum(summary["currency"]),
        )
        risk = await self.risk_profile(user_id, policy.horizon_years)
        check = ips.equity_check(policy, risk["profile"])
        classes = cast(list[dict[str, Any]], report["classes"])
        sells = await self._lots_to_sell(
            user_id, policy, holdings, classes, quantum(summary["currency"])
        )
        return {
            "version": current["version"],
            "currency": summary["currency"],
            "total_value": str(report["total_value"]),
            "classes": [
                {k: (str(v) if isinstance(v, Decimal) else v) for k, v in c.items()}
                for c in cast(list[dict[str, Any]], report["classes"])
            ],
            "rebalance_due": report["rebalance_due"],
            "review_due": report["review_due"],
            "risk_profile": risk,
            "equity_check": {
                k: (str(v) if isinstance(v, Decimal) else v) for k, v in check.items()
            },
            "tax_aware_sales": sells,
            "notes": summary["notes"],
        }

    async def _lots_to_sell(
        self,
        user_id: str,
        policy: ips.Policy,
        holdings: list[dict[str, Any]],
        classes: list[dict[str, Any]],
        money_quantum: Decimal,
    ) -> list[dict[str, Any]]:
        """For each class above its target, the open lots of its holdings
        that, sold, bring it to target with the least realised gain
        (`policy.lots_to_sell`). A fund tagged with an allocation, or one
        costed at its average, has no lots to pick and is left out."""
        targeted = {t.asset_class for t in policy.targets}
        out: list[dict[str, Any]] = []
        for row in classes:
            amount = -Decimal(row["to_target"])
            if amount <= 0 or not row["in_policy"]:
                continue
            lots: list[dict[str, Any]] = []
            for h in holdings:
                if (
                    h.get("allocation")
                    or ips.roll_up(h["asset_class"], targeted) != row["asset_class"]
                ):
                    continue
                quantity = Decimal(h["quantity"]) if h.get("quantity") else Decimal(0)
                if quantity <= 0 or h["cost_method"] != "fifo":
                    continue
                unit = Decimal(h["current_value"]) / quantity
                book = await self._portfolio.get_lots(user_id, h["id"])
                for lot in (book or {}).get("lots", []):
                    if not lot["is_open"]:
                        continue
                    held = Decimal(lot["quantity"])
                    lots.append(
                        {
                            "holding_id": h["id"],
                            "symbol": h["symbol"],
                            "lot_id": lot["id"],
                            "opened_on": lot["opened_on"],
                            "holding_period": lot.get("holding_period"),
                            "quantity": held,
                            "value": held * unit,
                            "cost": Decimal(lot["cost_base"]),
                        }
                    )
            picked, gain = ips.lots_to_sell(amount, lots, money_quantum)
            out.append(
                {
                    "asset_class": row["asset_class"],
                    "to_sell": str(amount.quantize(money_quantum)),
                    "lots": [
                        {
                            **p,
                            "quantity": f"{p['quantity'].normalize():f}",
                            "proceeds": str(p["proceeds"]),
                            "realised_gain": str(p["realised_gain"]),
                        }
                        for p in picked
                    ],
                    "realised_gain": str(gain.quantize(money_quantum)),
                }
            )
        return out
