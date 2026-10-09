"""
SQLAlchemy ORM models — the adapter layer only.
Domain models (Pydantic) live in domain/accounting/models.py.
These are the storage representations; mappers translate between them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


# ── Accounts ──────────────────────────────────────────────────────────────────


class AccountORM(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("accounts.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # How the tax engine should treat this account. NULL = no tax significance.
    # See `domain.accounting.models.TaxRole` for why this is explicit rather
    # than inferred from `name`.
    tax_role: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint("user_id", "code", name="uq_accounts_user_code"),
        CheckConstraint(
            "type IN ('asset','liability','equity','income','expense')",
            name="ck_accounts_type",
        ),
        CheckConstraint(
            "tax_role IS NULL OR tax_role IN "
            "('apit_credit','ait_credit','foreign_tax_credit',"
            "'qualifying_payment','fsi_income')",
            name="ck_accounts_tax_role",
        ),
    )


# ── Journal Entries & Postings ─────────────────────────────────────────────────


class JournalEntryORM(Base):
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entry_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("journal_entries.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    postings: Mapped[list[PostingORM]] = relationship(
        "PostingORM", back_populates="entry", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('manual','statement','sms','system')",
            name="ck_journal_entries_source",
        ),
        Index("ix_journal_entries_user_date", "user_id", "entry_date"),
    )


class PostingORM(Base):
    __tablename__ = "postings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=False)
    # +1 = DEBIT, -1 = CREDIT
    direction: Mapped[int] = mapped_column(Integer, nullable=False)
    # Transaction currency amount (minor units, e.g. cents)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Units of the owner's base currency per unit of `currency`; high-precision decimal
    fx_rate: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=1)
    fx_rate_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Base-currency amount, in the base currency's minor units; the balance
    # trigger checks these sum to zero per entry. Nothing reads them back.
    base_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    entry: Mapped[JournalEntryORM] = relationship("JournalEntryORM", back_populates="postings")
    tag_links: Mapped[list[PostingTagORM]] = relationship(
        "PostingTagORM",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("direction IN (1, -1)", name="ck_postings_direction"),
        CheckConstraint("amount_minor > 0", name="ck_postings_amount_positive"),
        Index("ix_postings_entry", "entry_id"),
        Index("ix_postings_account", "account_id"),
    )


# ── Tags: a second classification axis, orthogonal to the chart of accounts ───
#
# The account tree answers "which ledger account did this hit". It cannot also
# answer "was this essential" without duplicating the entire tree beneath every
# answer, which is why a separate dimension exists.
#
# Tags are metadata *about* an immutable posting rather than part of it: the
# money record is never edited, but a miscategorised expense must be fixable.


class TagORM(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # "category" (what it was for) | "need" (how necessary — the 50/30/20 split)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    # Seeded tags the reports reference by slug. Renameable, not deletable.
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint("user_id", "kind", "slug", name="uq_tags_user_kind_slug"),
        CheckConstraint("kind IN ('category','need')", name="ck_tags_kind"),
    )


class PostingTagORM(Base):
    __tablename__ = "posting_tags"

    posting_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("postings.id", ondelete="CASCADE"), primary_key=True
    )
    # `kind` is denormalised from the tag so it can sit in the primary key.
    # That is what enforces at most one tag per axis per posting — without it a
    # posting could carry both "essential" and "discretionary" and its amount
    # would be counted twice in any needs-vs-wants breakdown.
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    tag_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )

    tag: Mapped[TagORM] = relationship("TagORM", lazy="joined")

    __table_args__ = (Index("ix_posting_tags_tag", "tag_id"),)


# ── Statement parsing ─────────────────────────────────────────────────────────


class StatementORM(Base):
    __tablename__ = "statements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    bank: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # The bank or card account the statement is for: the money side of every
    # row in it. None for statements imported without one.
    account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("accounts.id"), nullable=True
    )
    period_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    period_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    parsed_transactions: Mapped[list[ParsedTransactionORM]] = relationship(
        "ParsedTransactionORM", back_populates="statement", cascade="all, delete-orphan"
    )


class ParsedTransactionORM(Base):
    __tablename__ = "parsed_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    statement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("statements.id", ondelete="CASCADE"), nullable=False
    )
    raw: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    dedup_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    posted_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("journal_entries.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    statement: Mapped[StatementORM] = relationship(
        "StatementORM", back_populates="parsed_transactions"
    )


# ── Tax computations ──────────────────────────────────────────────────────────


class TaxComputationORM(Base):
    __tablename__ = "tax_computations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    year: Mapped[str] = mapped_column(String(10), nullable=False)
    pack_version: Mapped[str] = mapped_column(String(20), nullable=False)
    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (Index("ix_tax_computations_user_year", "user_id", "year"),)


# ── Documents ─────────────────────────────────────────────────────────────────


class DocumentORM(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # T10, AIT_CERT, etc.
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    year: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


# ── Agent documents (document management + agent memory) ──────────────────────


class AgentDocumentORM(Base):
    __tablename__ = "agent_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="text/plain")
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # "user_upload" | "agent_created" | "agent_memory"
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="agent_created")
    # "documents" | "memories" | "context"
    namespace: Mapped[str] = mapped_column(String(50), nullable=False, default="documents")
    # Named key for memories (unique per user+namespace)
    slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("user_id", "namespace", "slug", name="uq_agent_docs_user_ns_slug"),
        Index("ix_agent_documents_user_id", "user_id"),
        Index("ix_agent_documents_namespace", "user_id", "namespace"),
    )


# ── Agent sessions (persistent conversation threads) ─────────────────────────


class AgentSessionORM(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Which agent persona this thread belongs to ("scrooge" = Pro Mode's
    # existing Salli AI, "buddy" = mobile Buddy Mode) — keeps the two modes'
    # session lists from merging into one, since threads are never shared
    # between personas.
    persona: Mapped[str] = mapped_column(String(20), nullable=False, default="scrooge")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint("user_id", "thread_id", name="uq_agent_sessions_user_thread"),
        Index("ix_agent_sessions_user_active", "user_id", "last_active_at"),
    )


# ── Reminders ─────────────────────────────────────────────────────────────────


class ReminderORM(Base):
    """A due-date task, or (via the nullable alert_type/source_* /severity columns
    added for the Alert/Notification generalization) a system-detected condition
    like a budget overspend or an expiring policy. Additive, not a schema
    rewrite — plain user-created reminders leave the new columns null."""

    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    due_date: Mapped[str] = mapped_column(String(10), nullable=False)
    kind: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    alert_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_domain: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        Index("ix_reminders_user_alert_source", "user_id", "source_domain", "source_id"),
    )


# ── User profile ─────────────────────────────────────────────────────────────


class UserProfileORM(Base):
    """Identity, fact-find, and preferences. `id` is the Supabase auth uid (JWT `sub`)."""

    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ISO 4217 code every posting is measured in (see Posting.fx_rate). Chosen
    # when the profile is created and fixed once the user has financial data:
    # changing it later would silently reinterpret every stored amount.
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # Fact-find (Phase 1 onboarding redo) — all nullable: unanswered until the user
    # completes the corresponding step.
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    dependents_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employment_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    residency_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    employer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ird_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    life_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Gates the MCP OAuth /authorize endpoint (see oauth_* tables below) — off by
    # default. Checked live at token-verification time too, so disabling this
    # immediately kills already-issued MCP tokens, not just future grants.
    mcp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Opt-in for the scheduled daily advisor run. Default off, deliberately:
    # each run is a model call made on the user's behalf, so it has to be
    # something they asked for rather than something that happens to them.
    daily_briefing_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Which Claude model this user's conversations run on. NULL means "no
    # preference" and resolves to ai_models.DEFAULT_MODEL, so the column can be
    # cleared rather than only ever set — see set_preference in the repository,
    # which exists because upsert() cannot write NULL.
    preferred_model: Mapped[str | None] = mapped_column(String(40), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="ck_user_profiles_base_currency"),
    )


class UserLlmCredentialORM(Base):
    """A user's own LLM API key (BYOK), encrypted at rest.

    Its own table rather than columns on user_profiles for three reasons:
    SQLUserProfileRepository.upsert skips None values so it cannot clear a
    field (which would break "remove my key"); a row delete is the natural
    remove; and a decryptable secret is easier to reason about — and to keep
    out of the data export — when it lives nowhere else.

    Unlike the OAuth tokens above, this is NOT hashed. Those are values Salli
    issued and only ever needs to *compare*, so SHA-256 suffices; a user's
    provider key has to be replayed to Anthropic/OpenAI, so it must be
    reversible. Never store plaintext here, even when no encryption key is
    configured — the feature reports unavailable instead.

    `ciphertext` is AES-GCM, with `f"{user_id}|{provider}"` as associated data.
    The AAD is what makes a row swap detectable: without it, moving user A's
    ciphertext onto user B's row (a bad WHERE clause, a restore from a mixed
    backup) would silently bill A for B's calls, and nothing about the
    ciphertext would reveal it. With it, decryption simply fails.
    """

    __tablename__ = "user_llm_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # anthropic
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    # Which configured encryption key sealed this row. Present from day one:
    # rotation can't be retrofitted later, because by the time you need it the
    # old key has to still be around to re-encrypt with the new one.
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Last 4 characters of the plaintext, so the UI can show a recognisable
    # preview without the key ever being readable back.
    last4: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    # Set when a live test call against the provider succeeded. NULL means
    # stored but never confirmed working.
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_llm_cred_user_provider"),)


# ── Financial Independence: goals, score snapshots, advisory reports ──────────


class GoalORM(Base):
    __tablename__ = "fi_goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # fi | retirement | home | emergency_fund | debt_free | wealth_growth | custom
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="custom")
    target_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    current_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    target_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=2)  # 1 high … 3 low
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (Index("ix_fi_goals_user_active", "user_id", "is_active"),)


class GoalAllocationORM(Base):
    """One goal's claim on one account.

    A goal used to carry `current_amount`, a number the user typed and had to
    maintain by hand — nothing tied it to the ledger, so it drifted immediately.
    An allocation is a claim on a *live* balance instead, so progress moves when
    money moves and only when money moves.

    Claims across one account may exceed its balance. That is a normal
    unfunded plan rather than an error, so it is recorded and the shortfall
    surfaced; `domain/fi/allocation.py` apportions the real balance by the
    goal's priority.
    """

    __tablename__ = "goal_allocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    goal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fi_goals.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    allocated_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        # One claim per (goal, account) — a second claim on the same pair is an
        # edit of the first, not an addition.
        UniqueConstraint("goal_id", "account_id", name="uq_goal_allocations_goal_account"),
        CheckConstraint("allocated_minor >= 0", name="ck_goal_allocations_non_negative"),
        Index("ix_goal_allocations_goal", "goal_id"),
    )


class FiScoreORM(Base):
    """Snapshot of a computed FI score (history for trend lines)."""

    __tablename__ = "fi_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    pack_version: Mapped[str] = mapped_column(String(20), nullable=False)
    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (Index("ix_fi_scores_user_date", "user_id", "created_at"),)


class FireStrategyORM(Base):
    """Versioned AI-generated FIRE strategy for a user."""

    __tablename__ = "fire_strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    strategy: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (Index("ix_fire_strategies_user_version", "user_id", "version"),)


class AdvisoryReportORM(Base):
    """A Wealth Advisor run: summary + structured, actionable recommendations."""

    __tablename__ = "advisory_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual"
    )  # manual | scheduled
    fi_score_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # list of {id,title,rationale,category,action_type(none|reminder|journal_entry),
    #          action_params,status(pending|applied|dismissed)}
    recommendations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (Index("ix_advisory_reports_user_date", "user_id", "created_at"),)


# ── Budget ────────────────────────────────────────────────────────────────────


class BudgetORM(Base):
    """One row per budget period. `lines` is a JSONB list of

    {account_id, limit_minor} — mirrors FireStrategyORM's JSONB sub-list convention
    rather than a separate join table, since a budget's category limits are always
    read/written together with their parent period.
    """

    __tablename__ = "budgets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    period_start: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    period_end: Mapped[str] = mapped_column(String(10), nullable=False)
    lines: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (Index("ix_budgets_user_period", "user_id", "period_start"),)


# ── Debt ──────────────────────────────────────────────────────────────────────


class DebtORM(Base):
    """A structured debt — principal, rate, and minimum payment for payoff planning."""

    __tablename__ = "debts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    principal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    apr: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)  # e.g. 0.1850 = 18.5%
    minimum_payment_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (Index("ix_debts_user_active", "user_id", "is_active"),)


# ── Portfolio ─────────────────────────────────────────────────────────────────


class HoldingORM(Base):
    """A manually-declared investment holding — cost basis and current value are
    user-entered, never fetched from a live market-data feed."""

    __tablename__ = "holdings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(40), nullable=False)
    cost_basis_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_value_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (Index("ix_holdings_user_active", "user_id", "is_active"),)


# ── Recurring subscription ────────────────────────────────────────────────────


class RecurringSubscriptionORM(Base):
    """A declared recurring-expense expectation, matched against posted ledger
    entries at query time — never a live bank/merchant integration. A user's own
    recurring expenses (streaming, gym, insurance premiums): personal-finance
    data, declared by the user.
    """

    __tablename__ = "recurring_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    next_due_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("accounts.id"), nullable=True
    )
    grace_days: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    amount_tolerance_pct: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.05)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (Index("ix_recurring_subscriptions_user_active", "user_id", "is_active"),)


# ── Insurance ─────────────────────────────────────────────────────────────────


class PolicyORM(Base):
    """A declared insurance policy — coverage/premium are user-entered, never
    fetched from an insurer's API."""

    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    policy_type: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(200), nullable=False)
    coverage_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    premium_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    premium_frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    expiry_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (Index("ix_policies_user_active", "user_id", "is_active"),)


