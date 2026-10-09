"""Small fakes shared by tests that drive services against an in-memory unit of work."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any


class FakeProfiles:
    """The slice of UserProfileRepository the money path reads: whose ledger is
    kept in which currency. Every user here is on `base_currency`."""

    def __init__(self, base_currency: str = "LKR", *, has_data: bool = False) -> None:
        self.base = base_currency
        self.has_data = has_data
        self.rows: dict[str, dict[str, Any]] = {}

    async def base_currency(self, user_id: str) -> str:
        return self.rows.get(user_id, {}).get("base_currency", self.base)

    async def get(self, user_id: str) -> dict[str, Any] | None:
        return {"id": user_id, "base_currency": await self.base_currency(user_id)}

    async def upsert(self, user_id: str, fields: dict[str, Any]) -> None:
        self.rows.setdefault(user_id, {}).update(fields)

    async def has_financial_data(self, user_id: str) -> bool:
        return self.has_data


class FakeRecords:
    """Things a user declares (budgets, debts, holdings, …) kept the way the SQL
    repositories hand them back: the stored fields plus the owner and ISO-8601
    `created_at`/`updated_at`. `defaults` are the columns' own defaults."""

    def __init__(self, **defaults: Any) -> None:
        self.defaults = defaults
        self.rows: dict[str, dict[str, Any]] = {}

    async def save(self, user_id: str, record: dict[str, Any]) -> str:
        record_id = record.get("id") or str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        self.rows[record_id] = {
            **self.defaults,
            **record,
            "id": record_id,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
        }
        return record_id

    async def get(self, user_id: str, record_id: str) -> dict[str, Any] | None:
        row = self.rows.get(record_id)
        return dict(row) if row is not None and row["user_id"] == user_id else None

    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.rows.values()
            if row["user_id"] == user_id and (not active_only or row.get("is_active", True))
        ]

    async def update(self, user_id: str, record_id: str, updates: dict[str, Any]) -> None:
        if await self.get(user_id, record_id) is None:
            return
        row = self.rows[record_id]
        row.update({k: v for k, v in updates.items() if v is not None})
        row["updated_at"] = datetime.now(UTC).isoformat()

    async def delete(self, user_id: str, record_id: str) -> None:
        if await self.get(user_id, record_id) is not None:
            del self.rows[record_id]


class FakeLedgerReader:
    """The slice of LedgerRepository that budgets and subscriptions read."""

    def __init__(self) -> None:
        self.accounts: list[Any] = []
        self.entries: list[Any] = []

    async def get_accounts(self, user_id: str) -> list[Any]:
        return self.accounts

    async def get_entries(
        self, user_id: str, from_date: str | None = None, to_date: str | None = None
    ) -> list[Any]:
        return [
            e
            for e in self.entries
            if (from_date is None or e.entry_date >= from_date)
            and (to_date is None or e.entry_date <= to_date)
        ]


class FakeRecordsUoW:
    """A unit of work over declared records, for the services that keep them.
    Every repository is named, so a service reaching for a wrong one fails."""

    def __init__(self, base_currency: str = "LKR") -> None:
        self.user_profiles = FakeProfiles(base_currency)
        self.ledger = FakeLedgerReader()
        self.budgets = FakeRecords()
        self.debts = FakeRecords(is_active=True)

    async def __aenter__(self) -> FakeRecordsUoW:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass
