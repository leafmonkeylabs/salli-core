"""
Storage for the operator's support sessions (application/ports.py
`SupportSessionRepository`): ended by setting `ended_at`, never deleted but
on erasure. The reads made under one are its rows in the audit log.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from salli.adapters.db.models import AuditLogORM, SupportSessionORM
from salli.application.ports import SupportSessionRepository

#: The audit log's action for a read made under a support session.
READ = "support.read"


def _row(row: SupportSessionORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "reason": row.reason,
        "opened_at": row.opened_at,
        "expires_at": row.expires_at,
        "ended_at": row.ended_at,
        "ended_by": row.ended_by,
    }


class SQLSupportSessionRepository(SupportSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def open(
        self,
        user_id: str,
        reason: str,
        token_hash: str,
        opened_at: datetime,
        expires_at: datetime,
    ) -> dict[str, Any]:
        row = SupportSessionORM(
            user_id=user_id,
            reason=reason,
            token_hash=token_hash,
            opened_at=opened_at,
            expires_at=expires_at,
        )
        self._s.add(row)
        await self._s.flush()
        return _row(row)

    async def by_token(self, token_hash: str) -> dict[str, Any] | None:
        row = await self._s.scalar(
            select(SupportSessionORM).where(SupportSessionORM.token_hash == token_hash)
        )
        return None if row is None else _row(row)

    async def list(self, user_id: str | None = None) -> list[dict[str, Any]]:
        query = select(SupportSessionORM).order_by(SupportSessionORM.opened_at.desc())
        if user_id is not None:
            query = query.where(SupportSessionORM.user_id == user_id)
        sessions = [_row(r) for r in (await self._s.execute(query)).scalars()]
        if not sessions:
            return []
        reads = await self._s.execute(
            select(AuditLogORM.params, AuditLogORM.created_at)
            .where(
                AuditLogORM.action == READ,
                AuditLogORM.user_id.in_({s["user_id"] for s in sessions}),
            )
            .order_by(AuditLogORM.seq)
        )
        by_session: dict[str, list[dict[str, Any]]] = {}
        for params, at in reads:
            by_session.setdefault(params.get("session_id"), []).append(
                {"at": at, "path": params.get("path")}
            )
        return [{**s, "reads": by_session.get(s["id"], [])} for s in sessions]

    async def end(
        self, session_id: str, by: str, at: datetime, user_id: str | None = None
    ) -> dict[str, Any] | None:
        query = select(SupportSessionORM).where(
            SupportSessionORM.id == session_id, SupportSessionORM.ended_at.is_(None)
        )
        if user_id is not None:
            query = query.where(SupportSessionORM.user_id == user_id)
        row = await self._s.scalar(query)
        if row is None:
            return None
        row.ended_at, row.ended_by = min(at, row.expires_at), by
        await self._s.flush()
        return _row(row)

    async def lapsed(self, now: datetime) -> list[dict[str, Any]]:
        rows = await self._s.execute(
            select(SupportSessionORM).where(
                SupportSessionORM.ended_at.is_(None), SupportSessionORM.expires_at <= now
            )
        )
        return [_row(r) for r in rows.scalars()]
