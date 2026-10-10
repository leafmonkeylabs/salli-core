"""
Storage for tax rule sets (application/ports.py `TaxRuleSetRepository`).

Every query names the owner. A version is always looked up by its id *and*
its `user_id` (which the composite foreign key keeps equal to its set's), and
a set by its id and `user_id`, so no id of someone else's reaches anything:
it is simply not found. This module is the only place that writes the two
tables, and nothing in it can change a version's content once written.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from salli.adapters.db.models import TaxRuleSetORM, TaxRuleSetVersionORM
from salli.application.ports import RuleSetExists, TaxRuleSetRepository

#: The fields of a version that change as it moves through its lifecycle.
#: Content, its hash, its set, owner, number and author never do.
_LIFECYCLE_FIELDS = frozenset(
    {"status", "validation", "proposed_at", "activated_at", "superseded_at"}
)


def _set(row: TaxRuleSetORM, versions: Sequence[TaxRuleSetVersionORM]) -> dict[str, Any]:
    return {
        "id": row.id,
        "country": row.country,
        "region": row.region,
        "year_label": row.year_label,
        "name": row.name,
        "active_version_id": row.active_version_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "versions": [_version(v, content=False) for v in versions],
    }


def _version(row: TaxRuleSetVersionORM, *, content: bool) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": row.id,
        "rule_set_id": row.rule_set_id,
        "version": row.version,
        "content_hash": row.content_hash,
        "status": row.status,
        "author_kind": row.author_kind,
        "author_name": row.author_name,
        "change_note": row.change_note,
        "created_at": row.created_at,
        "proposed_at": row.proposed_at,
        "activated_at": row.activated_at,
        "superseded_at": row.superseded_at,
    }
    if content:
        out["content"] = row.content
        out["validation"] = row.validation
    return out


class SQLTaxRuleSetRepository(TaxRuleSetRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _versions(
        self, user_id: str, rule_set_ids: Sequence[str]
    ) -> dict[str, list[TaxRuleSetVersionORM]]:
        if not rule_set_ids:
            return {}
        rows = (
            await self._s.execute(
                select(TaxRuleSetVersionORM)
                .where(
                    TaxRuleSetVersionORM.user_id == user_id,
                    TaxRuleSetVersionORM.rule_set_id.in_(rule_set_ids),
                )
                .order_by(TaxRuleSetVersionORM.rule_set_id, TaxRuleSetVersionORM.version)
            )
        ).scalars()
        grouped: dict[str, list[TaxRuleSetVersionORM]] = {i: [] for i in rule_set_ids}
        for row in rows:
            grouped[row.rule_set_id].append(row)
        return grouped

    async def list_sets(self, user_id: str) -> list[dict[str, Any]]:
        rows = list(
            (
                await self._s.execute(
                    select(TaxRuleSetORM)
                    .where(TaxRuleSetORM.user_id == user_id)
                    .order_by(
                        TaxRuleSetORM.country, TaxRuleSetORM.year_label, TaxRuleSetORM.created_at
                    )
                )
            ).scalars()
        )
        versions = await self._versions(user_id, [r.id for r in rows])
        return [_set(r, versions[r.id]) for r in rows]

    async def _one(self, stmt: Any, user_id: str, lock: bool) -> dict[str, Any] | None:
        if lock:
            stmt = stmt.with_for_update()
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _set(row, (await self._versions(user_id, [row.id]))[row.id])

    async def get_set(
        self, user_id: str, rule_set_id: str, *, lock: bool = False
    ) -> dict[str, Any] | None:
        stmt = select(TaxRuleSetORM).where(
            TaxRuleSetORM.id == rule_set_id, TaxRuleSetORM.user_id == user_id
        )
        return await self._one(stmt, user_id, lock)

    async def find_set(
        self, user_id: str, country: str, region: str | None, year_label: str, *, lock: bool = False
    ) -> dict[str, Any] | None:
        stmt = select(TaxRuleSetORM).where(
            TaxRuleSetORM.user_id == user_id,
            TaxRuleSetORM.country == country,
            func.coalesce(TaxRuleSetORM.region, "") == (region or ""),
            TaxRuleSetORM.year_label == year_label,
        )
        return await self._one(stmt, user_id, lock)

    async def create_set(
        self, user_id: str, country: str, region: str | None, year_label: str, name: str
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        row = TaxRuleSetORM(
            id=str(uuid.uuid4()),
            user_id=user_id,
            country=country,
            region=region,
            year_label=year_label,
            name=name,
            created_at=now,
            updated_at=now,
        )
        # In a savepoint, so losing a race to create the same set leaves the
        # rest of the unit of work usable.
        try:
            async with self._s.begin_nested():
                self._s.add(row)
                await self._s.flush()
        except IntegrityError:
            existing = await self.find_set(user_id, country, region, year_label)
            if existing is None:  # some other constraint: not ours to explain
                raise
            raise RuleSetExists(existing["id"]) from None
        return _set(row, [])

    async def get_version(self, user_id: str, version_id: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(TaxRuleSetVersionORM).where(
                    TaxRuleSetVersionORM.id == version_id,
                    TaxRuleSetVersionORM.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        return _version(row, content=True) if row is not None else None

    async def add_version(
        self, user_id: str, rule_set_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        latest = (
            await self._s.execute(
                select(func.coalesce(func.max(TaxRuleSetVersionORM.version), 0)).where(
                    TaxRuleSetVersionORM.rule_set_id == rule_set_id,
                    TaxRuleSetVersionORM.user_id == user_id,
                )
            )
        ).scalar_one()
        row = TaxRuleSetVersionORM(
            id=str(uuid.uuid4()),
            rule_set_id=rule_set_id,
            user_id=user_id,
            version=int(latest) + 1,
            content=fields["content"],
            content_hash=fields.get("content_hash"),
            status=fields["status"],
            validation=fields["validation"],
            author_kind=fields["author_kind"],
            author_name=fields.get("author_name"),
            change_note=fields.get("change_note"),
            created_at=datetime.now(UTC),
        )
        self._s.add(row)
        await self._s.flush()
        await self._touch(user_id, rule_set_id)
        return _version(row, content=True)

    async def update_version(self, user_id: str, version_id: str, fields: dict[str, Any]) -> bool:
        unknown = set(fields) - _LIFECYCLE_FIELDS
        if unknown:
            raise ValueError(f"A version's {', '.join(sorted(unknown))} cannot be changed")
        row = (
            await self._s.execute(
                select(TaxRuleSetVersionORM).where(
                    TaxRuleSetVersionORM.id == version_id,
                    TaxRuleSetVersionORM.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        for key, value in fields.items():
            setattr(row, key, value)
        await self._s.flush()
        await self._touch(user_id, row.rule_set_id)
        return True

    async def set_active(self, user_id: str, rule_set_id: str, version_id: str | None) -> None:
        row = (
            await self._s.execute(
                select(TaxRuleSetORM).where(
                    TaxRuleSetORM.id == rule_set_id, TaxRuleSetORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return
        row.active_version_id = version_id
        row.updated_at = datetime.now(UTC)
        await self._s.flush()

    async def _touch(self, user_id: str, rule_set_id: str) -> None:
        row = (
            await self._s.execute(
                select(TaxRuleSetORM).where(
                    TaxRuleSetORM.id == rule_set_id, TaxRuleSetORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            row.updated_at = datetime.now(UTC)
            await self._s.flush()

    async def declared_roles(self, user_id: str) -> set[str]:
        # Only documents that matched the schema (a content hash): their role
        # keys are known to be well formed. And only versions that aren't
        # superseded: those are history. jsonb_array_elements of a missing
        # `roles` is no rows.
        rows = await self._s.execute(
            text(
                "SELECT DISTINCT role ->> 'key' FROM tax_rule_set_versions v"
                " CROSS JOIN LATERAL jsonb_array_elements(v.content -> 'roles') AS role"
                " WHERE v.user_id = :user_id AND v.content_hash IS NOT NULL"
                " AND v.status <> 'superseded'"
            ),
            {"user_id": user_id},
        )
        return {str(key) for (key,) in rows if key}

    async def active_versions(self, user_id: str) -> list[dict[str, Any]]:
        rows = (
            await self._s.execute(
                select(TaxRuleSetORM, TaxRuleSetVersionORM)
                .join(
                    TaxRuleSetVersionORM,
                    (TaxRuleSetVersionORM.id == TaxRuleSetORM.active_version_id)
                    & (TaxRuleSetVersionORM.user_id == TaxRuleSetORM.user_id),
                )
                .where(TaxRuleSetORM.user_id == user_id)
                .order_by(TaxRuleSetORM.country, TaxRuleSetORM.year_label, TaxRuleSetORM.region)
            )
        ).all()
        return [
            {**_set(rule_set, []), "version": _version(version, content=True)}
            for rule_set, version in rows
        ]

    async def export(self, user_id: str) -> list[dict[str, Any]]:
        sets = (
            await self._s.execute(
                select(TaxRuleSetORM)
                .where(TaxRuleSetORM.user_id == user_id)
                .order_by(TaxRuleSetORM.created_at)
            )
        ).scalars()
        rows = list(sets)
        versions = await self._versions(user_id, [r.id for r in rows])
        return [
            {
                **_set(r, []),
                "versions": [_version(v, content=True) for v in versions[r.id]],
            }
            for r in rows
        ]
