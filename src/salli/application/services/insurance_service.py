"""
InsuranceService — declares insurance policies and coverage targets, and
computes a coverage-gap report by aggregating active policies' coverage per
type against declared targets. The domain engine never touches the DB; this
service fetches policies/targets via its own uow_factory and calls
compute_report() (same pattern as BudgetService.get_summary).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.application.services.baseline_service import BaselineService
from salli.domain.currency import quantize
from salli.domain.fi.returns import PLANNING_AGE
from salli.domain.insurance import engine
from salli.domain.insurance.models import CoverageTarget, Policy
from salli.domain.money import from_minor, to_minor

ZERO = Decimal(0)

# Coverage, premiums and targets are kept in the user's base currency.


def _policy_view(p: dict[str, Any], currency: str) -> dict[str, Any]:
    return {
        "id": p["id"],
        "name": p["name"],
        "policy_type": p["policy_type"],
        "provider": p["provider"],
        "currency": currency,
        "coverage_amount": str(from_minor(p["coverage_amount_minor"], currency)),
        "premium_amount": str(from_minor(p["premium_amount_minor"], currency)),
        "premium_frequency": p["premium_frequency"],
        "expiry_date": p["expiry_date"],
        "is_active": p["is_active"],
        "created_at": p.get("created_at"),
        "updated_at": p.get("updated_at"),
    }


def _target_view(t: dict[str, Any], currency: str) -> dict[str, Any]:
    return {
        "id": t["id"],
        "policy_type": t["policy_type"],
        "currency": currency,
        "target_amount": str(from_minor(t["target_amount_minor"], currency)),
    }


def _to_domain_policy(p: dict[str, Any], currency: str) -> Policy:
    return Policy(
        name=p["name"],
        policy_type=p["policy_type"],
        provider=p["provider"],
        coverage_amount=from_minor(p["coverage_amount_minor"], currency),
        premium_amount=from_minor(p["premium_amount_minor"], currency),
        premium_frequency=p["premium_frequency"],
        expiry_date=p["expiry_date"],
        is_active=p["is_active"],
    )


def _to_domain_target(t: dict[str, Any], currency: str) -> CoverageTarget:
    return CoverageTarget(
        policy_type=t["policy_type"], target_amount=from_minor(t["target_amount_minor"], currency)
    )


def _protection_months(baseline: Any, replacement_years: int, benefit_years: int | None) -> int:
    """How long disability cover replaces income: the chosen benefit period;
    else to the planning age (the plan's, else the placeholder's) from the
    date of birth; else `replacement_years`."""
    if benefit_years is not None:
        return benefit_years * 12
    born = baseline.plan.born
    if born is None:
        return replacement_years * 12
    age = baseline.plan.planning_age or PLANNING_AGE
    as_of = baseline.as_of
    return max(0, (born.year + age - as_of.year) * 12 + born.month - as_of.month)


class InsuranceService:
    def __init__(
        self, uow_factory: Callable[[], Any], baselines: BaselineService | None = None
    ) -> None:
        self._uow_factory = uow_factory
        # The figures a needs analysis starts from.
        self._baselines = baselines

    async def _needs(
        self,
        user_id: str,
        replacement_years: int,
        benefit_years: int | None = None,
        sick_pay: Decimal = ZERO,
    ) -> tuple[str, engine.Needs]:
        if self._baselines is None:
            raise RuntimeError("InsuranceService needs the baseline for a needs analysis")
        baseline = await self._baselines.build(user_id)
        currency = baseline.currency
        async with self._uow_factory() as uow:
            goals = await uow.goals.list(user_id, active_only=True)
            policies = await uow.policies.list(user_id, active_only=True)
        to_fund = sum(
            (
                max(
                    from_minor(g["target_amount_minor"] - g["current_amount_minor"], currency), ZERO
                )
                for g in goals
            ),
            ZERO,
        )

        def held(kind: str) -> Decimal:
            return sum(
                (
                    from_minor(p["coverage_amount_minor"], currency)
                    for p in policies
                    if p["policy_type"] == kind
                ),
                ZERO,
            )

        investments = sum((b.owned for b in baseline.balances if b.role == "investment"), ZERO)
        return currency, engine.needs(
            baseline.flows.income,
            baseline.flows.expenses,
            baseline.total_liabilities,
            to_fund,
            baseline.liquid + investments,
            held("life"),
            replacement_years,
            baseline.net_worth,
            held("liability"),
            _protection_months(baseline, replacement_years, benefit_years),
            held("income_protection"),
            sick_pay,
        )

    async def get_needs(
        self,
        user_id: str,
        replacement_years: int = 10,
        benefit_years: int | None = None,
        sick_pay: Decimal = ZERO,
    ) -> dict[str, Any]:
        """Life cover, income protection and liability cover, as figures from
        the baseline: income replacement for `replacement_years`, debts and
        the active goals still to fund, less cash, savings and investments; a
        month's spending; and net worth, what a claim could reach. Never a
        product."""
        currency, result = await self._needs(user_id, replacement_years, benefit_years, sick_pay)

        def money(value: Decimal) -> str:
            return str(quantize(value, currency, strict=False))

        return {
            "currency": currency,
            "replacement_years": result.replacement_years,
            "income_replacement": money(result.income_replacement),
            "debts": money(result.debts),
            "goals": money(result.goals),
            "assets": money(result.assets),
            "life_cover_need": money(result.life_cover_need),
            "life_cover_held": money(result.life_cover_held),
            "life_cover_gap": money(result.life_cover_gap),
            "income_protection_monthly": money(result.income_protection_monthly),
            "liability_cover_need": money(result.liability_cover_need),
            "liability_cover_held": money(result.liability_cover_held),
            "liability_cover_gap": money(result.liability_cover_gap),
            "protection_months": result.protection_months,
            "sick_pay": money(result.sick_pay),
            "protection_need": money(result.protection_need),
            "protection_held": money(result.protection_held),
            "protection_gap": money(result.protection_gap),
        }

    async def add_policy(self, user_id: str, data: dict[str, Any]) -> str:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            policy = {
                "name": data["name"],
                "policy_type": data["policy_type"],
                "provider": data["provider"],
                "coverage_amount_minor": to_minor(Decimal(str(data["coverage_amount"])), currency),
                "premium_amount_minor": to_minor(Decimal(str(data["premium_amount"])), currency),
                "premium_frequency": data["premium_frequency"],
                "expiry_date": data["expiry_date"],
            }
            return await uow.policies.save(user_id, policy)

    async def list_policies(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            policies = await uow.policies.list(user_id, active_only)
        return [_policy_view(p, currency) for p in policies]

    async def get_policy(self, user_id: str, policy_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            p = await uow.policies.get(user_id, policy_id)
        return _policy_view(p, currency) if p else None

    async def update_policy(self, user_id: str, policy_id: str, data: dict[str, Any]) -> None:
        updates: dict[str, Any] = {}
        if "name" in data:
            updates["name"] = data["name"]
        if "policy_type" in data:
            updates["policy_type"] = data["policy_type"]
        if "provider" in data:
            updates["provider"] = data["provider"]
        if "premium_frequency" in data:
            updates["premium_frequency"] = data["premium_frequency"]
        if "expiry_date" in data:
            updates["expiry_date"] = data["expiry_date"]
        if "is_active" in data:
            updates["is_active"] = data["is_active"]
        async with self._uow_factory() as uow:
            if "coverage_amount" in data or "premium_amount" in data:
                currency = await uow.user_profiles.base_currency(user_id)
                if "coverage_amount" in data:
                    updates["coverage_amount_minor"] = to_minor(
                        Decimal(str(data["coverage_amount"])), currency
                    )
                if "premium_amount" in data:
                    updates["premium_amount_minor"] = to_minor(
                        Decimal(str(data["premium_amount"])), currency
                    )
            await uow.policies.update(user_id, policy_id, updates)

    async def delete_policy(self, user_id: str, policy_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.policies.delete(user_id, policy_id)

    async def set_target(self, user_id: str, policy_type: str, target_amount: Decimal) -> str:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            return await uow.insurance_targets.upsert(
                user_id, policy_type, to_minor(target_amount, currency)
            )

    async def list_targets(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            targets = await uow.insurance_targets.list(user_id)
        return [_target_view(t, currency) for t in targets]

    async def delete_target(self, user_id: str, policy_type: str) -> None:
        async with self._uow_factory() as uow:
            await uow.insurance_targets.delete(user_id, policy_type)

    async def get_report(self, user_id: str, today: str) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            policies = await uow.policies.list(user_id, active_only=True)
            targets = await uow.insurance_targets.list(user_id)

        # Life and liability cover without a typed target: the needs analysis's.
        needed = None if self._baselines is None else (await self._needs(user_id, 10))[1]
        report = engine.compute_report(
            [_to_domain_policy(p, currency) for p in policies],
            [_to_domain_target(t, currency) for t in targets],
            today,
            needed=needed,
        )
        return {
            "currency": currency,
            "lines": [
                {
                    "policy_type": line.policy_type,
                    "target_amount": str(quantize(line.target_amount, currency, strict=False)),
                    "actual_coverage": str(quantize(line.actual_coverage, currency, strict=False)),
                    "gap": str(quantize(line.gap, currency, strict=False)),
                    "basis": line.basis,
                }
                for line in report.lines
            ],
            "missing_types": report.missing_types,
            "expiring_soon": [
                {
                    "policy_name": a.policy_name,
                    "policy_type": a.policy_type,
                    "expiry_date": a.expiry_date,
                    "days_until_expiry": a.days_until_expiry,
                }
                for a in report.expiring_soon
            ],
        }
