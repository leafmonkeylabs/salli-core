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


class FakeFx:
    """The FX port (application/ports.FxRatePort) from a table of published
    rates: `(from, to, date)` → `(rate, source)`, where a date of None is a
    rate for any day. Anything else is FxUnavailableError, as the real port
    raises."""

    def __init__(self, rates: dict[tuple[str, str, str | None], tuple[Decimal, str]]) -> None:
        self.rates = dict(rates)
        self.asked: list[tuple[str, str, str]] = []

    async def rate(self, from_currency: str, to_currency: str, on_date: str) -> Any:
        from salli.application.ports import FxQuote, FxUnavailableError

        self.asked.append((from_currency, to_currency, on_date))
        if from_currency == to_currency:
            return FxQuote(rate=Decimal(1), source="identity", as_of=on_date)
        for key in ((from_currency, to_currency, on_date), (from_currency, to_currency, None)):
            if key in self.rates:
                rate, source = self.rates[key]
                return FxQuote(rate=rate, source=source, as_of=on_date)
        raise FxUnavailableError(f"No {from_currency}→{to_currency} rate for {on_date}")


class FakeLedger:
    """The ledger repository over accounts and entries held in memory, scoped
    to their owner as the SQL repository is: each query answers for one user."""

    def __init__(self) -> None:
        self.accounts: list[Any] = []
        self.entries: list[Any] = []

    async def get_accounts(self, user_id: str, include_inactive: bool = False) -> list[Any]:
        return sorted(
            (
                a
                for a in self.accounts
                if a.user_id == user_id and (include_inactive or a.is_active)
            ),
            key=lambda a: a.code,
        )

    async def get_account(self, user_id: str, account_id: str) -> Any:
        return next((a for a in self.accounts if a.id == account_id and a.user_id == user_id), None)

    async def get_entries(
        self, user_id: str, from_date: str | None = None, to_date: str | None = None
    ) -> list[Any]:
        return sorted(
            (
                e
                for e in self.entries
                if e.user_id == user_id
                and (from_date is None or e.entry_date >= from_date)
                and (to_date is None or e.entry_date <= to_date)
            ),
            key=lambda e: e.entry_date,
        )

    async def posting_totals(
        self, user_id: str, account_ids: Any, to_date: str | None = None
    ) -> list[tuple[str, str, Decimal, Decimal]]:
        """Per account and currency: the signed amount and its base value, as
        the database sums them (entries on or before `to_date`, if given)."""
        wanted = set(account_ids)
        sums: dict[tuple[str, str], list[Decimal]] = {}
        for e in await self.get_entries(user_id, to_date=to_date):
            for p in e.postings:
                if p.account_id in wanted:
                    signed = Decimal(p.direction.value) * p.amount
                    pair = sums.setdefault((p.account_id, p.currency), [Decimal(0), Decimal(0)])
                    pair[0] += signed
                    pair[1] += signed * p.fx_rate
        return [(a, c, amount, base) for (a, c), (amount, base) in sums.items()]

    async def balances_before(self, user_id: str, before: str) -> dict[str, Decimal]:
        balances: dict[str, Decimal] = {}
        for e in await self.get_entries(user_id):
            if e.entry_date < before:
                for p in e.postings:
                    balances[p.account_id] = balances.get(p.account_id, Decimal(0)) + p.base_signed
        return balances

    async def first_flow_date(self, user_id: str, to_date: str | None = None) -> str | None:
        """The date of the user's first entry touching an income or an expense
        account (on or before `to_date`, if given)."""
        kinds = {a.id for a in self.accounts if a.type in ("income", "expense")}
        for e in await self.get_entries(user_id, to_date=to_date):
            if any(p.account_id in kinds for p in e.postings):
                return e.entry_date
        return None


class FakeGoals:
    def __init__(self) -> None:
        self.goals: list[dict[str, Any]] = []
        self.allocations: list[dict[str, Any]] = []

    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        return [dict(g) for g in self.goals]

    async def list_allocations(
        self, user_id: str, goal_id: str | None = None
    ) -> list[dict[str, Any]]:
        return [dict(a) for a in self.allocations if goal_id in (None, a["goal_id"])]


class FakeScores:
    """Stored FI scores, oldest first, as `fi_scores` keeps them."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def save(self, user_id: str, score: dict[str, Any]) -> str:
        self.rows.append(dict(score))
        return str(len(self.rows))

    async def get_latest(self, user_id: str) -> dict[str, Any] | None:
        return dict(self.rows[-1]) if self.rows else None

    async def history(self, user_id: str) -> list[dict[str, Any]]:
        return [
            {"score": float(r["overall_score"]), "net_worth": r.get("net_worth"), "created_at": ""}
            for r in reversed(self.rows)
        ]


class FakeStrategies:
    def __init__(self, strategy: dict[str, Any] | None = None) -> None:
        self.strategy = strategy

    async def get_latest(self, user_id: str) -> dict[str, Any] | None:
        return self.strategy

    async def get_history(self, user_id: str) -> list[dict[str, Any]]:
        return [self.strategy] if self.strategy else []


class FakeFeeds:
    """Statements and bank connections: none, unless a test adds them."""

    def __init__(self) -> None:
        self.statements: list[dict[str, Any]] = []
        self.connections: list[dict[str, Any]] = []
        self.pending: list[Any] = []

    async def list_statements(self, user_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        return list(self.statements)

    async def get_all_pending(self, user_id: str) -> list[Any]:
        return list(self.pending)

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        return list(self.connections)


class FakeUoW:
    """A unit of work over one in-memory ledger and what a user declares
    beside it: enough for FI, insights, the forecast, debts and the baseline."""

    def __init__(self, base_currency: str = "EUR") -> None:
        self.user_profiles = FakeProfiles(base_currency)
        self.ledger = FakeLedger()
        self.goals = FakeGoals()
        self.fi_scores = FakeScores()
        self.fire_strategies = FakeStrategies()
        self.debts = FakeRecords(is_active=True, account_id=None)
        self.recurring_subscriptions = FakeRecords(is_active=True)
        self.statements = FakeFeeds()
        self.bank_connections = self.statements

    async def __aenter__(self) -> FakeUoW:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    def factory(self) -> Any:
        """A uow_factory handing out this unit of work."""
        return lambda: self
