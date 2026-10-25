"""
The instance's usage counts, for its owner (`salli-server stats`;
business/metrics.md).

Counts only, over the seven days before `now`, from timestamps Salli already
stores: no one's id, email, description or amount is read out, and nothing
is sent anywhere. Off unless the owner sets SALLI_USAGE_COUNTERS.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select, union
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from salli.adapters.db.models import (
    JournalEntryORM,
    LoginSessionORM,
    OAuthGrantORM,
    PersonalAccessTokenORM,
    ReconciliationORM,
)


async def usage_counts(sessions: async_sessionmaker[AsyncSession], now: datetime) -> dict[str, int]:
    """Members who used the instance (a sign-in session, an app or AI
    connection, a token), statement entries posted, and reconciliations
    completed, in the week before `now`."""
    since = now - timedelta(days=7)
    used = union(
        *(
            select(t.user_id).where(t.last_used_at >= since, t.last_used_at <= now)
            for t in (LoginSessionORM, OAuthGrantORM, PersonalAccessTokenORM)
        ),
        select(LoginSessionORM.user_id).where(
            LoginSessionORM.created_at >= since, LoginSessionORM.created_at <= now
        ),
    ).subquery()
    async with sessions() as session:
        active = await session.scalar(select(func.count()).select_from(used))
        imported = await session.scalar(
            select(func.count())
            .select_from(JournalEntryORM)
            .where(
                JournalEntryORM.source == "statement",
                JournalEntryORM.created_at >= since,
                JournalEntryORM.created_at <= now,
            )
        )
        reconciled = await session.scalar(
            select(func.count())
            .select_from(ReconciliationORM)
            .where(ReconciliationORM.completed_at >= since, ReconciliationORM.completed_at <= now)
        )
    return {
        "active_members": active or 0,
        "entries_imported": imported or 0,
        "reconciliations_completed": reconciled or 0,
    }
