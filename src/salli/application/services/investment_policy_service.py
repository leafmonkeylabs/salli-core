"""
InvestmentPolicyService — the person's investment policy statement (stored as
versions, never changed), the drift report against it, and the risk profile
shown beside it: the questionnaire's tolerance, the capacity the baseline
shows, and the lower of the two (domain/risk/capacity.py). The profile gates
nothing; a policy whose equity target is above its band is flagged.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from decimal import Decimal
from typing import Any, cast

from salli.application.services.baseline_service import BaselineService
from salli.application.services.portfolio_service import PortfolioService
from salli.domain.currency import quantum
from salli.domain.portfolio import policy as ips
from salli.domain.risk import capacity
from salli.domain.risk.models import RiskCategory


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
        document = ips.Policy.model_validate(content).document()
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
        result = capacity.compute(emergency, variation, horizon, service)
        tolerance = cast(RiskCategory | None, profile.get("risk_category"))
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
            "profile": capacity.profile(tolerance, result.category),
            "equity_max": str(capacity.EQUITY_BANDS[capacity.profile(tolerance, result.category)]),
        }

    async def drift(self, user_id: str) -> dict[str, Any] | None:
        """The portfolio against the policy in force, with the risk profile
        beside it; None when there is no policy."""
        current = await self.current(user_id)
        if current is None:
            return None
        policy = ips.Policy.model_validate(current["content"])
        summary = await self._portfolio.get_summary(user_id)
        values = {a["asset_class"]: Decimal(a["current_value"]) for a in summary["allocation"]}
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
            "notes": summary["notes"],
        }
