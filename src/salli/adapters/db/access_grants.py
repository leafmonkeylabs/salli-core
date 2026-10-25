"""
Storage for read-only access grants (application/ports.py
`AccessGrantRepository`): at most one live grant a pair (core_0036's partial
unique index), ended by setting `revoked_at`, never deleted but on erasure.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from salli.adapters.db.models import AccessGrantORM
from salli.application.ports import AccessGrantRepository


def _row(row: AccessGrantORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "grantor_id": row.grantor_id,
        "grantee_id": row.grantee_id,
        "created_at": row.created_at,
    }


class SQLAccessGrantRepository(AccessGrantRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _live(self, *where: Any) -> list[AccessGrantORM]:
        query = select(AccessGrantORM).where(AccessGrantORM.revoked_at.is_(None), *where)
        return list((await self._s.execute(query)).scalars())

    async def create(self, grantor_id: str, grantee_id: str) -> dict[str, Any]:
        existing = await self._live(
            AccessGrantORM.grantor_id == grantor_id, AccessGrantORM.grantee_id == grantee_id
        )
        if existing:
            return _row(existing[0])
        row = AccessGrantORM(
            grantor_id=grantor_id, grantee_id=grantee_id, created_at=datetime.now(UTC)
        )
        self._s.add(row)
        await self._s.flush()
        return _row(row)

    async def list_for(self, user_id: str) -> list[dict[str, Any]]:
        rows = await self._live(
            or_(AccessGrantORM.grantor_id == user_id, AccessGrantORM.grantee_id == user_id)
        )
        return [_row(r) for r in sorted(rows, key=lambda r: r.created_at, reverse=True)]

    async def is_live(self, grantor_id: str, grantee_id: str) -> bool:
        return bool(
            await self._live(
                AccessGrantORM.grantor_id == grantor_id, AccessGrantORM.grantee_id == grantee_id
            )
        )

    async def revoke(self, user_id: str, grant_id: str) -> dict[str, Any] | None:
        rows = await self._live(
            AccessGrantORM.id == grant_id,
            or_(AccessGrantORM.grantor_id == user_id, AccessGrantORM.grantee_id == user_id),
        )
        if not rows:
            return None
        rows[0].revoked_at = datetime.now(UTC)
        await self._s.flush()
        return _row(rows[0])
