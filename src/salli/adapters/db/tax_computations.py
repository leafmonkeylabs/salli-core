"""
Storage for tax computations (application/ports.py `TaxComputationRepository`).

A computation is only ever added. Each names the rule set version that
computed it, by a composite foreign key with its owner, so a row can't name
another user's version. Every read names the owner too, and comes back with
the version's number and rule set, joined, so a result can say which rules
produced it.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from salli.adapters.db.models import TaxComputationORM, TaxRuleSetVersionORM
from salli.application.ports import TaxComputationRepository

#: What a caller supplies to `save`.
_FIELDS = (
    "country",
    "region",
    "year",
    "rule_set_version_id",
    "content_hash",
    "currency",
    "net_minor",
    "tax_payable_minor",
    "refund_due_minor",
    "lines",
    "inputs",
    "warnings",
)


def _row(row: TaxComputationORM, rule_set_id: str, version: int) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "country": row.country,
        "region": row.region,
        "year": row.year,
        "rule_set_id": rule_set_id,
        "rule_set_version_id": row.rule_set_version_id,
        "version": version,
        "content_hash": row.content_hash,
        "currency": row.currency,
        "net_minor": row.net_minor,
        "tax_payable_minor": row.tax_payable_minor,
        "refund_due_minor": row.refund_due_minor,
        "lines": row.lines,
        "inputs": row.inputs,
        "warnings": row.warnings,
        "created_at": row.created_at,
    }


def _joined() -> Select[tuple[TaxComputationORM, str, int]]:
    return select(
        TaxComputationORM, TaxRuleSetVersionORM.rule_set_id, TaxRuleSetVersionORM.version
    ).join(
        TaxRuleSetVersionORM,
        (TaxRuleSetVersionORM.id == TaxComputationORM.rule_set_version_id)
        & (TaxRuleSetVersionORM.user_id == TaxComputationORM.user_id),
    )


class SQLTaxComputationRepository(TaxComputationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, user_id: str, record: dict[str, Any]) -> dict[str, Any]:
        missing = [f for f in _FIELDS if f not in record]
        if missing:
            raise ValueError(f"A computation needs {', '.join(missing)}")
        orm = TaxComputationORM(
            id=str(uuid.uuid4()), user_id=user_id, **{f: record[f] for f in _FIELDS}
        )
        self._s.add(orm)
        await self._s.flush()
        found = await self.get(user_id, orm.id)
        assert found is not None
        return found

    async def get(self, user_id: str, computation_id: str) -> dict[str, Any] | None:
        result = await self._s.execute(
            _joined().where(
                TaxComputationORM.id == computation_id, TaxComputationORM.user_id == user_id
            )
        )
        found = result.first()
        return _row(*found) if found else None

    async def get_latest(
        self, user_id: str, country: str, region: str | None, year: str
    ) -> dict[str, Any] | None:
        result = await self._s.execute(
            _joined()
            .where(
                TaxComputationORM.user_id == user_id,
                TaxComputationORM.country == country,
                TaxComputationORM.region.is_not_distinct_from(region),
                TaxComputationORM.year == year,
            )
            .order_by(TaxComputationORM.created_at.desc(), TaxComputationORM.id.desc())
            .limit(1)
        )
        found = result.first()
        return _row(*found) if found else None

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        result = await self._s.execute(
            _joined()
            .where(TaxComputationORM.user_id == user_id)
            .order_by(TaxComputationORM.created_at.desc(), TaxComputationORM.id.desc())
        )
        return [_row(*found) for found in result.all()]

    async def latest_of_each(self) -> list[dict[str, Any]]:
        # DISTINCT ON keeps the first row of each group in the ORDER BY: the
        # newest computation of each user, jurisdiction and year.
        result = await self._s.execute(
            _joined()
            .distinct(
                TaxComputationORM.user_id,
                TaxComputationORM.country,
                TaxComputationORM.region,
                TaxComputationORM.year,
            )
            .order_by(
                TaxComputationORM.user_id,
                TaxComputationORM.country,
                TaxComputationORM.region,
                TaxComputationORM.year,
                TaxComputationORM.created_at.desc(),
                TaxComputationORM.id.desc(),
            )
        )
        return [_row(*found) for found in result.all()]
