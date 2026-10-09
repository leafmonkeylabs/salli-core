"""
Port interfaces — abstract contracts the domain depends on.
Adapters (in salli/adapters/) implement these; the domain never imports adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from salli.domain.usage import AIAction


class LedgerRepository(ABC):
    @abstractmethod
    async def save_entry(self, user_id: str, entry: Any) -> str:
        """Persist a JournalEntry and return its generated ID."""
        ...

    @abstractmethod
    async def get_entries(
        self,
        user_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[Any]:
        """Return StoredJournalEntry list, optionally filtered by date range."""
        ...

    @abstractmethod
    async def get_entry_by_id(self, user_id: str, entry_id: str) -> Any | None:
        """Return a single StoredJournalEntry by ID, or None."""
        ...

    @abstractmethod
    async def set_reversed_by(self, entry_id: str, reversing_id: str) -> None:
        """Mark an entry as reversed by another entry."""
        ...

    @abstractmethod
    async def get_accounts(self, user_id: str, include_inactive: bool = False) -> list[Any]:
        """Return Account list for the user."""
        ...

    @abstractmethod
    async def get_account(self, user_id: str, account_id: str) -> Any | None:
        """Return a single Account by ID (active or inactive), or None."""
        ...

    @abstractmethod
    async def save_account(self, user_id: str, account: Any) -> str:
        """Persist an Account and return its ID."""
        ...

    @abstractmethod
    async def update_account(
        self,
        user_id: str,
        account_id: str,
        *,
        code: str,
        name: str,
        type: str,
        currency: str,
        tax_role: str | None = None,
    ) -> None:
        """Update mutable fields of an existing account."""
        ...

    @abstractmethod
    async def deactivate_account(self, user_id: str, account_id: str) -> None:
        """Soft-delete an account by setting is_active=False."""
        ...

    @abstractmethod
    async def ensure_system_tags(self, user_id: str, tags: list[tuple[str, str, str]]) -> None:
        """Create the closed `need` tag axis for a user. Idempotent."""
        ...

    @abstractmethod
    async def list_tags(self, user_id: str, kind: str | None = None) -> list[Any]:
        """This user's tags, optionally filtered to one axis."""
        ...

    @abstractmethod
    async def set_posting_tags(self, user_id: str, posting_id: str, tags: dict[str, str]) -> None:
        """Replace a posting's tags. Tags are mutable; the posting is not."""
        ...

    @abstractmethod
    async def reactivate_account(self, user_id: str, account_id: str) -> None:
        """Reverse a soft-delete by setting is_active=True."""
        ...


class TaxComputationRepository(ABC):
    @abstractmethod
    async def save(self, user_id: str, computation: Any) -> str: ...

    @abstractmethod
    async def get_latest(self, user_id: str, year: str) -> Any | None: ...

    @abstractmethod
    async def list_computation_keys(self) -> list[tuple[str, str]]:
        """Every (user_id, year) that has at least one stored computation.

        Admin-only. Used to re-run stored computations after an engine fix, so
        users are not left looking at a number the engine no longer agrees with.
        """
        ...


class ReminderRepository(ABC):
    @abstractmethod
    async def list_reminders(self, user_id: str, status: str | None = None) -> list[Any]: ...

    @abstractmethod
    async def create_reminder(
        self, user_id: str, reminder_id: str, kind: str, due_date: str
    ) -> None: ...

    @abstractmethod
    async def mark_done(self, user_id: str, reminder_id: str) -> None: ...

    @abstractmethod
    async def delete_reminder(self, user_id: str, reminder_id: str) -> None: ...

    @abstractmethod
    async def upsert_alert(
        self,
        user_id: str,
        alert_type: str,
        source_domain: str,
        source_id: str,
        kind: str,
        due_date: str,
        severity: str,
    ) -> str:
        """Create or refresh a system-detected alert, keyed on
        (user_id, source_domain, source_id, alert_type) — re-running a sync
        against the same still-active condition updates the existing row
        (kind/due_date/severity, and resets status to "pending" if it had been
        dismissed) rather than creating a duplicate."""
        ...