class InsuranceTargetORM(Base):
    """A declared desired coverage amount per policy type — at most one per
    (user, policy_type), analogous to a budget category limit."""

    __tablename__ = "insurance_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("user_id", "policy_type", name="uq_insurance_targets_user_type"),
    )


# ── Audit log ──────────────────────────────────────────────────────────────────


class AuditLogORM(Base):
    """Immutable record of every agent-initiated write action and its human
    decision (approved/denied) — never updated or deleted once written."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    # This index was declared at the bottom of the file until 2026-07-27, where it
    # landed in OAuthRefreshTokenORM's __table_args__ instead — so the ORM claimed
    # an index named ix_audit_logs_user_created on oauth_refresh_tokens, while
    # migration 32951ad2556e had actually created it on audit_logs. Every
    # autogenerate run emitted a spurious drop-and-recreate-on-the-wrong-table
    # pair as a result. It belongs here, next to the columns it covers.
    __table_args__ = (Index("ix_audit_logs_user_created", "user_id", "created_at"),)


# ── MCP OAuth (lets external AI clients — Claude, ChatGPT, etc. — connect to a
# user's read-only financial data via a Model Context Protocol server) ─────────


class OAuthClientORM(Base):
    """A dynamically-registered MCP client (RFC 7591). Public clients only —
    no client_secret, since these are PKCE-only per OAuth 2.1."""

    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    redirect_uris: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class OAuthAuthorizationCodeORM(Base):
    """Short-lived, single-use authorization code. Consumed (deleted) on
    exchange; a background sweep can also drop expired rows."""

    __tablename__ = "oauth_authorization_codes"

    code: Mapped[str] = mapped_column(String(128), primary_key=True)
    client_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("oauth_clients.client_id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    redirect_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scope: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class OAuthAccessTokenORM(Base):
    """Stored as a SHA-256 hash — the plaintext token is only ever seen once,
    at issuance. `resource` binds the token to this server (RFC 8707) so a
    token minted here can't be replayed against a different resource server."""

    __tablename__ = "oauth_access_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    client_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("oauth_clients.client_id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    resource: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class OAuthRefreshTokenORM(Base):
    """Also stored hashed. Rotated on use — each refresh mints a new refresh
    token and revokes this one, so a stolen-then-replayed refresh token is
    detectable (both the old and new token being used is a signal to revoke
    the whole chain, though v1 only implements the rotation half)."""

    __tablename__ = "oauth_refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    access_token_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("oauth_access_tokens.id"), nullable=False
    )
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    resource: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class OAuthDeviceCodeORM(Base):
    """A pending device authorization (RFC 8628): a machine without a browser
    shows `user_code`, the person approves it on another device, and the
    machine, polling with `device_code`, then receives tokens. The device code
    is stored hashed, like every other token."""

    __tablename__ = "oauth_device_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    device_code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    client_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("oauth_clients.client_id"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    resource: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # pending → approved | denied; approved → consumed once tokens are issued.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','denied','consumed')",
            name="ck_oauth_device_codes_status",
        ),
    )


class PersonalAccessTokenORM(Base):
    """A long-lived token a person creates for scripts and CI (`salli_pat_…`).

    Stored as a SHA-256 hash; the plaintext is shown once, at creation. `prefix`
    is the first characters of the token, kept so a list can show which token
    is which without revealing it."""

    __tablename__ = "personal_access_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class CategorizationRuleORM(Base):
    """A user's rule for booking transactions that look a certain way (see
    domain/rules/engine.py). Conditions and actions are small JSON documents
    validated by the domain before they are stored."""

    __tablename__ = "categorization_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    match_all: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    conditions: Mapped[list] = mapped_column(JSONB, nullable=False)
    actions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # How often it has decided a transaction, for "which rules earn their keep".
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
