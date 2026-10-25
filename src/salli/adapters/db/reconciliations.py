"""
Storage for bank reconciliation (application/ports.py `ReconciliationRepository`):
statements' balances, postings' cleared flag, and completed reconciliations.
Every read and write names the owner.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from salli.adapters.db.models import (
    JournalEntryORM,
    PostingORM,
    ReconciliationORM,
    StatementORM,
)
from salli.application.ports import ReconciliationRepository


def _statement(row: StatementORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "bank": row.bank,
        "account_id": row.account_id,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "opening_balance_minor": row.opening_balance_minor,
        "closing_balance_minor": row.closing_balance_minor,
    }


class SQLReconciliationRepository(ReconciliationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add_statement(self, user_id: str, record: dict[str, Any]) -> str:
        statement_id = str(uuid.uuid4())
        self._s.add(
            StatementORM(
                id=statement_id,
                user_id=user_id,
                storage_key="",
                bank=record.get("bank") or None,
                account_id=record["account_id"],
                kind="statement",
                period_start=record["period_start"],
                period_end=record["period_end"],
                opening_balance_minor=record["opening_balance_minor"],
                closing_balance_minor=record["closing_balance_minor"],
                status="reviewed",
            )
        )
        await self._s.flush()
        return statement_id

    async def statements(
        self, user_id: str, statement_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = (
            select(StatementORM, ReconciliationORM)
            .outerjoin(ReconciliationORM, ReconciliationORM.statement_id == StatementORM.id)
            .where(
                StatementORM.user_id == user_id,
                StatementORM.account_id.is_not(None),
                StatementORM.opening_balance_minor.is_not(None),
                StatementORM.closing_balance_minor.is_not(None),
            )
            .order_by(StatementORM.period_end.desc(), StatementORM.created_at.desc())
        )
        if statement_id is not None:
            query = query.where(StatementORM.id == statement_id)
        found: list[dict[str, Any]] = []
        for statement, done in (await self._s.execute(query)).all():
            row = _statement(statement)
            row["reconciliation"] = (
                None
                if done is None
                else {
                    "cleared_total_minor": done.cleared_total_minor,
                    "difference_minor": done.difference_minor,
                    "completed_by": done.completed_by,
                    "completed_at": done.completed_at.isoformat(),
                }
            )
            found.append(row)
        return found

    async def postings(
        self, user_id: str, account_id: str, from_date: str, to_date: str
    ) -> list[dict[str, Any]]:
        rows = await self._s.execute(
            select(PostingORM, JournalEntryORM)
            .join(JournalEntryORM, JournalEntryORM.id == PostingORM.entry_id)
            .where(
                JournalEntryORM.user_id == user_id,
                PostingORM.account_id == account_id,
                JournalEntryORM.entry_date >= from_date,
                JournalEntryORM.entry_date <= to_date,
            )
            .order_by(JournalEntryORM.entry_date, JournalEntryORM.created_at, PostingORM.id)
        )
        return [
            {
                "posting_id": p.id,
                "entry_id": e.id,
                "entry_date": e.entry_date,
                "description": e.description,
                "direction": p.direction,
                "amount_minor": p.amount_minor,
                "currency": p.currency,
                "cleared": p.cleared,
            }
            for p, e in rows.all()
        ]

    async def set_cleared(self, user_id: str, posting_ids: list[str], cleared: bool) -> None:
        owned = select(JournalEntryORM.id).where(JournalEntryORM.user_id == user_id)
        await self._s.execute(
            update(PostingORM)
            .where(PostingORM.id.in_(posting_ids), PostingORM.entry_id.in_(owned))
            .values(cleared=cleared)
        )

    async def complete(self, user_id: str, record: dict[str, Any]) -> None:
        self._s.add(ReconciliationORM(id=str(uuid.uuid4()), user_id=user_id, **record))
        await self._s.flush()
