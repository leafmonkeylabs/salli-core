"""
Storage for capital-market assumptions packs (application/ports.py
`CmaPackRepository`). Every query names the owner; nothing here can change a
pack's document once written (core_0035's trigger refuses it too).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from salli.adapters.db.models import CmaPackORM
from salli.application.ports import CmaPackRepository


def _row(row: CmaPackORM, *, content: bool) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": row.id,
        "name": row.name,
        "version": row.version,
        "content_hash": row.content_hash,
        "is_active": row.is_active,
        "created_at": row.created_at,
        "activated_at": row.activated_at,
    }
    if content:
        out["content"] = row.content
    return out


class SQLCmaPackRepository(CmaPackRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _one(self, user_id: str, pack_id: str) -> CmaPackORM | None:
        return (
            await self._s.execute(
                select(CmaPackORM).where(CmaPackORM.user_id == user_id, CmaPackORM.id == pack_id)
            )
        ).scalar_one_or_none()

    async def add(
        self, user_id: str, *, name: str, version: str, content: Any, content_hash: str
    ) -> dict[str, Any]:
        found = (
            await self._s.execute(
                select(CmaPackORM).where(
                    CmaPackORM.user_id == user_id, CmaPackORM.content_hash == content_hash
                )
            )
        ).scalar_one_or_none()
        if found is None:
            found = CmaPackORM(
                user_id=user_id,
                name=name,
                version=version,
                content=content,
                content_hash=content_hash,
                is_active=False,
                created_at=datetime.now(UTC),
            )
            self._s.add(found)
            await self._s.flush()
        return _row(found, content=True)

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        rows = (
            await self._s.execute(
                select(CmaPackORM)
                .where(CmaPackORM.user_id == user_id)
                .order_by(CmaPackORM.created_at.desc(), CmaPackORM.id)
            )
        ).scalars()
        return [_row(r, content=False) for r in rows]

    async def get(self, user_id: str, pack_id: str) -> dict[str, Any] | None:
        row = await self._one(user_id, pack_id)
        return None if row is None else _row(row, content=True)

    async def activate(self, user_id: str, pack_id: str | None) -> None:
        await self._s.execute(
            update(CmaPackORM)
            .where(CmaPackORM.user_id == user_id, CmaPackORM.is_active)
            .values(is_active=False)
        )
        await self._s.flush()
        if pack_id is not None:
            await self._s.execute(
                update(CmaPackORM)
                .where(CmaPackORM.user_id == user_id, CmaPackORM.id == pack_id)
                .values(is_active=True, activated_at=datetime.now(UTC))
            )
            await self._s.flush()

    async def active(self, user_id: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(CmaPackORM).where(CmaPackORM.user_id == user_id, CmaPackORM.is_active)
            )
        ).scalar_one_or_none()
        return None if row is None else _row(row, content=True)
