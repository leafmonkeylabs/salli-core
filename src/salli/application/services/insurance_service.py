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

from salli.domain.insurance import engine
from salli.domain.insurance.models import CoverageTarget, Policy
from salli.domain.money import to_minor


def _policy_view(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": p["id"],
        "name": p["name"],
        "policy_type": p["policy_type"],
        "provider": p["provider"],
        "coverage_amount": str(Decimal(p["coverage_amount_minor"]) / 100),
        "premium_amount": str(Decimal(p["premium_amount_minor"]) / 100),
        "premium_frequency": p["premium_frequency"],
        "expiry_date": p["expiry_date"],
        "is_active": p["is_active"],
        "created_at": p.get("created_at"),
        "updated_at": p.get("updated_at"),
    }


def _target_view(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": t["id"],
        "policy_type": t["policy_type"],
        "target_amount": str(Decimal(t["target_amount_minor"]) / 100),
    }


def _to_domain_policy(p: dict[str, Any]) -> Policy:
    return Policy(
        name=p["name"],
        policy_type=p["policy_type"],
        provider=p["provider"],
        coverage_amount=Decimal(p["coverage_amount_minor"]) / 100,
        premium_amount=Decimal(p["premium_amount_minor"]) / 100,
        premium_frequency=p["premium_frequency"],
        expiry_date=p["expiry_date"],
        is_active=p["is_active"],
    )


def _to_domain_target(t: dict[str, Any]) -> CoverageTarget:
    return CoverageTarget(
        policy_type=t["policy_type"], target_amount=Decimal(t["target_amount_minor"]) / 100
    )


class InsuranceService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    async def add_policy(self, user_id: str, data: dict[str, Any]) -> str:
        policy = {
            "name": data["name"],
            "policy_type": data["policy_type"],
            "provider": data["provider"],
            "coverage_amount_minor": to_minor(Decimal(str(data["coverage_amount"]))),
            "premium_amount_minor": to_minor(Decimal(str(data["premium_amount"]))),
            "premium_frequency": data["premium_frequency"],
            "expiry_date": data["expiry_date"],
        }
        async with self._uow_factory() as uow:
            return await uow.policies.save(user_id, policy)

    async def list_policies(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            policies = await uow.policies.list(user_id, active_only)
        return [_policy_view(p) for p in policies]

    async def get_policy(self, user_id: str, policy_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            p = await uow.policies.get(user_id, policy_id)
        return _policy_view(p) if p else None

    async def update_policy(self, user_id: str, policy_id: str, data: dict[str, Any]) -> None:
        updates: dict[str, Any] = {}
        if "name" in data:
            updates["name"] = data["name"]
        if "policy_type" in data:
            updates["policy_type"] = data["policy_type"]
        if "provider" in data:
            updates["provider"] = data["provider"]
        if "coverage_amount" in data:
            updates["coverage_amount_minor"] = to_minor(Decimal(str(data["coverage_amount"])))
        if "premium_amount" in data:
            updates["premium_amount_minor"] = to_minor(Decimal(str(data["premium_amount"])))
        if "premium_frequency" in data:
            updates["premium_frequency"] = data["premium_frequency"]
        if "expiry_date" in data:
            updates["expiry_date"] = data["expiry_date"]
        if "is_active" in data:
            updates["is_active"] = data["is_active"]
        async with self._uow_factory() as uow:
            await uow.policies.update(user_id, policy_id, updates)

    async def delete_policy(self, user_id: str, policy_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.policies.delete(user_id, policy_id)

    async def set_target(self, user_id: str, policy_type: str, target_amount: Decimal) -> str:
        async with self._uow_factory() as uow:
            return await uow.insurance_targets.upsert(user_id, policy_type, to_minor(target_amount))

    async def list_targets(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            targets = await uow.insurance_targets.list(user_id)
        return [_target_view(t) for t in targets]

    async def delete_target(self, user_id: str, policy_type: str) -> None:
        async with self._uow_factory() as uow:
            await uow.insurance_targets.delete(user_id, policy_type)

    async def get_report(self, user_id: str, today: str) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            policies = await uow.policies.list(user_id, active_only=True)
            targets = await uow.insurance_targets.list(user_id)

        report = engine.compute_report(
            [_to_domain_policy(p) for p in policies],
            [_to_domain_target(t) for t in targets],
            today,
        )
        return {
            "lines": [
                {
                    "policy_type": line.policy_type,
                    "target_amount": str(line.target_amount),
                    "actual_coverage": str(line.actual_coverage),
                    "gap": str(line.gap),
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
