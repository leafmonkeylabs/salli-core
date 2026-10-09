"""Small fakes shared by tests that drive services against an in-memory unit of work."""

from __future__ import annotations

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
