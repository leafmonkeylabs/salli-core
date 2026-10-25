"""
Storage for tax returns and the payments made against them
(application/ports.py `TaxReturnRepository`). Rows are only ever added
(core_0037's trigger refuses anything else but erasure).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from salli.adapters.db.models import TaxReturnORM, TaxReturnPaymentORM
from salli.application.ports import TaxReturnRepository

_FIELDS = (
    "country",
    "region",
    "year",
    "period_start",
    "period_end",
    "version",
    "status",
    "supersedes_id",
    "reason",
    "computation_id",
    "rule_set_version_id",
    "content_hash",
    "snapshot",
    "snapshot_hash",
    "chain_head_hash",
    "provisional_note",
    "reference",
    "filed_on",
)

#: A region, or "" for none: the same expression in DISTINCT ON and ORDER BY.
_REGION = func.coalesce(TaxReturnORM.region, literal_column("''"))


def _row(row: TaxReturnORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        **{f: getattr(row, f) for f in _FIELDS},
        "created_at": row.created_at,
    }


def _payment(row: TaxReturnPaymentORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "return_id": row.return_id,
        "paid_on": row.paid_on,
        "amount_minor": row.amount_minor,
        "currency": row.currency,
        "reference": row.reference,
        "created_at": row.created_at,
    }


class SQLTaxReturnRepository(TaxReturnRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, user_id: str, record: dict[str, Any]) -> dict[str, Any]:
        orm = TaxReturnORM(
            id=str(uuid.uuid4()), user_id=user_id, **{f: record.get(f) for f in _FIELDS}
        )
        self._s.add(orm)
        await self._s.flush()
        return _row(orm)

    async def get(self, user_id: str, return_id: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(TaxReturnORM).where(
                    TaxReturnORM.id == return_id, TaxReturnORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        return _row(row) if row else None

    async def list(self, user_id: str, year: str | None = None) -> list[dict[str, Any]]:
        stmt = select(TaxReturnORM).where(TaxReturnORM.user_id == user_id)
        if year is not None:
            stmt = stmt.where(TaxReturnORM.year == year)
        stmt = stmt.order_by(
            TaxReturnORM.period_end.desc(),
            TaxReturnORM.country,
            TaxReturnORM.region,
            TaxReturnORM.version.desc(),
        )
        return [_row(r) for r in (await self._s.execute(stmt)).scalars().all()]

    async def latest_of_each(self, user_id: str) -> list[dict[str, Any]]:
        result = await self._s.execute(
            select(TaxReturnORM)
            .where(TaxReturnORM.user_id == user_id)
            .distinct(TaxReturnORM.country, _REGION, TaxReturnORM.year)
            .order_by(
                TaxReturnORM.country,
                _REGION,
                TaxReturnORM.year,
                TaxReturnORM.version.desc(),
            )
        )
        return [_row(r) for r in result.scalars().all()]

    async def add_payment(self, user_id: str, record: dict[str, Any]) -> dict[str, Any]:
        orm = TaxReturnPaymentORM(id=str(uuid.uuid4()), user_id=user_id, **record)
        self._s.add(orm)
        await self._s.flush()
        return _payment(orm)

    async def payments(self, user_id: str) -> list[dict[str, Any]]:
        result = await self._s.execute(
            select(TaxReturnPaymentORM)
            .where(TaxReturnPaymentORM.user_id == user_id)
            .order_by(TaxReturnPaymentORM.paid_on, TaxReturnPaymentORM.created_at)
        )
        return [_payment(r) for r in result.scalars().all()]