class StatementRepository(ABC):
    """Imported statements and their parsed transactions. A parsed transaction
    read back carries its statement's `account_id` ("" when it has none)."""

    @abstractmethod
    async def save_statement(
        self,
        user_id: str,
        statement_id: str,
        bank: str,
        period_start: str,
        period_end: str,
        transactions: list[Any],
        storage_key: str = "",
        account_id: str | None = None,
    ) -> None:
        """Store the statement and its transactions, and fill in each
        transaction's new `id` and `statement_id`."""
        ...

    @abstractmethod
    async def imported_between(self, user_id: str, from_date: str, to_date: str) -> list[Any]:
        """The user's parsed transactions dated `from_date`..`to_date`, what a
        new import is checked against for duplicates. Not the discarded ones,
        which never happened, nor those already found to duplicate another:
        that one stands for both."""
        ...

    @abstractmethod
    async def get_all_pending(self, user_id: str) -> list[Any]:
        """Transactions waiting for review: neither posted nor discarded."""
        ...

    @abstractmethod
    async def get_pending(self, user_id: str, statement_id: str) -> list[Any]:
        """One statement's transactions waiting for review."""
        ...

    @abstractmethod
    async def discard(self, user_id: str, statement_id: str, ids: list[str] | None = None) -> int:
        """Mark a statement's pending transactions (those of `ids`, or all of
        them) discarded: never posted, out of review, and no duplicate of
        anything imported later. Returns how many."""
        ...

    @abstractmethod
    async def get_by_ids(self, user_id: str, ids: list[str]) -> list[Any]: ...

    @abstractmethod
    async def list_statements(self, user_id: str, limit: int = 50) -> list[Any]:
        """Every statement this user has uploaded, newest first.

        The rows were always persisted; nothing exposed them, so the mobile app
        told users a statement history "isn't tracked by the server yet".
        """
        ...

    @abstractmethod
    async def mark_posted(self, transaction_id: str, entry_id: str) -> None: ...

    @abstractmethod
    async def get_statement(self, user_id: str, statement_id: str) -> dict[str, Any] | None:
        """Return a single statement's metadata (bank, period, storage key), or None."""
        ...


class LLMPort(ABC):
    """
    Single gateway to the LLM — tiering, retries, and usage metering live here.
    The domain never calls Anthropic directly.
    """

    @abstractmethod
    async def extract_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        model_tier: str = "fast",
    ) -> dict[str, Any]:
        """Run structured extraction; returns validated JSON matching schema."""
        ...

    @abstractmethod
    async def stream_agent(
        self,
        thread_id: str,
        user_message: str,
    ):
        """Stream agent tokens; yields (event_type, payload) tuples."""
        ...


class StoragePort(ABC):
    @abstractmethod
    async def upload(self, user_id: str, key: str, data: bytes) -> str:
        """Upload and return the storage URL."""
        ...

    @abstractmethod
    async def download(self, key: str) -> bytes: ...


@dataclass(frozen=True)
class FxQuote:
    """An exchange rate and where it came from.

    `rate` is units of the target currency per one unit of the source currency.
    `as_of` is the date the rate is actually for, which can be earlier than the
    one asked about: a central bank publishes nothing on a Sunday, so Sunday's
    rate is Friday's. `source` is recorded on every posting converted with it.
    """

    rate: Decimal
    source: str
    as_of: str


class FxUnavailableError(LookupError):
    """No source could give this rate. Never answered with a made-up number."""


class FxRatePort(ABC):
    @abstractmethod
    async def rate(self, from_currency: str, to_currency: str, on_date: str) -> FxQuote:
        """How many `to_currency` one `from_currency` bought on `on_date` (YYYY-MM-DD).

        Raises FxUnavailableError when there is no such rate.
        """
        ...


