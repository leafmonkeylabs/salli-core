"""
Port interfaces — abstract contracts the domain depends on.
Adapters (in salli/adapters/) implement these; the domain never imports adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol, TypedDict

from pydantic import BaseModel

from salli.domain.llm import Tier

# The message a `Notifier` delivers, built by core (domain/notifications).
from salli.domain.notifications.digest import Notification as Notification
from salli.domain.notifications.digest import NotificationItem as NotificationItem
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

    async def verify_chain(self, user_id: str) -> dict[str, Any]:
        """The user's hash chain checked from its first entry
        (`domain.accounting.chain.verify`)."""
        raise NotImplementedError

    async def chain_head(self, user_id: str) -> str | None:
        """The hash of the user's last stored entry; None with none."""
        raise NotImplementedError

    async def set_retained_earnings(self, user_id: str, account_id: str) -> None:
        """Make this (equity) account the user's one `retained_earnings`
        account, taking the role from any other."""
        raise NotImplementedError

    async def posting_totals(
        self, user_id: str, account_ids: Collection[str], to_date: str | None = None
    ) -> list[tuple[str, str, Decimal, Decimal]]:
        """For each of these accounts and each currency posted to it: (account
        id, currency, the signed total in that currency, the signed total in
        the base currency), summed by the store over every entry (dated on or
        before `to_date`, when given)."""
        raise NotImplementedError

    async def search_entries(
        self,
        user_id: str,
        *,
        text: str | None = None,
        account_id: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        min_base_minor: int | None = None,
        max_base_minor: int | None = None,
        after: tuple[str, str] | None = None,
        limit: int = 50,
    ) -> tuple[list[Any], int, list[tuple[str, str, Decimal]]]:
        """The entries whose description contains `text` (any case), dated in
        the range, with a posting (on `account_id`, when given) whose
        base-currency amount, in its minor units, is within the bounds:
        newest first, at most `limit` after the (entry date, id) `after`.
        With them, how many match in all, and over every match the net
        (debits less credits) of the postings counted (on `account_id`, when
        given) as (account type, currency, amount), summed by the store."""
        raise NotImplementedError

    async def posting_entry_date(self, user_id: str, posting_id: str) -> str | None:
        """The date of the user's entry this posting belongs to, or None."""
        raise NotImplementedError

    async def manual_entry_by_ref(self, user_id: str, external_ref: str) -> Any | None:
        """The user's manual entry with this `external_ref`, or None."""
        raise NotImplementedError

    async def first_flow_date(self, user_id: str, to_date: str | None = None) -> str | None:
        """The date of the user's first entry with a posting to an income or
        an expense account (on or before `to_date`, when given), or None:
        when their record of money in and out begins. A reversed entry and
        its reversal are left out: together they are nothing."""
        raise NotImplementedError

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
        asset_role: str | None = None,
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


