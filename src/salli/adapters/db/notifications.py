"""
Storage for digests (application/ports.py `NotificationRepository`): a
person's preferences, the delivery log, and when the digest job last ran.

The log has at most one row per person and period (a unique key), and a send
is claimed by an atomic insert, or by an update that only matches a FAILED
row with attempts left, before anything goes. So a rerun, or two servers at
once, sends a period's digest once; a run that stops after claiming leaves
the row `sending`, which is never claimed again.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from salli.adapters.db.models import (
    InstanceSettingORM,
    NotificationDeliveryORM,
    NotificationPreferencesORM,
    PushDeviceORM,
    UserProfileORM,
)
from salli.application.ports import NotificationRepository

#: `instance_settings` key: when `send_due` last ran (ISO 8601, UTC).
LAST_RUN_KEY = "notifications.last_run_at"


def _preferences(row: NotificationPreferencesORM) -> dict[str, Any]:
    return {
        "enabled": row.enabled,
        "cadence": row.cadence,
        "weekday": row.weekday,
        "hour": row.hour,
        "items": list(row.items),
        "push": dict(row.push) if row.push else None,
        "updated_at": row.updated_at,
    }


def _delivery(row: NotificationDeliveryORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "period": row.period,
        "status": row.status,
        "attempts": row.attempts,
        "items": [dict(i) for i in row.items],
        "hash": row.hash,
        "created_at": row.created_at,
        "last_attempt_at": row.last_attempt_at,
        "sent_at": row.sent_at,
    }


class SQLNotificationRepository(NotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_preferences(self, user_id: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(NotificationPreferencesORM).where(
                    NotificationPreferencesORM.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        return None if row is None else _preferences(row)

    async def save_preferences(self, user_id: str, preferences: dict[str, Any]) -> None:
        now = dt.datetime.now(dt.UTC)
        values = {
            "enabled": bool(preferences["enabled"]),
            "cadence": str(preferences["cadence"]),
            "weekday": str(preferences["weekday"]),
            "hour": int(preferences["hour"]),
            "items": [str(i) for i in preferences["items"]],
            "push": preferences.get("push"),
            "updated_at": now,
        }
        await self._s.execute(
            insert(NotificationPreferencesORM)
            .values(user_id=user_id, created_at=now, **values)
            .on_conflict_do_update(index_elements=["user_id"], set_=values)
        )

    async def opted_in(self) -> list[dict[str, Any]]:
        rows = (
            await self._s.execute(
                select(NotificationPreferencesORM, UserProfileORM.time_zone)
                .join(UserProfileORM, UserProfileORM.id == NotificationPreferencesORM.user_id)
                .where(
                    NotificationPreferencesORM.enabled.is_(True),
                    UserProfileORM.time_zone.is_not(None),
                )
                .order_by(NotificationPreferencesORM.user_id)
            )
        ).all()
        return [
            {**_preferences(prefs), "user_id": prefs.user_id, "time_zone": time_zone}
            for prefs, time_zone in rows
        ]

    async def delivery(self, user_id: str, period: str) -> dict[str, Any] | None:
        row = (
            await self._s.execute(
                select(NotificationDeliveryORM).where(
                    NotificationDeliveryORM.user_id == user_id,
                    NotificationDeliveryORM.period == period,
                )
            )
        ).scalar_one_or_none()
        return None if row is None else _delivery(row)

    async def claim(
        self,
        user_id: str,
        *,
        delivery_id: str,
        period: str,
        items: list[dict[str, Any]],
        message_hash: str,
        now: dt.datetime,
        first: bool,
        max_attempts: int,
    ) -> int | None:
        if first:
            inserted = await self._s.execute(
                insert(NotificationDeliveryORM)
                .values(
                    id=delivery_id,
                    user_id=user_id,
                    period=period,
                    items=items,
                    hash=message_hash,
                    status="sending",
                    attempts=1,
                    created_at=now,
                    last_attempt_at=now,
                )
                .on_conflict_do_nothing()
                .returning(NotificationDeliveryORM.attempts)
            )
            attempt = inserted.scalar_one_or_none()
            if attempt is not None:
                return int(attempt)
        # A failed attempt with attempts left. Postgres re-checks the WHERE
        # once a concurrent claim commits, so only one run takes it.
        retried = await self._s.execute(
            update(NotificationDeliveryORM)
            .where(
                NotificationDeliveryORM.user_id == user_id,
                NotificationDeliveryORM.period == period,
                NotificationDeliveryORM.id == delivery_id,
                NotificationDeliveryORM.status == "failed",
                NotificationDeliveryORM.attempts < max_attempts,
            )
            .values(
                status="sending",
                attempts=NotificationDeliveryORM.attempts + 1,
                items=items,
                hash=message_hash,
                last_attempt_at=now,
            )
            .returning(NotificationDeliveryORM.attempts)
        )
        attempt = retried.scalar_one_or_none()
        return None if attempt is None else int(attempt)

    async def finish(self, user_id: str, delivery_id: str, status: str, now: dt.datetime) -> None:
        await self._s.execute(
            update(NotificationDeliveryORM)
            .where(
                NotificationDeliveryORM.user_id == user_id,
                NotificationDeliveryORM.id == delivery_id,
                NotificationDeliveryORM.status == "sending",
            )
            .values(status=status, sent_at=now if status == "sent" else None)
        )

    async def deliveries(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self._s.execute(
                select(NotificationDeliveryORM)
                .where(NotificationDeliveryORM.user_id == user_id)
                .order_by(NotificationDeliveryORM.created_at.desc(), NotificationDeliveryORM.id)
                .limit(limit)
            )
        ).scalars()
        return [_delivery(r) for r in rows]

    async def record_run(self, at: dt.datetime) -> None:
        stamp = at.astimezone(dt.UTC).isoformat()
        await self._s.execute(
            insert(InstanceSettingORM)
            .values(key=LAST_RUN_KEY, value=stamp, created_at=at)
            .on_conflict_do_update(index_elements=["key"], set_={"value": stamp})
        )

    async def last_run(self) -> dt.datetime | None:
        value = (
            await self._s.execute(
                select(InstanceSettingORM.value).where(InstanceSettingORM.key == LAST_RUN_KEY)
            )
        ).scalar_one_or_none()
        return None if value is None else dt.datetime.fromisoformat(value)

    async def add_device(
        self, user_id: str, token_hash: str, token: str, key_version: int | None, platform: str
    ) -> None:
        values = {
            "user_id": user_id,
            "token": token,
            "key_version": key_version,
            "platform": platform,
            "created_at": dt.datetime.now(dt.UTC),
        }
        await self._s.execute(
            insert(PushDeviceORM)
            .values(token_hash=token_hash, **values)
            .on_conflict_do_update(index_elements=[PushDeviceORM.token_hash], set_=values)
        )

    async def remove_device(self, user_id: str, token_hash: str) -> bool:
        result = await self._s.execute(
            delete(PushDeviceORM).where(
                PushDeviceORM.user_id == user_id, PushDeviceORM.token_hash == token_hash
            )
        )
        return bool(getattr(result, "rowcount", 0))

    async def devices(self, user_id: str) -> list[dict[str, Any]]:
        rows = (
            await self._s.execute(
                select(PushDeviceORM)
                .where(PushDeviceORM.user_id == user_id)
                .order_by(PushDeviceORM.created_at)
            )
        ).scalars()
        return [
            {
                "token_hash": r.token_hash,
                "token": r.token,
                "key_version": r.key_version,
                "platform": r.platform,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    async def device_users(self) -> list[dict[str, Any]]:
        rows = await self._s.execute(
            select(PushDeviceORM.user_id, UserProfileORM.time_zone)
            .outerjoin(UserProfileORM, UserProfileORM.id == PushDeviceORM.user_id)
            .distinct()
        )
        return [{"user_id": u, "time_zone": tz} for u, tz in rows.all()]