class KnowledgeBasePort(ABC):
    @abstractmethod
    async def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        """Retrieve relevant chunks from the tax knowledge base with citations."""
        ...


class AgentSessionRepository(ABC):
    @abstractmethod
    async def upsert(self, user_id: str, thread_id: str, persona: str = "scrooge") -> None:
        """Create or touch (update last_active_at) a session. `persona` is only
        used on creation — an existing session keeps its original persona."""
        ...

    @abstractmethod
    async def set_title(self, user_id: str, thread_id: str, title: str) -> None:
        """Set the generated title for a session."""
        ...

    @abstractmethod
    async def list(
        self, user_id: str, limit: int = 50, persona: str = "scrooge"
    ) -> list[dict[str, Any]]:
        """Return this persona's sessions sorted by last_active_at desc."""
        ...

    @abstractmethod
    async def get(self, user_id: str, thread_id: str) -> dict[str, Any] | None:
        """Return a single session or None."""
        ...

    @abstractmethod
    async def delete(self, user_id: str, thread_id: str) -> None:
        """Hard-delete a session record."""
        ...


class AgentDocumentRepository(ABC):
    @abstractmethod
    async def save(self, user_id: str, doc: dict[str, Any]) -> str:
        """Persist an agent document and return its ID."""
        ...

    @abstractmethod
    async def get(self, user_id: str, doc_id: str) -> dict[str, Any] | None:
        """Return a document by ID, or None if not found/not owned by user."""
        ...

    @abstractmethod
    async def update(self, user_id: str, doc_id: str, updates: dict[str, Any]) -> None:
        """Update mutable fields of an existing document."""
        ...

    @abstractmethod
    async def list(
        self,
        user_id: str,
        tags: list[str] | None = None,
        namespace: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return documents for the user, optionally filtered."""
        ...

    @abstractmethod
    async def delete(self, user_id: str, doc_id: str) -> None:
        """Hard-delete a document."""
        ...

    @abstractmethod
    async def get_by_slug(self, user_id: str, namespace: str, slug: str) -> dict[str, Any] | None:
        """Return a document by its user+namespace+slug key."""
        ...

    @abstractmethod
    async def upsert_by_slug(
        self, user_id: str, namespace: str, slug: str, doc: dict[str, Any]
    ) -> str:
        """Insert or update a document keyed by user+namespace+slug. Returns ID."""
        ...


# ── User profile ─────────────────────────────────────────────────────────────


class UserProfileRepository(ABC):
    @abstractmethod
    async def get(self, user_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def upsert(self, user_id: str, fields: dict[str, Any]) -> None: ...

    @abstractmethod
    async def set_flag(self, user_id: str, field: str, value: bool) -> None:
        """Set a boolean flag, including to False (which `upsert` cannot do)."""
        ...

    @abstractmethod
    async def set_preference(self, user_id: str, field: str, value: str | None) -> None:
        """Set a nullable string preference, including back to None.

        The string sibling of `set_flag`, and needed for the same reason:
        `upsert` skips None, so it can set a preference but never clear one.
        """
        ...

    @abstractmethod
    async def list_daily_briefing_optins(self) -> list[dict[str, Any]]:
        """Users who opted in to the scheduled daily advisor run."""
        ...

    async def base_currency(self, user_id: str) -> str:
        """The ISO code the user's amounts are kept in. `LookupError` if no profile."""
        profile = await self.get(user_id)
        if not profile or not profile.get("base_currency"):
            raise LookupError(f"User {user_id} has no profile")
        return str(profile["base_currency"])

    async def has_financial_data(self, user_id: str) -> bool:
        """Whether anything is stored in the user's base currency yet."""
        raise NotImplementedError


class LlmCredentialRepository(ABC):
    """Per-user provider API keys (BYOK), stored encrypted.

    Deliberately dumb: it moves ciphertext in and out and never encrypts,
    decrypts, or validates. All crypto lives in LlmCredentialService so there
    is exactly one place a plaintext key can exist.
    """

    @abstractmethod
    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        """All stored credentials for a user, ciphertext included."""
        ...

    @abstractmethod
    async def get(self, user_id: str, provider: str) -> dict[str, Any] | None:
        """One credential, or None."""
        ...

    @abstractmethod
    async def upsert(
        self,
        user_id: str,
        provider: str,
        *,
        ciphertext: str,
        last4: str,
        validated_at: Any,
        key_version: int,
    ) -> None:
        """Create or replace this user's credential for the provider.

        `key_version` records which encryption key sealed the ciphertext, so a
        rotated-away key is a loud failure rather than a silent wrong-key
        decrypt attempt.
        """
        ...

    @abstractmethod
    async def delete(self, user_id: str, provider: str) -> bool:
        """Remove it. Returns False when there was nothing to remove."""
        ...


# ── Financial Independence ───────────────────────────────────────────────────


class GoalRepository(ABC):
    """Goals and their claims on real accounts.

    Allocation methods live here rather than on their own repository because a
    claim has no meaning apart from the goal that makes it, and both are written
    inside the same unit of work.
    """

    @abstractmethod
    async def save(self, user_id: str, goal: dict[str, Any]) -> str: ...

    @abstractmethod
    async def get(self, user_id: str, goal_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def update(self, user_id: str, goal_id: str, updates: dict[str, Any]) -> None: ...

    @abstractmethod
    async def delete(self, user_id: str, goal_id: str) -> None: ...

    @abstractmethod
    async def list_allocations(self, user_id: str, goal_id: str | None = None) -> list[Any]:
        """Every claim this user's goals make on their accounts."""
        ...

    @abstractmethod
    async def set_allocation(
        self, user_id: str, goal_id: str, account_id: str, allocated_minor: int
    ) -> None:
        """Create, update, or (with zero) clear one goal's claim on one account."""
        ...


class FiScoreRepository(ABC):
    @abstractmethod
    async def save(self, user_id: str, score: dict[str, Any]) -> str: ...

    @abstractmethod
    async def get_latest(self, user_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def history(self, user_id: str, limit: int = 90) -> list[dict[str, Any]]: ...


class AdvisoryRepository(ABC):
    @abstractmethod
    async def save(self, user_id: str, report: dict[str, Any]) -> str: ...

    @abstractmethod
    async def get(self, user_id: str, report_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def get_latest(self, user_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list(self, user_id: str, limit: int = 30) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def update_recommendations(
        self, user_id: str, report_id: str, recommendations: list[Any]
    ) -> None: ...

    @abstractmethod
    async def ran_today(self, user_id: str, day: str) -> bool: ...


class FireStrategyRepository(ABC):
    @abstractmethod
    async def get_latest(self, user_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def save(self, user_id: str, strategy: dict[str, Any]) -> int:
        """Persist a new strategy version and return the version number."""
        ...

    @abstractmethod
    async def get_history(self, user_id: str) -> list[dict[str, Any]]: ...


# ── Budget ────────────────────────────────────────────────────────────────────


class BudgetRepository(ABC):
    @abstractmethod
    async def save(self, user_id: str, budget: dict[str, Any]) -> str: ...

    @abstractmethod
    async def get(self, user_id: str, budget_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list(self, user_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def update(self, user_id: str, budget_id: str, updates: dict[str, Any]) -> None: ...

    @abstractmethod
    async def delete(self, user_id: str, budget_id: str) -> None: ...


# ── Debt ──────────────────────────────────────────────────────────────────────


class DebtRepository(ABC):
    @abstractmethod
    async def save(self, user_id: str, debt: dict[str, Any]) -> str: ...

    @abstractmethod
    async def get(self, user_id: str, debt_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def update(self, user_id: str, debt_id: str, updates: dict[str, Any]) -> None: ...

    @abstractmethod
    async def delete(self, user_id: str, debt_id: str) -> None: ...


# ── Portfolio ─────────────────────────────────────────────────────────────────


class PortfolioRepository(ABC):
    @abstractmethod
    async def save(self, user_id: str, holding: dict[str, Any]) -> str: ...

    @abstractmethod
    async def get(self, user_id: str, holding_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def update(self, user_id: str, holding_id: str, updates: dict[str, Any]) -> None: ...

    @abstractmethod
    async def delete(self, user_id: str, holding_id: str) -> None: ...


# ── Recurring subscription ────────────────────────────────────────────────────


class RecurringSubscriptionRepository(ABC):
    @abstractmethod
    async def save(self, user_id: str, subscription: dict[str, Any]) -> str: ...

    @abstractmethod
    async def get(self, user_id: str, subscription_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def update(self, user_id: str, subscription_id: str, updates: dict[str, Any]) -> None: ...

    @abstractmethod
    async def delete(self, user_id: str, subscription_id: str) -> None: ...


# ── Insurance ──────────────────────────────────────────────────────────────────


class PolicyRepository(ABC):
    @abstractmethod
    async def save(self, user_id: str, policy: dict[str, Any]) -> str: ...

    @abstractmethod
    async def get(self, user_id: str, policy_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def update(self, user_id: str, policy_id: str, updates: dict[str, Any]) -> None: ...

    @abstractmethod
    async def delete(self, user_id: str, policy_id: str) -> None: ...


class InsuranceTargetRepository(ABC):
    @abstractmethod
    async def upsert(self, user_id: str, policy_type: str, target_amount_minor: int) -> str: ...

    @abstractmethod
    async def list(self, user_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def delete(self, user_id: str, policy_type: str) -> None: ...


# ── Audit log ──────────────────────────────────────────────────────────────────


class AuditLogRepository(ABC):
    @abstractmethod
    async def log(
        self, user_id: str, action: str, params: dict[str, Any], decision: str
    ) -> str: ...

    @abstractmethod
    async def list(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]: ...


# ── Data portability ───────────────────────────────────────────────────────────


class DataPortabilityRepository(ABC):
    @abstractmethod
    async def delete_all(self, user_id: str) -> dict[str, int]:
        """Permanently delete every row belonging to this user across every
        user-scoped table. Returns {table_name: rows_deleted}. Irreversible."""
        ...


# ── MCP OAuth ────────────────────────────────────────────────────────────────


class OAuthClientRepository(ABC):
    @abstractmethod
    async def register(self, client_name: str | None, redirect_uris: list[str]) -> dict[str, Any]:
        """Dynamic Client Registration (RFC 7591). Returns the new client's record."""
        ...

    @abstractmethod
    async def get(self, client_id: str) -> dict[str, Any] | None: ...


class OAuthTokenRepository(ABC):
    @abstractmethod
    async def save_authorization_code(
        self,
        code: str,
        client_id: str,
        user_id: str,
        redirect_uri: str,
        code_challenge: str,
        scope: str,
        resource: str | None,
        expires_at: datetime,
    ) -> None: ...

    @abstractmethod
    async def get_authorization_code(self, code: str) -> dict[str, Any] | None:
        """Look up without consuming. None if missing/expired. Callers must
        call delete_authorization_code() only after validation succeeds, so a
        failed PKCE/client check doesn't burn a code a legitimate retry needs."""
        ...

    @abstractmethod
    async def delete_authorization_code(self, code: str) -> None:
        """Marks a code used — call only once the exchange has succeeded."""
        ...

    @abstractmethod
    async def save_access_token(
        self,
        token_hash: str,
        client_id: str,
        user_id: str,
        scope: str,
        resource: str | None,
        expires_at: datetime,
    ) -> str:
        """Returns the new access token row's id (FK target for its refresh token)."""
        ...

    @abstractmethod
    async def save_refresh_token(
        self,
        token_hash: str,
        access_token_id: str,
        client_id: str,
        user_id: str,
        scope: str,
        resource: str | None,
        expires_at: datetime,
    ) -> None: ...

    @abstractmethod
    async def get_access_token(self, token_hash: str) -> dict[str, Any] | None:
        """None if missing, expired, or revoked."""
        ...

    @abstractmethod
    async def get_refresh_token(self, token_hash: str) -> dict[str, Any] | None:
        """None if missing, expired, or revoked."""
        ...

    @abstractmethod
    async def revoke_access_token(self, token_id: str, user_id: str) -> bool:
        """Revokes only if the token belongs to user_id. Returns whether it revoked anything."""
        ...

    @abstractmethod
    async def revoke_refresh_token(self, token_hash: str) -> None: ...

    @abstractmethod
    async def list_active_connections(
        self, user_id: str, resource: str | None = None
    ) -> list[dict[str, Any]]:
        """Active (non-revoked, non-expired) client connections for a user,
        one row per access token, joined with the client's display name. With
        `resource`, only tokens issued for it."""
        ...

    # Device authorization (RFC 8628). Not abstract: only a server that offers
    # device sign-in needs them.

    async def save_device_code(
        self,
        device_code_hash: str,
        user_code: str,
        client_id: str,
        scope: str,
        resource: str | None,
        interval_seconds: int,
        expires_at: datetime,
    ) -> None:
        raise NotImplementedError

    async def get_device_code(self, device_code_hash: str) -> dict[str, Any] | None:
        """The authorization a device is polling for, in any state."""
        raise NotImplementedError

    async def get_device_code_by_user_code(self, user_code: str) -> dict[str, Any] | None:
        """A pending, unexpired authorization, by the code the person typed."""
        raise NotImplementedError

    async def update_device_code(self, device_id: str, **fields: Any) -> None:
        """Set status / user_id / last_polled_at."""
        raise NotImplementedError


# ── Bank connections ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RemoteAccount:
    """An account at a bank, as a connection provider reports it."""

    remote_id: str
    name: str
    institution: str
    currency: str
    balance: Decimal
    balance_date: datetime | None


@dataclass(frozen=True)
class RemoteTransaction:
    remote_id: str
    account_remote_id: str
    posted: str  # YYYY-MM-DD
    #: Signed: positive is money into the account, as banks report it.
    amount: Decimal
    description: str


@dataclass(frozen=True)
class BankSnapshot:
    accounts: list[RemoteAccount]
    transactions: list[RemoteTransaction]
    #: Messages the provider asks to show the user (a connection needing
    #: re-authentication, an account it could not reach). Already sanitized.
    warnings: list[str]


class BankLinkError(Exception):
    """The provider refused: a used or unknown setup token, revoked access."""


class BankConnector(ABC):
    """A provider that reads accounts and transactions from people's banks."""

    provider: str

    @abstractmethod
    async def link(self, setup: str) -> str:
        """Exchange what the user pasted (a setup token, a code) for the
        credential to keep. Raises BankLinkError."""
        ...

    @abstractmethod
    async def fetch(
        self, credential: str, start: datetime | None, balances_only: bool = False
    ) -> BankSnapshot:
        """Accounts, and transactions posted since `start`. Raises BankLinkError
        when the credential no longer works."""
        ...


class BankConnectionRepository(ABC):
    @abstractmethod
    async def create(self, user_id: str, connection: dict[str, Any]) -> str: ...

    @abstractmethod
    async def list(self, user_id: str) -> list[dict[str, Any]]:
        """Connections with their accounts, never the credential."""
        ...

    @abstractmethod
    async def get_secret(self, user_id: str, connection_id: str) -> dict[str, Any] | None:
        """The sealed credential and its key version, for a sync."""
        ...

    @abstractmethod
    async def upsert_accounts(
        self, user_id: str, connection_id: str, accounts: list[RemoteAccount]
    ) -> None: ...

    @abstractmethod
    async def map_account(
        self, user_id: str, connection_id: str, remote_id: str, account_id: str | None
    ) -> bool: ...

    @abstractmethod
    async def update(self, user_id: str, connection_id: str, fields: dict[str, Any]) -> None: ...

    @abstractmethod
    async def delete(self, user_id: str, connection_id: str) -> bool: ...

    @abstractmethod
    async def list_due(self, synced_before: datetime) -> list[tuple[str, str]]:
        """(user id, connection id) of every connection, anyone's, never
        synced or last synced before `synced_before`. For the scheduler."""
        ...


class RuleRepository(ABC):
    """A user's categorisation rules, as plain dicts (see domain/rules)."""

    @abstractmethod
    async def list(self, user_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get(self, user_id: str, rule_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def save(self, user_id: str, rule: dict[str, Any]) -> str: ...

    @abstractmethod
    async def update(self, user_id: str, rule_id: str, fields: dict[str, Any]) -> bool: ...

    @abstractmethod
    async def delete(self, user_id: str, rule_id: str) -> bool: ...

    @abstractmethod
    async def record_hits(self, user_id: str, counts: dict[str, int], at: datetime) -> None:
        """Add to each rule's hit count, and stamp when it last decided something."""
        ...


class PersonalAccessTokenRepository(ABC):
    """Long-lived tokens for scripts and CI, stored hashed."""

    @abstractmethod
    async def create(
        self,
        user_id: str,
        name: str,
        token_hash: str,
        prefix: str,
        expires_at: datetime | None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def list(self, user_id: str) -> list[dict[str, Any]]:
        """The user's tokens that are not revoked, newest first (never the hash)."""
        ...

    @abstractmethod
    async def get_active(self, token_hash: str) -> dict[str, Any] | None:
        """The token if it exists, is not revoked and has not expired."""
        ...

    @abstractmethod
    async def revoke(self, user_id: str, token_id: str) -> bool: ...

    @abstractmethod
    async def touch(self, token_id: str, at: datetime) -> None:
        """Record use, for "last used" in the list."""
        ...


# ── Extension seams ──────────────────────────────────────────────────────────
#
# The two places a deployment may change what users can do or see. Salli ships
# permissive defaults for both (application/defaults.py); an extension can
# replace them (salli/extensions.py). Nothing else in the codebase branches on
# who a user is or what they pay.


class UsageMeter(ABC):
    """A pre-flight gate in front of every AI action.

    Called before the model runs, so the user is refused before any inference
    is spent rather than after. Return to allow the action; raise
    `salli.domain.usage.UsageLimitReached` to refuse it.
    """

    @abstractmethod
    async def charge(
        self,
        user_id: str,
        action: AIAction,
        *,
        model_id: str | None = None,
        email: str | None = None,
    ) -> None: ...


class Surface(StrEnum):
    """A response whose depth an `EntitlementPolicy` may shape."""

    FI_PROJECTIONS = "fi.projections"
    FIRE_STRATEGY = "fi.strategy"
    ADVISOR_REPORT = "advisor.report"


class PayloadView(Protocol):
    """One user's view of the shapeable surfaces. Synchronous: everything it
    needs was resolved when `EntitlementPolicy.for_user` returned it."""

    def shape(self, surface: Surface, payload: dict[str, Any]) -> dict[str, Any]:
        """Return the payload as this user may see it. Must not mutate `payload`."""
        ...


class EntitlementPolicy(ABC):
    """What of a computed result a user may see.

    Services always compute the full, truthful payload; the interface layer
    asks the policy how much of it to return. Resolved once per request, so a
    list endpoint or a streamed response pays for one lookup, not one per item.
    """

    @abstractmethod
    async def for_user(self, user_id: str, email: str | None = None) -> PayloadView: ...