class TaxReturnRepository(ABC):
    """A user's tax returns, each version a row, and the payments made
    against them, as plain dicts. Rows are only added."""

    @abstractmethod
    async def add(self, user_id: str, record: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def get(self, user_id: str, return_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list(self, user_id: str, year: str | None = None) -> list[dict[str, Any]]:
        """Newest year first, each year's versions newest first."""
        ...

    @abstractmethod
    async def latest_of_each(self, user_id: str) -> list[dict[str, Any]]:
        """The latest version of each jurisdiction and year's return."""
        ...

    @abstractmethod
    async def add_payment(self, user_id: str, record: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def payments(self, user_id: str) -> list[dict[str, Any]]: ...


class TaxComputationRepository(ABC):
    """A user's stored tax computations, as plain dicts. Rows are only added;
    each read comes back with the rule set version's `rule_set_id` and
    `version` number joined in."""

    @abstractmethod
    async def save(self, user_id: str, record: dict[str, Any]) -> dict[str, Any]:
        """Store a computation: country, region, year, rule_set_version_id (one
        of the user's own), content_hash, currency, net_minor,
        tax_payable_minor, refund_due_minor, lines, inputs, warnings."""
        ...

    @abstractmethod
    async def get(self, user_id: str, computation_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def get_latest(
        self, user_id: str, country: str, region: str | None, year: str
    ) -> dict[str, Any] | None:
        """The newest computation for this jurisdiction and year."""
        ...

    @abstractmethod
    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        """Every computation of the user's, newest first (their data export)."""
        ...

    @abstractmethod
    async def latest_of_each(self) -> list[dict[str, Any]]:
        """Every user's newest computation for each jurisdiction and year.

        Operator-only: recomputing stored results (`salli-server jobs
        recompute-tax`), so nobody is left looking at a figure their ledger
        and active rules no longer give."""
        ...


class RuleSetExists(ValueError):
    """The user already has a tax rule set for this jurisdiction and year."""

    def __init__(self, rule_set_id: str) -> None:
        super().__init__(
            f"A tax rule set for this jurisdiction and year already exists: {rule_set_id}"
        )
        self.rule_set_id = rule_set_id


class CmaPackRepository(ABC):
    """A user's capital-market assumptions packs (`domain/fi/cma.py`). A
    pack's document never changes once added; one at most is active."""

    @abstractmethod
    async def add(
        self, user_id: str, *, name: str, version: str, content: Any, content_hash: str
    ) -> dict[str, Any]:
        """Store a pack (inactive) and return it; the stored one when the
        user already has a pack with this content hash."""

    @abstractmethod
    async def list(self, user_id: str) -> list[dict[str, Any]]:
        """The user's packs, newest first, without their documents."""

    @abstractmethod
    async def get(self, user_id: str, pack_id: str) -> dict[str, Any] | None:
        """One of the user's packs with its document; None if not theirs."""

    @abstractmethod
    async def activate(self, user_id: str, pack_id: str | None) -> None:
        """Make `pack_id` the user's active pack (None: none is)."""

    @abstractmethod
    async def active(self, user_id: str) -> dict[str, Any] | None:
        """The user's active pack with its document, or None."""


class TaxRuleSetRepository(ABC):
    """A user's tax rule sets and their versions, as plain dicts.

    Every method takes the owner's id and touches nothing of anyone else's: a
    set or version of another user's is indistinguishable from one that does
    not exist. A version's `content` and `content_hash` are written once, by
    `add_version`, and there is no way here to change them (core_0010's
    trigger refuses it too): an edit is a new version.
    """

    @abstractmethod
    async def list_sets(self, user_id: str) -> list[dict[str, Any]]:
        """The user's rule sets, each with `versions`: a summary of every
        version (no content), oldest first."""
        ...

    @abstractmethod
    async def get_set(
        self, user_id: str, rule_set_id: str, *, lock: bool = False
    ) -> dict[str, Any] | None:
        """One set with its version summaries. `lock` holds the set's row until
        the unit of work ends (SELECT … FOR UPDATE), so versions can be
        numbered and activated one at a time."""
        ...

    @abstractmethod
    async def find_set(
        self, user_id: str, country: str, region: str | None, year_label: str, *, lock: bool = False
    ) -> dict[str, Any] | None: ...

    @abstractmethod
    async def create_set(
        self, user_id: str, country: str, region: str | None, year_label: str, name: str
    ) -> dict[str, Any]:
        """RuleSetExists when the user has one for this jurisdiction and year."""
        ...

    @abstractmethod
    async def get_version(self, user_id: str, version_id: str) -> dict[str, Any] | None:
        """One version, with its content and validation report."""
        ...

    @abstractmethod
    async def add_version(
        self, user_id: str, rule_set_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """A new version of the set, numbered one past its latest. The caller
        holds the set's lock (`get_set(…, lock=True)`). `fields`: content,
        content_hash, status, validation, author_kind, author_name,
        change_note."""
        ...

    @abstractmethod
    async def update_version(self, user_id: str, version_id: str, fields: dict[str, Any]) -> bool:
        """Change a version's lifecycle fields (status, validation, proposed_at,
        activated_at, superseded_at); ValueError for any other field."""
        ...

    @abstractmethod
    async def set_active(self, user_id: str, rule_set_id: str, version_id: str | None) -> None: ...

    @abstractmethod
    async def declared_roles(self, user_id: str) -> set[str]:
        """Every role key the user's rule sets declare now: in a version whose
        document matches the schema and that hasn't been superseded (an
        active version, or one still being worked on). A superseded version is
        history, so a role only it declared is declared no longer."""
        ...

    @abstractmethod
    async def declared_role_kinds(self, user_id: str) -> dict[str, set[str]]:
        """The roles `declared_roles` gives, each with the kinds (income,
        deduction, withholding, other) the versions declaring it give it."""
        ...

    @abstractmethod
    async def active_versions(self, user_id: str) -> list[dict[str, Any]]:
        """Every rule set of the user's that has an active version: the set's
        fields with `version`, that version in full (content included)."""
        ...

    @abstractmethod
    async def export(self, user_id: str) -> list[dict[str, Any]]:
        """Every set with every version in full, for the user's data export."""
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

    @abstractmethod
    async def sync_source(
        self,
        user_id: str,
        source_domain: str,
        source_prefix: str,
        items: list[tuple[str, str, str]],
    ) -> dict[str, list[str]]:
        """Make the user's reminders from one source exactly `items`, each
        (source_id, kind, due_date), every source_id starting with
        `source_prefix`: add the new ones, update the changed ones (back to
        pending when the date moves; a done reminder whose date stands stays
        done), and delete those under the prefix that are no longer listed.
        Returns the ids `created`, `updated` and `removed`."""
        ...


class PrincipleRepository(ABC):
    """A user's principles (domain/decisions/principles.py): preferences,
    so they are edited and archived, never deleted. Every read and write
    names the owner. A row is a dict: id, label, check, account, note,
    version, author_kind, author_name, created_at, updated_at, archived_at."""

    @abstractmethod
    async def list(self, user_id: str, include_archived: bool = False) -> list[dict[str, Any]]:
        """Oldest first."""
        ...

    @abstractmethod
    async def get(self, user_id: str, principle_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def add(self, user_id: str, record: dict[str, Any]) -> dict[str, Any]:
        """`record`: label, check, account, note, author_kind, author_name."""
        ...

    @abstractmethod
    async def update(
        self, user_id: str, principle_id: str, changes: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Change label, check, account or note (those `changes` names), and
        count the version up. None when it isn't the user's, or archived."""
        ...

    @abstractmethod
    async def archive(self, user_id: str, principle_id: str) -> dict[str, Any] | None:
        """Stop using it: it stays, archived. None when it isn't the user's."""
        ...


class DecisionRepository(ABC):
    """The decision journal (domain/decisions/journal.py): append-only.
    There is no way here to change or delete an entry, a note or a review;
    the database refuses it too (core_0017). Every read names the owner.

    An entry row: id, question, chosen, currency, as_of, review_on,
    recorded_at, content, hash; `get` and `list_full` add `notes` and
    `reviews` (each id, content, hash, created_at, oldest first), `list` and
    `due` add `notes` and `reviews` as counts and `last_reviewed_at`."""

    @abstractmethod
    async def record(self, user_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        """`entry`: id, question, chosen, currency, as_of, review_on,
        recorded_at, content, hash."""
        ...

    @abstractmethod
    async def get(self, user_id: str, decision_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def list(self, user_id: str) -> list[dict[str, Any]]:
        """Newest first, without their documents."""
        ...

    @abstractmethod
    async def list_full(self, user_id: str) -> list[dict[str, Any]]:
        """Every entry with its notes and reviews, oldest first: the export."""
        ...

    @abstractmethod
    async def due(self, user_id: str, on: date) -> list[dict[str, Any]]:
        """Entries whose review date is on or before `on` and that have no
        review yet, soonest due first."""
        ...

    @abstractmethod
    async def add_note(
        self, user_id: str, decision_id: str, note: dict[str, Any]
    ) -> dict[str, Any] | None:
        """`note`: id, content, hash, created_at. None when the entry isn't
        the user's."""
        ...

    @abstractmethod
    async def add_review(
        self, user_id: str, decision_id: str, review: dict[str, Any]
    ) -> dict[str, Any] | None:
        """`review`: id, as_of, content, hash, created_at. None when the
        entry isn't the user's."""
        ...


class ReconciliationRepository(ABC):
    """Statements with the bank's balances, the cleared flag on postings, and
    completed reconciliations. Amounts in minor units of the account's
    currency."""

    @abstractmethod
    async def add_statement(self, user_id: str, record: dict[str, Any]) -> str:
        """A statement typed in from the bank's: account_id, period_start,
        period_end, opening_balance_minor, closing_balance_minor, bank."""
        ...

    @abstractmethod
    async def statements(
        self, user_id: str, statement_id: str | None = None
    ) -> list[dict[str, Any]]:
        """The user's statements that carry the bank's balances (and an
        account), newest period first, each with its `reconciliation` (None
        until completed); only `statement_id` when given."""
        ...

    @abstractmethod
    async def postings(
        self, user_id: str, account_id: str, from_date: str, to_date: str
    ) -> list[dict[str, Any]]:
        """The postings on the account dated in the period, with their entry's
        date and description and their `cleared` flag."""
        ...

    @abstractmethod
    async def set_cleared(self, user_id: str, posting_ids: list[str], cleared: bool) -> None:
        """Set the cleared flag on the user's own postings named."""
        ...

    @abstractmethod
    async def complete(self, user_id: str, record: dict[str, Any]) -> None:
        """Record a completed reconciliation: statement_id,
        cleared_total_minor, difference_minor (0), completed_by."""
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
        kind: str = "import",
        balances_minor: tuple[int, int] | None = None,
    ) -> None:
        """Store the statement and its transactions, and fill in each
        transaction's new `id` and `statement_id`. `kind` is "import" (a file
        or a feed) or "drafts" (a batch of drafted transactions).
        `balances_minor`: the bank's opening and closing balance, for
        reconciling."""
        ...

    @abstractmethod
    async def open_drafts(self, user_id: str, account_id: str) -> str | None:
        """The account's drafts batch still in review (a row of it waiting),
        locked until the unit of work ends; None when there is none."""
        ...

    @abstractmethod
    async def add_rows(
        self,
        user_id: str,
        statement_id: str,
        transactions: list[Any],
        *,
        period_start: str,
        period_end: str,
    ) -> None:
        """Add transactions to one of the user's statements (a drafts batch),
        widen its period to take them in, and fill in each one's `id` and
        `statement_id`."""
        ...

    @abstractmethod
    async def imported_between(
        self,
        user_id: str,
        from_date: str,
        to_date: str,
        *,
        account_id: str | None = None,
        excluding_statement: str | None = None,
    ) -> list[Any]:
        """The user's parsed transactions dated `from_date`..`to_date`, what a
        new import is checked against for duplicates: the discarded ones too
        (a discarded card hold is still that transaction), but not those
        already found to duplicate another, which that one stands for.

        With `account_id`, only rows on that account or on a statement with
        no account (which may be on any). `excluding_statement`'s rows are
        left out unless posted: a statement being imported again on purpose
        does not duplicate itself."""
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
    async def get_by_ids(
        self, user_id: str, ids: list[str], *, for_update: bool = False
    ) -> list[Any]:
        """The user's parsed transactions with these ids. `for_update` locks
        them until the unit of work ends, so two approvals of the same rows
        post them once: the second waits, then reads them posted."""
        ...

    @abstractmethod
    async def set_choice(self, user_id: str, transaction_id: str, fields: dict[str, Any]) -> None:
        """Record what a person (or their AI) chose for a pending transaction:
        its accounts, category and need. Nothing else about it changes."""
        ...

    @abstractmethod
    async def list_statements(self, user_id: str, limit: int = 50) -> list[Any]:
        """Every statement this user has uploaded, newest first.

        The rows were always persisted, and this exposes them: a client can
        show the history of imports.
        """
        ...

    @abstractmethod
    async def mark_posted(self, transaction_id: str, entry_id: str) -> None: ...

    async def export(self, user_id: str) -> list[dict[str, Any]]:
        """Every statement of the user's, each with all its parsed
        transactions whatever their state, for the data export."""
        raise NotImplementedError

    @abstractmethod
    async def get_statement(self, user_id: str, statement_id: str) -> dict[str, Any] | None:
        """Return a single statement's metadata (bank, period, storage key), or None."""
        ...


class LLMClient(ABC):
    """One user's way to a language model, for one request, whichever provider
    is behind it: Anthropic or OpenAI on an API key, or the user's ChatGPT plan.

    LlmCredentialService.resolve builds it: it has already decided the
    provider, the credential and the model for each tier, so nothing that
    holds one ever branches on which company runs the model. Two ways in, which
    between them cover every AI feature:

    - `generate`: one instruction, one input, the model's text back. Statement
      sorting, quick add and the briefing ask for JSON and
      parse it themselves; naming a conversation takes the text as it is.
    - `chat_model`: a LangChain chat model with tool calling and streaming, for
      the LangGraph agents.

    Errors are the typed ones in domain/llm.py, in our own words.
    """

    #: "anthropic", "openai" or "chatgpt".
    provider: str
    #: "user" when the user's own key or plan pays, "platform" for the
    #: deployment's key.
    source: str

    @property
    @abstractmethod
    def fingerprint(self) -> str:
        """Names this provider and credential without containing it: what a
        compiled agent graph is cached under."""
        ...

    @abstractmethod
    def model_for(self, tier: Tier) -> str:
        """The model this client runs for a tier ("fast" or "best")."""
        ...

    @abstractmethod
    async def generate(
        self,
        *,
        instructions: str,
        input: str,
        tier: Tier = "fast",
        model: str | None = None,
        schema: dict[str, Any] | type[BaseModel] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """The model's answer to `input` under `instructions`, once it is complete.

        With `schema` (a JSON Schema, or a pydantic model), the answer is JSON
        of that shape; the caller still parses and validates it, because a
        model only ever proposes. `max_output_tokens` and `temperature` are
        hints a route honours where it may: Anthropic does, as it always has;
        the ChatGPT plan forbids both, and so the OpenAI routes never send them.
        """
        ...

    @abstractmethod
    def chat_model(
        self,
        *,
        model: str | None = None,
        tier: Tier = "best",
        cache: bool = False,
        **options: Any,
    ) -> Any:
        """A LangChain chat model (tool calling, streaming) for the agents.

        `cache` asks for prompt caching where the provider offers it; `options`
        are Anthropic's own settings (temperature, max_tokens), which the
        OpenAI routes do not send.
        """
        ...


class StoragePort(ABC):
    @abstractmethod
    async def upload(self, user_id: str, key: str, data: bytes) -> str:
        """Upload and return the storage URL."""
        ...

    @abstractmethod
    async def download(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete_user(self, user_id: str) -> int:
        """Delete every file uploaded for this user; how many there were."""
        ...


class ConversationStore(ABC):
    """A person's conversations with Salli's AI, where the agents keep them
    (LangGraph's checkpointer): read for their export, deleted with them."""

    @abstractmethod
    async def export(self, user_id: str) -> list[dict[str, Any]]:
        """Each conversation, newest first: its thread id, when it last
        changed and its messages in order (role, text, the tools called)."""
        ...

    @abstractmethod
    async def delete_all(self, user_id: str) -> int:
        """Delete every thread of the user's, review workflows' included;
        how many there were."""
        ...


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


class AccountNotFound(KeyError):
    """A posting names an account that is not the caller's: one that does not
    exist, or another user's. The two look the same to the caller, so an
    account id says nothing about anyone else's ledger."""

    def __init__(self, account_ids: Collection[str]) -> None:
        self.account_ids = tuple(sorted(account_ids))
        super().__init__(self.account_ids)

    def __str__(self) -> str:
        return "Account not found: " + ", ".join(self.account_ids)


class HoldingNotFound(KeyError):
    """A scenario names a holding that is not one of the caller's: one that
    does not exist, or another user's. They look the same, so a holding id
    says nothing about anyone else's portfolio, and a security the caller
    doesn't hold can never get into a scenario."""

    def __init__(self, holding_ids: Collection[str]) -> None:
        self.holding_ids = tuple(sorted(holding_ids))
        super().__init__(self.holding_ids)

    def __str__(self) -> str:
        return "Holding not found: " + ", ".join(self.holding_ids)


class DebtNotFound(KeyError):
    """A request names a debt that is not one of the caller's active debts:
    one that does not exist, one they closed, or another user's. They look
    the same, so a debt id says nothing about anyone else's."""

    def __init__(self, debt_ids: Collection[str]) -> None:
        self.debt_ids = tuple(sorted(debt_ids))
        super().__init__(self.debt_ids)

    def __str__(self) -> str:
        return "Debt not found: " + ", ".join(self.debt_ids)


class PrincipleNotFound(KeyError):
    """A principle that is not the caller's: one that does not exist, or
    another user's. They look the same."""

    def __init__(self, principle_id: str) -> None:
        self.principle_id = principle_id
        super().__init__(principle_id)

    def __str__(self) -> str:
        return f"Principle not found: {self.principle_id}"


class DecisionNotFound(KeyError):
    """A decision that is not the caller's: one that does not exist, or
    another user's. They look the same."""

    def __init__(self, decision_id: str) -> None:
        self.decision_id = decision_id
        super().__init__(decision_id)

    def __str__(self) -> str:
        return f"Decision not found: {self.decision_id}"


class ProfileMissing(LookupError):
    """The user has no profile row yet, so nothing that needs one (a base
    currency, a setting) can be read or written. Callers create it first:
    `UserProfileService.ensure_user`, which `salli-server setup` and onboarding run."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"User {user_id} has no profile")
        self.user_id = user_id


class AccountCodeTaken(ValueError):
    """The user already has an account with this code (active or not)."""

    def __init__(self, code: str) -> None:
        super().__init__(f"An account with code {code} already exists")
        self.code = code


class EntryRefTaken(ValueError):
    """An entry was booked with this client_ref meanwhile (a retry that ran
    at the same time): core_0027's unique index refused the second."""

    def __init__(self, external_ref: str) -> None:
        super().__init__(f"An entry is already booked with {external_ref}")
        self.external_ref = external_ref


class FxUnavailableError(LookupError):
    """No source could give this rate. Never answered with a made-up number."""


class FxRatePort(ABC):
    @abstractmethod
    async def rate(self, from_currency: str, to_currency: str, on_date: str) -> FxQuote:
        """How many `to_currency` one `from_currency` bought on `on_date` (YYYY-MM-DD).

        Raises FxUnavailableError when there is no such rate.
        """
        ...


class FetchRefused(ValueError):
    """A URL Salli won't fetch (not https, not on the public internet), or a
    response it won't read (too large, too slow, not text, a redirect it won't
    follow). The message is safe to show: it never describes the network."""


@dataclass(frozen=True)
class FetchedDocument:
    #: Where the text finally came from, after any redirects followed.
    url: str
    text: str


class DocumentFetcher(ABC):
    """Fetches a text document from a URL a user gave, guarded against
    server-side request forgery (adapters/net)."""

    @abstractmethod
    async def fetch_text(self, url: str) -> FetchedDocument:
        """The document at `url`, or FetchRefused."""
        ...


@dataclass(frozen=True)
class PriceQuote:
    """A closing price: what one unit of `symbol` closed at on `on`, in
    `currency`, as quoted that day (not adjusted for later splits), and
    where it came from ("user" for one a person recorded)."""

    symbol: str
    on: date
    close: Decimal
    currency: str
    source: str


class PriceUnavailableError(LookupError):
    """No price for this symbol (on or before that date). Never answered
    with a made-up number."""


class MarketDataPort(ABC):
    """Closing prices for a symbol.

    Salli's implementation is the price history a user keeps
    (application/market_data.py). It ships no network provider: none it
    could find was both keyless and clearly licensed for an open-source app
    that also runs as a hosted service (in 2026 Stooq's downloads need a key,
    and CoinGecko's keyless API is not for production use and its terms
    discourage storing its data). One added later must be asked only when a
    user asks for a refresh, and what it says stored under its name — never
    fetched implicitly, on a read.
    """

    @abstractmethod
    async def latest(
        self, symbol: str, *, currency: str | None = None, on_or_before: date | None = None
    ) -> PriceQuote:
        """The most recent close on or before `on_or_before` (by default, the
        most recent there is). `currency` asks for a price in that currency
        where the source can quote one; the quote says what it is in.
        Raises PriceUnavailableError."""
        ...

    @abstractmethod
    async def history(self, symbol: str, start: date, end: date) -> list[PriceQuote]:
        """Every close from `start` to `end` inclusive, oldest first."""
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
    async def cited_by_entry(self, user_id: str, doc_id: str) -> bool:
        """Whether one of the user's journal entries cites the document."""
        ...

    @abstractmethod
    async def filed_return_citing(self, user_id: str, doc_id: str) -> date | None:
        """The latest filing date of a filed tax return whose period holds an
        entry citing the document, or None."""
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
        """The ISO code the user's amounts are kept in. `ProfileMissing` if none."""
        profile = await self.get(user_id)
        if not profile or not profile.get("base_currency"):
            raise ProfileMissing(user_id)
        return str(profile["base_currency"])

    async def has_financial_data(self, user_id: str) -> bool:
        """Whether anything is stored in the user's base currency yet."""
        raise NotImplementedError

    async def get_ai_settings(self, user_id: str) -> dict[str, Any]:
        """`{"provider": str | None, "models": {provider: {tier: model}}}`:
        which provider powers this user's AI (None is "auto"), and the models
        they chose themselves. The defaults when there is no profile."""
        raise NotImplementedError

    async def set_ai_settings(
        self, user_id: str, *, provider: str | None, models: dict[str, Any]
    ) -> None:
        """Replace both, `provider` None meaning "auto". `ProfileMissing` if
        there is no profile."""
        raise NotImplementedError

    async def set_tax_identity(
        self,
        user_id: str,
        *,
        tax_residency: str | None,
        tax_ids: list[dict[str, str]],
    ) -> None:
        """Write the tax residency (None clears it) and the tax ids exactly as
        given. `ProfileMissing` if there is no profile."""
        raise NotImplementedError

    async def set_monthly_budget(self, user_id: str, lines: list[dict[str, Any]]) -> None:
        """Replace the monthly budget's lines (`limit_minor` in the base
        currency). `ProfileMissing` if there is no profile."""
        raise NotImplementedError

    async def set_fi_plan(self, user_id: str, stored: dict[str, Any]) -> None:
        """Replace the user's FI plan with `stored`, as `FiPlan.as_stored()`
        writes it. `ProfileMissing` if there is no profile."""
        raise NotImplementedError

    async def set_fi_assumptions(self, user_id: str, stored: dict[str, Any]) -> None:
        """Replace the user's own FI assumptions with `stored`, as
        `OwnAssumptions.as_stored()` writes them. `ProfileMissing` if there is
        no profile."""
        raise NotImplementedError

    async def set_lock_date(self, user_id: str, lock_date: str | None) -> None:
        """Close the books up to and including `lock_date` (YYYY-MM-DD), or
        open them (None). `ProfileMissing` if there is no profile."""
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


class AiConnectionRepository(ABC):
    """Per-user sign-ins with an AI provider's plan (ChatGPT), stored sealed.

    As dumb as LlmCredentialRepository, for the same reason: it moves the
    sealed blob and the few columns beside it, and never encrypts or decrypts.
    A row is a dict of `sealed`, `key_version`, `status`, `status_detail`,
    `expires_at`, `paused_until`, `created_at` and `updated_at`.
    """

    @abstractmethod
    async def get(self, user_id: str, provider: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def get_for_update(self, user_id: str, provider: str) -> dict[str, Any] | None:
        """The row, locked until this unit of work ends (SELECT ... FOR
        UPDATE): a renewal holds it while it spends the refresh token, so a
        second renewal waits and then sees the new one."""
        ...

    @abstractmethod
    async def save(self, user_id: str, provider: str, fields: dict[str, Any]) -> bool:
        """Create the row or replace these fields. True when it was created."""
        ...

    @abstractmethod
    async def update(self, user_id: str, provider: str, fields: dict[str, Any]) -> bool:
        """Change these fields of an existing row. False when there is none."""
        ...

    @abstractmethod
    async def delete(self, user_id: str, provider: str) -> bool: ...


class InstanceSettingsRepository(ABC):
    """Facts about the instance as a whole (not any user's), by key."""

    @abstractmethod
    async def get_or_create(self, key: str, value: str) -> str:
        """The stored value for `key`, storing `value` first if there is none.
        Safe when two processes race: both get the one value that was kept."""
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
    async def export(self, user_id: str) -> list[dict[str, Any]]:
        """Every report as stored, newest first: briefings, and the advisor's
        earlier reports with their recommendations."""
        ...

    @abstractmethod
    async def ran_today(self, user_id: str, day: str) -> bool: ...


class FireStrategyRepository(ABC):
    """The FIRE strategies an earlier Salli drafted with a model. None are
    made any more; they are kept for the user's export and erased with them."""

    @abstractmethod
    async def export(self, user_id: str) -> list[dict[str, Any]]:
        """Every version as stored, newest first."""
        ...


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
    async def delete(self, user_id: str, holding_id: str) -> None:
        """Delete the holding, and with it its transactions."""
        ...

    async def lock(self, user_id: str, holding_id: str) -> None:
        """Hold the holding against concurrent changes to its history until
        the unit of work ends. A store with no concurrency need not."""
        return None


class InvestmentPolicyRepository(ABC):
    """A user's investment policy statements: one version a row, added and
    never changed; the latest is the one in force."""

    @abstractmethod
    async def add(self, user_id: str, content: dict[str, Any]) -> dict[str, Any]:
        """Store `content` as the next version; returns {id, version, content,
        created_at}."""
        ...

    @abstractmethod
    async def list(self, user_id: str) -> list[dict[str, Any]]:
        """Every version, oldest first."""
        ...


class HoldingTransactionRepository(ABC):
    """Holdings' transactions, as plain dicts of their stored columns: money in
    minor units of the holding's currency, quantities, prices, ratios and the
    rate as Decimal, `transaction_date` as YYYY-MM-DD, and `lots` as a list of
    {"lot_id", "quantity"} with the quantity a decimal string."""

    @abstractmethod
    async def list(self, user_id: str, holding_id: str | None = None) -> list[dict[str, Any]]:
        """One holding's transactions, or all of this user's, in the order they
        were recorded (which breaks ties between transactions on one date)."""
        ...

    @abstractmethod
    async def get(self, user_id: str, transaction_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def save(self, user_id: str, transaction: dict[str, Any]) -> str: ...

    @abstractmethod
    async def update(self, user_id: str, transaction_id: str, fields: dict[str, Any]) -> bool:
        """Set the given columns, None included. False if there is no such transaction."""
        ...

    @abstractmethod
    async def delete(self, user_id: str, transaction_id: str) -> bool: ...


class HoldingPriceRepository(ABC):
    """The closing prices a user keeps, one per symbol, currency and day, as plain
    dicts: symbol (upper case), price_date (YYYY-MM-DD), close (Decimal),
    currency, source."""

    @abstractmethod
    async def upsert(self, user_id: str, price: dict[str, Any]) -> str:
        """Record a close; one already recorded for that symbol, currency and
        day is replaced. Returns its id."""
        ...

    @abstractmethod
    async def list(
        self,
        user_id: str,
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Closes oldest first: one symbol's or all, from `start` to `end`
        inclusive (YYYY-MM-DD; either may be open)."""
        ...

    @abstractmethod
    async def get(self, user_id: str, quote_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def delete(self, user_id: str, quote_id: str) -> bool: ...


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
    """Append-only (core_0027's trigger): rows are added, never changed."""

    @abstractmethod
    async def log(
        self,
        user_id: str,
        action: str,
        params: dict[str, Any],
        decision: str,
        client_id: str | None = None,
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
        """Dynamic Client Registration (RFC 7591). Returns the new client's
        record. A client that registers itself is never first party."""
        ...

    @abstractmethod
    async def get(self, client_id: str) -> dict[str, Any] | None:
        """{client_id, client_name, redirect_uris, first_party}, or None."""
        ...


class McpConnectionRow(TypedDict):
    """One connected client grant (a client, for one resource)."""

    #: The newest access token of the grant: what revoking it takes.
    token_id: str
    client_id: str
    #: As the client registered itself; "Unnamed app" when it gave no name.
    client_name: str
    scope: str
    #: The resource it was issued for: None or the MCP URL for an AI client,
    #: the API's for the user's own CLI.
    resource: str | None
    connected_at: datetime


class SignInGrantRow(TypedDict):
    """One live OAuth sign-in to the REST API (the CLI on a machine, the
    console in a tab, another API client), for the list of sign-ins."""

    grant_id: str
    client_id: str
    #: As the client is known: "Salli CLI", "Salli console", or as a client
    #: that registered itself named itself ("Unnamed app" when it gave none).
    client_name: str
    created_at: datetime
    last_used_at: datetime | None
    #: When it ends unless revoked first: its absolute end (the console's),
    #: or when its newest refresh token runs out.
    expires_at: datetime | None


class OAuthTokenRepository(ABC):
    """Tokens are looked up by hash; every access and refresh token belongs to
    a grant (one sign-in), which rotation keeps and revocation ends."""

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
        authenticated_at: datetime,
    ) -> None: ...

    @abstractmethod
    async def get_authorization_code(self, code: str) -> dict[str, Any] | None:
        """Look up without consuming. None if missing/expired. Callers must
        call delete_authorization_code() only after validation succeeds, so a
        failed PKCE/client check doesn't burn a code a legitimate retry needs."""
        ...

    @abstractmethod
    async def delete_authorization_code(self, code: str) -> bool:
        """Marks a code used — call only once the exchange has succeeded.
        False when it was already gone (two exchanges racing for one code)."""
        ...

    @abstractmethod
    async def create_grant(
        self,
        user_id: str,
        client_id: str,
        scope: str,
        resource: str | None,
        authenticated_at: datetime,
        expires_at: datetime | None,
    ) -> str:
        """A new sign-in; returns its id."""
        ...

    @abstractmethod
    async def save_access_token(
        self,
        token_hash: str,
        grant_id: str,
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
        grant_id: str,
        access_token_id: str,
        client_id: str,
        user_id: str,
        scope: str,
        resource: str | None,
        expires_at: datetime,
    ) -> None: ...

    @abstractmethod
    async def get_access_token(self, token_hash: str) -> dict[str, Any] | None:
        """None if missing, expired or revoked, or if its grant is revoked or
        past its absolute end. Includes the holding client's `client_name`,
        whether it is first party (`client_first_party`) and its
        `client_step_up_seconds`, and the grant's `grant_id` and
        `authenticated_at`."""
        ...

    @abstractmethod
    async def find_refresh_token(self, token_hash: str) -> dict[str, Any] | None:
        """A refresh token in any state, with its grant's: `revoked_at`,
        `expires_at`, `access_revoked_at`, `grant_id`, `grant_revoked_at`,
        `grant_expires_at`, `authenticated_at`. None if never issued."""
        ...

    @abstractmethod
    async def rotate_refresh_token(self, token_hash: str) -> bool:
        """Revokes a live refresh token as it is used. False when it was
        already revoked: then it is being used a second time."""
        ...

    @abstractmethod
    async def get_grant(self, grant_id: str) -> dict[str, Any] | None:
        """A grant in any state, or None."""
        ...

    @abstractmethod
    async def grant_of_token(self, token_hash: str) -> dict[str, Any] | None:
        """The grant an access or refresh token belongs to, whatever either's
        state: {id, user_id, client_id, resource}. None if never issued."""
        ...

    @abstractmethod
    async def revoke_grant(self, grant_id: str, user_id: str | None = None) -> int:
        """Revoke a grant and every token in it; with `user_id`, only if it is
        theirs. Returns how many rows it revoked (0: none, or not theirs)."""
        ...

    @abstractmethod
    async def touch_grant(self, grant_id: str, at: datetime) -> None:
        """Record that a grant's access token was just used."""
        ...

    @abstractmethod
    async def revoke_access_token(self, token_id: str, user_id: str) -> bool:
        """Revokes only if the token belongs to user_id. Returns whether it revoked anything."""
        ...

    @abstractmethod
    async def token_exists(self, token_hash: str) -> bool:
        """Whether an access or refresh token with this hash was ever issued,
        expired, revoked or for any resource."""
        ...

    @abstractmethod
    async def get_access_token_by_id(self, token_id: str, user_id: str) -> dict[str, Any] | None:
        """The user's access token row by id, whatever its state (expired or
        revoked included), with its client and resource. None if not theirs."""
        ...

    @abstractmethod
    async def revoke_client_grant(self, user_id: str, client_id: str, resource: str | None) -> int:
        """Revoke every grant (and its tokens) this client holds for this user
        and resource. Returns how many tokens it revoked."""
        ...

    @abstractmethod
    async def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke every grant, access and refresh token any client holds for
        this user (signing them out everywhere). Returns how many tokens it
        revoked."""
        ...

    @abstractmethod
    async def list_active_connections(
        self, user_id: str, resource: str | None = None
    ) -> list[McpConnectionRow]:
        """Connected clients for a user: one row per client grant (client and
        resource) holding a live access token or a live refresh token, joined
        with the client's display name. With `resource`, only grants for it."""
        ...

    @abstractmethod
    async def list_sign_in_grants(
        self, user_id: str, resource: str, now: datetime
    ) -> list[SignInGrantRow]:
        """The user's live grants for `resource`, one row each, newest first:
        not revoked, not past an absolute end, and holding a live access or
        refresh token."""
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
    #: An ISO 4217 code, normalised by the connector; or a provider's own unit
    #: (points, miles) as it gave it, which `is_currency` says no ledger holds.
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
    #: Accounts whose institution reported a problem: what came back for
    #: them may be incomplete, so their import marker is not moved on.
    troubled: frozenset[str] = frozenset()


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
    async def list_due(
        self, attempted_before: datetime, failed_before: datetime, now: datetime
    ) -> list[tuple[str, str]]:
        """(user id, connection id) of every connection, anyone's, due a sync:
        never attempted or last attempted before `attempted_before`, one in
        error only if attempted before `failed_before`, and none another sync
        holds (`claim`). For the scheduler."""
        ...

    @abstractmethod
    async def claim(self, user_id: str, connection_id: str, now: datetime, until: datetime) -> bool:
        """Hold the connection for a sync until `until`, and record the
        attempt. False when another sync holds it."""
        ...

    @abstractmethod
    async def release(self, user_id: str, connection_id: str) -> None: ...

    @abstractmethod
    async def update_account(
        self, user_id: str, connection_id: str, remote_id: str, fields: dict[str, Any]
    ) -> None:
        """Set a bank account's `last_imported_at` or `notes`."""
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


class AccessGrantRepository(ABC):
    """Read-only access one member gives another to their books."""

    @abstractmethod
    async def create(self, grantor_id: str, grantee_id: str) -> dict[str, Any]:
        """A live grant: {id, grantor_id, grantee_id, created_at}; the live
        one already there for the pair, if any."""
        ...

    @abstractmethod
    async def list_for(self, user_id: str) -> list[dict[str, Any]]:
        """The live grants the user gave or holds, newest first."""
        ...

    @abstractmethod
    async def is_live(self, grantor_id: str, grantee_id: str) -> bool: ...

    @abstractmethod
    async def revoke(self, user_id: str, grant_id: str) -> dict[str, Any] | None:
        """End a live grant the user gave or holds; it, or None."""
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
        permissions: list[str],
    ) -> dict[str, Any]:
        """A new token holding `permissions` (application/permissions.py)."""
        ...

    @abstractmethod
    async def list(self, user_id: str) -> list[dict[str, Any]]:
        """The user's tokens that are not revoked, newest first (never the
        hash), each with its `permissions`."""
        ...

    @abstractmethod
    async def get_active(self, token_hash: str) -> dict[str, Any] | None:
        """The token if it exists, is not revoked and has not expired."""
        ...

    @abstractmethod
    async def revoke(self, user_id: str, token_id: str) -> bool: ...

    @abstractmethod
    async def revoke_all(self, user_id: str) -> int:
        """Revoke every live token of the user's; how many."""
        ...

    @abstractmethod
    async def touch(self, token_id: str, at: datetime) -> None:
        """Record use, for "last used" in the list."""
        ...


# ── Sign-in: Salli's own accounts ────────────────────────────────────────────


class PasswordHasher(ABC):
    """Turns a password into a hash that can be stored, and checks one
    against it (adapters/auth/passwords.py: argon2id). Async because a good
    hash is slow on purpose: an adapter runs it off the event loop."""

    @abstractmethod
    async def hash(self, password: str) -> str: ...

    @abstractmethod
    async def verify(self, password_hash: str, password: str) -> bool:
        """Whether `password` is the one `password_hash` was made from. False,
        never an exception, for a hash it can't read."""
        ...

    @abstractmethod
    def needs_rehash(self, password_hash: str) -> bool:
        """Whether a stored hash was made with other parameters than the
        current ones, and should be made again at the next sign-in."""
        ...


class LoginRepository(ABC):
    """Who can sign in (`logins`, one per user, keyed by the user id), their
    sessions (`login_sessions`, stored hashed), and failed sign-ins
    (`login_failures`, by a hash of what was tried) for throttling."""

    @abstractmethod
    async def create(
        self, user_id: str, email: str, password_hash: str, *, is_owner: bool, at: datetime
    ) -> dict[str, Any]:
        """A login for an existing profile. `email` is already normalised."""
        ...

    @abstractmethod
    async def get(self, user_id: str) -> dict[str, Any] | None:
        """{user_id, email, is_owner, password_hash, password_changed_at,
        created_at, totp_secret, totp_key_version, totp_enabled_at,
        totp_recovery_codes_left}."""
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def owner(self) -> dict[str, Any] | None:
        """The instance's owner's login, if there is one yet."""
        ...

    @abstractmethod
    async def list(self) -> list[dict[str, Any]]:
        """Every login, oldest first, without password hashes."""
        ...

    @abstractmethod
    async def set_password(
        self, user_id: str, password_hash: str, *, changed_at: datetime | None
    ) -> bool:
        """Store a new hash. `changed_at` None: the same password, hashed
        again with newer parameters, so not a change."""
        ...

    @abstractmethod
    async def create_invitation(
        self,
        token_hash: str,
        email: str,
        base_currency: str | None,
        at: datetime,
        expires_at: datetime,
    ) -> None: ...

    @abstractmethod
    async def get_invitation(self, token_hash: str, now: datetime) -> dict[str, Any] | None:
        """{email, base_currency} of an invitation not used and not expired."""
        ...

    @abstractmethod
    async def use_invitation(self, token_hash: str, now: datetime) -> dict[str, Any] | None:
        """Mark it used, if it was still good: {email, base_currency}, or None."""
        ...

    @abstractmethod
    async def create_session(
        self,
        user_id: str,
        token_hash: str,
        user_agent: str | None,
        at: datetime,
        expires_at: datetime,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def get_session(self, token_hash: str, now: datetime) -> dict[str, Any] | None:
        """The session if it exists, is not revoked and has not expired."""
        ...

    @abstractmethod
    async def list_sessions(self, user_id: str, now: datetime) -> list[dict[str, Any]]:
        """The user's live sessions, newest first, never the hash."""
        ...

    @abstractmethod
    async def touch_session(self, session_id: str, at: datetime) -> None: ...

    @abstractmethod
    async def revoke_session(self, user_id: str, session_id: str, at: datetime) -> bool: ...

    @abstractmethod
    async def revoke_sessions(self, user_id: str, at: datetime, *, keep: str | None = None) -> int:
        """Revoke every live session of the user's but `keep`; how many."""
        ...

    @abstractmethod
    async def record_failure(self, key_hash: str, at: datetime) -> None: ...

    @abstractmethod
    async def failures_since(self, key_hash: str, since: datetime) -> list[datetime]:
        """When each failure for `key_hash` after `since` happened, oldest first."""
        ...

    @abstractmethod
    async def clear_failures(self, key_hash: str) -> None: ...

    @abstractmethod
    async def prune_failures(self, before: datetime) -> None:
        """Forget failures too old to count."""
        ...

    @abstractmethod
    async def set_totp(self, user_id: str, sealed: str | None, key_version: int | None) -> None:
        """Start two-step sign-in afresh with a new sealed secret, not yet
        enabled; None for both turns it off. Either way, forgets the last
        step used and the recovery codes."""
        ...

    @abstractmethod
    async def enable_totp(
        self, user_id: str, recovery_hashes: list[str], *, step: int, at: datetime
    ) -> bool:
        """Turn on the secret set, with these recovery codes, `step` being
        the code just proved. False if there is no secret, or it is on."""
        ...

    @abstractmethod
    async def use_totp_step(self, user_id: str, step: int) -> bool:
        """Record a code from time step `step` as used. False if a code from
        it, or a later one, already was."""
        ...

    @abstractmethod
    async def use_recovery_code(self, user_id: str, code_hash: str) -> bool:
        """Use up a recovery code. False if it is not one of theirs (any more)."""
        ...


@dataclass(frozen=True)
class ExternalIdentity:
    """Who an `IdentityProvider` says a bearer token belongs to."""

    user_id: str
    email: str | None = None


class IdentityProvider(ABC):
    """An identity provider outside Salli (an OIDC provider, say) whose
    tokens the API should accept as a person's own session. Salli ships none:
    a deployment supplies one through an extension (`Extension.
    identity_provider`). The API asks it only about a bearer token that is
    none of Salli's own, and the person must already have an account here:
    a provider vouching for someone never creates one."""

    @abstractmethod
    async def verify(self, token: str) -> ExternalIdentity | None:
        """Whose token this is, or None if it isn't one of this provider's
        (or is no longer valid). Must not raise for a token it doesn't know."""
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


class ChatGPTPlanPolicy(ABC):
    """Whether a user may power Salli's AI with their ChatGPT plan here.

    OpenAI lets open-source and self-hosted apps offer ChatGPT plan usage;
    a paid or remotely hosted product needs its approval first. Salli as
    shipped allows it (application/defaults.py), subject to
    `Settings.salli_chatgpt_plan_usage`; a hosted deployment's extension can
    say no until it is approved, or yes for only some users while it is
    being reviewed. Asked when a user connects their plan and on every
    request that would use it.
    """

    @abstractmethod
    async def allows(self, user_id: str) -> bool: ...


class Surface(StrEnum):
    """A response whose depth an `EntitlementPolicy` may shape."""

    FI_PROJECTIONS = "fi.projections"
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


# ── Notifications ────────────────────────────────────────────────────────────
#
# The third seam: delivering a digest (docs/design/decision-lab-phase-3.md,
# section 4). Core builds every message (domain/notifications), deterministic
# and in its own words; where it goes is the deployment's. Salli ships no
# sender: `NoNotifier` (application/defaults.py) sends nothing, and an
# extension supplies a `Notifier` (Extension.notifier), at most one per
# deployment.


class Delivery(StrEnum):
    """What became of a notification handed to a `Notifier`."""

    SENT = "sent"
    #: The deployment has nowhere to send this person's messages.
    NO_DESTINATION = "no_destination"
    #: Not delivered: tried again on a later run in the same period, at most
    #: three attempts in all.
    FAILED = "failed"


class Notifier(ABC):
    """Delivers a message core built, to wherever the deployment sends this
    person's messages (an email, a push, a chat). It gets the user's id and
    keeps its own destinations: core never stores an address or a chat id
    for sending (only the phone app's push tokens, for Salli's own relay
    notifier, `adapters/net/push.py`). It may restyle the message, never add to it.
    `Notification.id` is the same for every attempt in a period, so a sender
    can drop a repeat. Must not raise for an ordinary failure: return FAILED."""

    @abstractmethod
    async def send(self, notification: Notification) -> Delivery: ...


class NotificationRepository(ABC):
    """A person's digest preferences and the log of what was delivered, and
    when the digest job last ran. Every per-user query names the owner."""

    @abstractmethod
    async def add_device(
        self, user_id: str, token_hash: str, token: str, key_version: int | None, platform: str
    ) -> None:
        """Register a push device (insert, or replace one with the same hash)."""
        ...

    @abstractmethod
    async def remove_device(self, user_id: str, token_hash: str) -> bool:
        """Remove the person's device with this hash; False if none."""
        ...

    @abstractmethod
    async def devices(self, user_id: str) -> list[dict[str, Any]]:
        """The person's push devices: `token`, `key_version`, `platform`,
        `token_hash`, `created_at`."""
        ...

    @abstractmethod
    async def device_users(self) -> list[dict[str, Any]]:
        """Everyone with a push device: `user_id` and `time_zone`."""
        ...

    @abstractmethod
    async def get_preferences(self, user_id: str) -> dict[str, Any] | None:
        """`{"enabled", "cadence", "weekday", "hour", "items"}`, or None
        while the person has set nothing."""
        ...

    @abstractmethod
    async def save_preferences(self, user_id: str, preferences: dict[str, Any]) -> None:
        """Store them whole (insert or replace)."""
        ...

    @abstractmethod
    async def opted_in(self) -> list[dict[str, Any]]:
        """Everyone with digests on and a time zone: their preferences, with
        `user_id` and `time_zone`."""
        ...

    @abstractmethod
    async def delivery(self, user_id: str, period: str) -> dict[str, Any] | None:
        """The log's row for this person and period, if any."""
        ...

    @abstractmethod
    async def claim(
        self,
        user_id: str,
        *,
        delivery_id: str,
        period: str,
        items: list[dict[str, Any]],
        message_hash: str,
        now: datetime,
        first: bool,
        max_attempts: int,
    ) -> int | None:
        """Take this period's send for this person, atomically: a new row
        (only when `first`), or a FAILED one with fewer than `max_attempts`
        attempts. Marks it `sending` and counts the attempt. Returns the
        attempt's number, or None when another run has it, it went, or its
        attempts are used up. The unique (user, period) key decides a race."""
        ...

    @abstractmethod
    async def finish(self, user_id: str, delivery_id: str, status: str, now: datetime) -> None:
        """Record what became of the attempt: a `Delivery` value."""
        ...

    @abstractmethod
    async def deliveries(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """The person's log, newest period first."""
        ...

    @abstractmethod
    async def record_run(self, at: datetime) -> None:
        """Note that the digest job ran (for `salli-server doctor`)."""
        ...

    @abstractmethod
    async def last_run(self) -> datetime | None:
        """When the digest job last ran, if ever."""
        ...
