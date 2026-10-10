"""Small fakes shared by tests that drive services against an in-memory unit of work."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
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
        return {
            **self.rows.get(user_id, {}),
            "id": user_id,
            "base_currency": await self.base_currency(user_id),
        }

    async def upsert(self, user_id: str, fields: dict[str, Any]) -> None:
        self.rows.setdefault(user_id, {}).update(fields)

    async def has_financial_data(self, user_id: str) -> bool:
        return self.has_data

    async def set_fi_assumptions(self, user_id: str, stored: dict[str, Any]) -> None:
        self.rows.setdefault(user_id, {})["fi_assumptions"] = stored


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


class FakeHoldingTransactions:
    """Holdings' transactions as the SQL repository keeps them: every column,
    with the defaults the table has, listed in the order they were recorded."""

    DEFAULTS: dict[str, Any] = {
        "quantity": None,
        "price": None,
        "fees_minor": 0,
        "amount_minor": None,
        "withholding_tax_minor": 0,
        "split_to": None,
        "split_from": None,
        "lots": [],
        "fx_rate": Decimal(1),
        "fx_rate_source": None,
        "note": None,
    }

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def list(self, user_id: str, holding_id: str | None = None) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.rows.values()
            if row["user_id"] == user_id and holding_id in (None, row["holding_id"])
        ]

    async def get(self, user_id: str, transaction_id: str) -> dict[str, Any] | None:
        row = self.rows.get(transaction_id)
        return dict(row) if row is not None and row["user_id"] == user_id else None

    async def save(self, user_id: str, transaction: dict[str, Any]) -> str:
        transaction_id = transaction.get("id") or str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        self.rows[transaction_id] = {
            **self.DEFAULTS,
            **transaction,
            "id": transaction_id,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
        }
        return transaction_id

    async def update(self, user_id: str, transaction_id: str, fields: dict[str, Any]) -> bool:
        if await self.get(user_id, transaction_id) is None:
            return False
        self.rows[transaction_id].update(fields, updated_at=datetime.now(UTC).isoformat())
        return True

    async def delete(self, user_id: str, transaction_id: str) -> bool:
        if await self.get(user_id, transaction_id) is None:
            return False
        del self.rows[transaction_id]
        return True


class FakeHoldings(FakeRecords):
    """Holdings, whose transactions go with them when they are deleted, as
    the table's ON DELETE CASCADE does."""

    def __init__(self, transactions: FakeHoldingTransactions) -> None:
        super().__init__(is_active=True)
        self.transactions = transactions
        self.locked: list[str] = []

    async def lock(self, user_id: str, holding_id: str) -> None:
        self.locked.append(holding_id)

    async def delete(self, user_id: str, record_id: str) -> None:
        await super().delete(user_id, record_id)
        for transaction_id in [
            t for t, row in self.transactions.rows.items() if row["holding_id"] == record_id
        ]:
            del self.transactions.rows[transaction_id]


class FakeHoldingPrices:
    """Closing prices as the SQL repository keeps them: one per user, symbol,
    currency and day (recording another replaces it), listed oldest first."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def upsert(self, user_id: str, price: dict[str, Any]) -> str:
        now = datetime.now(UTC).isoformat()
        for row in self.rows.values():
            if (row["user_id"], row["symbol"], row["currency"], row["price_date"]) == (
                user_id,
                price["symbol"],
                price["currency"],
                price["price_date"],
            ):
                row.update(price, updated_at=now)
                return row["id"]
        quote_id = str(uuid.uuid4())
        self.rows[quote_id] = {
            **price,
            "id": quote_id,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
        }
        return quote_id

    async def list(
        self,
        user_id: str,
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [
            dict(row)
            for row in self.rows.values()
            if row["user_id"] == user_id
            and symbol in (None, row["symbol"])
            and (start is None or row["price_date"] >= start)
            and (end is None or row["price_date"] <= end)
        ]
        return sorted(rows, key=lambda row: (row["price_date"], row["symbol"]))

    async def get(self, user_id: str, quote_id: str) -> dict[str, Any] | None:
        row = self.rows.get(quote_id)
        return dict(row) if row is not None and row["user_id"] == user_id else None

    async def delete(self, user_id: str, quote_id: str) -> bool:
        if await self.get(user_id, quote_id) is None:
            return False
        del self.rows[quote_id]
        return True


class FakeLedgerReader:
    """The slice of LedgerRepository that budgets and subscriptions read."""

    def __init__(self) -> None:
        self.accounts: list[Any] = []
        self.entries: list[Any] = []

    async def get_accounts(self, user_id: str, include_inactive: bool = False) -> list[Any]:
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


class FakeInsuranceTargets:
    """Coverage targets: at most one per user and policy type, as in the SQL
    repository, so setting one again replaces its amount and keeps its id."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}

    async def upsert(self, user_id: str, policy_type: str, target_amount_minor: int) -> str:
        now = datetime.now(UTC).isoformat()
        row = self.rows.setdefault(
            (user_id, policy_type),
            {"id": str(uuid.uuid4()), "user_id": user_id, "policy_type": policy_type},
        )
        row.update(target_amount_minor=target_amount_minor, updated_at=now)
        row.setdefault("created_at", now)
        return row["id"]

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        return [dict(row) for (owner, _), row in self.rows.items() if owner == user_id]

    async def delete(self, user_id: str, policy_type: str) -> None:
        self.rows.pop((user_id, policy_type), None)


class FakeRecordsUoW:
    """A unit of work over declared records, for the services that keep them.
    Every repository is named, so a service reaching for a wrong one fails."""

    def __init__(self, base_currency: str = "LKR") -> None:
        self.user_profiles = FakeProfiles(base_currency)
        self.ledger = FakeLedgerReader()
        self.budgets = FakeRecords()
        self.debts = FakeRecords(is_active=True)
        self.holding_transactions = FakeHoldingTransactions()
        self.holdings = FakeHoldings(self.holding_transactions)
        self.holding_prices = FakeHoldingPrices()
        self.recurring_subscriptions = FakeRecords(is_active=True)
        self.policies = FakeRecords(is_active=True)
        self.insurance_targets = FakeInsuranceTargets()

    async def __aenter__(self) -> FakeRecordsUoW:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass


class FakeLLM:
    """An LLMClient stand-in (application/ports.py): answers every `generate`
    with `reply`, or the next of `replies`, and keeps what it was asked."""

    def __init__(
        self,
        reply: str = "",
        *,
        replies: list[str] | None = None,
        provider: str = "anthropic",
        source: str = "platform",
    ) -> None:
        self.reply = reply
        self.replies = list(replies or [])
        self.provider = provider
        self.source = source
        self.requests: list[dict[str, Any]] = []

    @property
    def fingerprint(self) -> str:
        return f"fake:{self.provider}"

    def model_for(self, tier: str) -> str:
        return f"fake-{tier}"

    @property
    def prompts(self) -> list[str]:
        return [r["input"] for r in self.requests]

    async def generate(self, **request: Any) -> str:
        self.requests.append(request)
        return self.replies.pop(0) if self.replies else self.reply

    def chat_model(self, **options: Any) -> Any:
        raise NotImplementedError("FakeLLM has no chat model")
