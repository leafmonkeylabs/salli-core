"""
SQLAlchemy ORM models — the adapter layer only.
Domain models (Pydantic) live in domain/accounting/models.py.
These are the storage representations; mappers translate between them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
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
    # than inferred from `name`. The user's own tax rule sets declare which
    # roles exist, so the database checks only the shape of the code.
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
            "tax_role IS NULL OR tax_role ~ '^[a-z][a-z0-9_]*$'",
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

    __table_args__ = (
        Index("ix_parsed_transactions_statement_id", "statement_id"),
        # What every import searches its history by: the row's date.
        Index("ix_parsed_transactions_date", text("(extracted_json ->> 'date')")),
    )


# ── Tax computations ──────────────────────────────────────────────────────────


class TaxComputationORM(Base):
    """A user's tax for one jurisdiction and year, as Salli's engine computed it
    from the rule set version that was active (docs/taxrules.md).

    Reproducible: it records the version (and that version's content hash) and
    the inputs the engine was given (each role's total from the ledger, the
    answers, the exchange rates), so evaluating the same version with the same
    inputs gives the same lines again, whatever the rules or the ledger say
    since. Rows are only ever added: a recomputation is a new row.

    The amounts owed are money, so BIGINT minor units of the rule set's
    currency (`domain/currency.py`); every line is kept exactly, as a decimal
    string, in `lines`.
    """

    __tablename__ = "tax_computations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    region: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # What the rule set calls the year: "2031", "2031/32".
    year: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_set_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Owed after every credit: positive to pay, negative to be refunded.
    net_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_payable_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    refund_due_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Every line, in order: key, label, amount (a decimal string), expr,
    # source, refundable.
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    # What the engine was given: role totals (decimal strings) and how many
    # postings each came from, the answers, the base currency and the rates.
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        # The version is the user's own: a computation can't name another's.
        ForeignKeyConstraint(
            ["rule_set_version_id", "user_id"],
            ["tax_rule_set_versions.id", "tax_rule_set_versions.user_id"],
            name="fk_tax_computations_version",
        ),
        Index(
            "ix_tax_computations_user_jurisdiction_year",
            "user_id",
            "country",
            "year",
            "created_at",
        ),
        CheckConstraint("country ~ '^[A-Z]{2}$'", name="ck_tax_computations_country"),
        CheckConstraint(
            "tax_payable_minor >= 0 AND refund_due_minor >= 0"
            " AND net_minor = tax_payable_minor - refund_due_minor"
            " AND (tax_payable_minor = 0 OR refund_due_minor = 0)",
            name="ck_tax_computations_amounts",
        ),
        CheckConstraint("jsonb_typeof(lines) = 'array'", name="ck_tax_computations_lines"),
    )


# ── Tax rule sets (user data: docs/taxrules.md) ───────────────────────────────

#: A version's lifecycle (application/services/tax_rule_service.py).
RULE_SET_STATUSES = ("draft", "validated", "proposed", "active", "superseded", "invalid")


class TaxRuleSetORM(Base):
    """One jurisdiction's tax for one year, as a user (or their agent) wrote
    it: a named series of immutable versions, at most one of them active.

    One per user, country, region and year. `region` is part of that key even
    when NULL (a country-wide rule set), which a plain UNIQUE constraint would
    not enforce, so the key is an index over COALESCE(region, '') (a region is
    never empty). The active version must be one of this set's own: the
    composite foreign key says so, not just the service.
    """

    __tablename__ = "tax_rule_sets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    region: Mapped[str | None] = mapped_column(String(200), nullable=True)
    year_label: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        CheckConstraint("country ~ '^[A-Z]{2}$'", name="ck_tax_rule_sets_country"),
        CheckConstraint("region IS NULL OR region <> ''", name="ck_tax_rule_sets_region"),
        # What versions' composite foreign key points at.
        UniqueConstraint("id", "user_id", name="uq_tax_rule_sets_id_user"),
        Index(
            "uq_tax_rule_sets_jurisdiction_year",
            "user_id",
            "country",
            text("COALESCE(region, '')"),
            "year_label",
            unique=True,
        ),
        ForeignKeyConstraint(
            ["id", "active_version_id"],
            ["tax_rule_set_versions.rule_set_id", "tax_rule_set_versions.id"],
            name="fk_tax_rule_sets_active_version",
            use_alter=True,
        ),
    )


class TaxRuleSetVersionORM(Base):
    """One version of a rule set: the document, its validation report and its
    place in the lifecycle.

    `content` and `content_hash` never change once written: an edit is a new
    version. The repository has no way to update them, and a trigger
    (core_0010) refuses an UPDATE that would, as defence in depth. Status and
    its timestamps, and the stored report, do change as the version moves
    through its lifecycle.

    `user_id` is the set's owner, repeated so every query can filter on it
    directly; the composite foreign key keeps it equal to the set's.
    """

    __tablename__ = "tax_rule_set_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    rule_set_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # The document as it was submitted (parsed JSON; decimals are strings in it).
    content: Mapped[Any] = mapped_column(JSONB, nullable=False)
    # The rule set's content hash (docs/taxrules.md); NULL for a document that
    # doesn't match the schema, which has none.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    # The last validation: errors, warnings and each example's result.
    validation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    author_kind: Mapped[str] = mapped_column(String(10), nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["rule_set_id", "user_id"],
            ["tax_rule_sets.id", "tax_rule_sets.user_id"],
            name="fk_tax_rule_set_versions_rule_set",
            ondelete="CASCADE",
        ),
        UniqueConstraint("rule_set_id", "version", name="uq_tax_rule_set_versions_number"),
        # What the set's active-version foreign key points at.
        UniqueConstraint("rule_set_id", "id", name="uq_tax_rule_set_versions_set_id"),
        # What a computation's foreign key points at: a version and its owner.
        UniqueConstraint("id", "user_id", name="uq_tax_rule_set_versions_id_user"),
        # One active version per set, whatever a caller does.
        Index(
            "uq_tax_rule_set_versions_one_active",
            "rule_set_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        CheckConstraint("version > 0", name="ck_tax_rule_set_versions_version"),
        CheckConstraint(
            "status IN (" + ",".join(f"'{s}'" for s in RULE_SET_STATUSES) + ")",
            name="ck_tax_rule_set_versions_status",
        ),
        CheckConstraint(
            "author_kind IN ('user','agent')", name="ck_tax_rule_set_versions_author_kind"
        ),
        CheckConstraint(
            "(status <> 'active' OR activated_at IS NOT NULL)"
            " AND (status <> 'superseded' OR superseded_at IS NOT NULL)"
            " AND (status <> 'proposed' OR proposed_at IS NOT NULL)",
            name="ck_tax_rule_set_versions_timestamps",
        ),
    )


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

    # Which provider powers this user's AI: "anthropic", "openai" or
    # "chatgpt"; NULL is "auto" (LlmCredentialService documents its order).
    ai_provider: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # The user's own choice of model on the OpenAI routes, per provider and
    # tier: {"chatgpt": {"best": "...", "fast": "..."}, "openai": {...}}. NULL
    # or a missing tier means "let Salli pick from the account's models".
    ai_models: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Where the user is taxed: an ISO 3166-1 alpha-2 code, or NULL while they
    # have not said. It decides which of their tax rule sets compute their tax.
    tax_residency: Mapped[str | None] = mapped_column(String(2), nullable=True)
    # Their tax ids, [{"scheme": "XX-TIN", "value": "..."}, ...], one per scheme.
    tax_ids: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    # The user's own FI planning assumptions, each with where it comes from:
    # {"inflation": {"value": "0.03", "source": "...", "note": "...",
    # "set_at": "..."}, ...}, values as decimal strings. One that is missing
    # uses the FIRE strategy's figure, or a labelled placeholder
    # (domain/fi/assumptions.py).
    fi_assumptions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="ck_user_profiles_base_currency"),
        CheckConstraint(
            "tax_residency IS NULL OR tax_residency ~ '^[A-Z]{2}$'",
            name="ck_user_profiles_tax_residency",
        ),
        CheckConstraint("jsonb_typeof(tax_ids) = 'array'", name="ck_user_profiles_tax_ids"),
        CheckConstraint(
            "jsonb_typeof(fi_assumptions) = 'object'", name="ck_user_profiles_fi_assumptions"
        ),
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


class AiConnectionORM(Base):
    """A user's sign-in with an AI provider that pays from their own plan:
    today, ChatGPT (Sign in with ChatGPT plan usage).

    Everything a connection holds is sealed with the instance's key ring
    (AES-GCM, with `f"{user_id}|{provider}"` as associated data, exactly as a
    stored API key): the issued client id, the access token, the rotating
    refresh token, the ID token kept for the next sign-in's hint, the granted
    scopes, and the account's `sub` and email. The columns beside it are only
    what deciding needs without opening the seal.

    One per user and provider. A refresh replaces the sealed tokens under a
    row lock (SELECT ... FOR UPDATE), so two requests never spend one rotating
    refresh token twice.
    """

    __tablename__ = "ai_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # chatgpt
    sealed: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # active: usable. needs_sign_in: its renewal was refused, sign in again.
    # needs_consent: signed in, but plan use was not allowed. signed_out:
    # disconnected; only the account and its issued client id are kept, for
    # the next sign-in.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # Our own words for why it needs the user, never the provider's.
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # When the access token expires: whether to renew it, without opening the seal.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when the plan's usage limit for Salli was reached: new requests wait.
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_ai_connections_user_provider"),
    )


class InstanceSettingORM(Base):
    """A fact about this Salli instance as a whole, not about any user.

    Today one: `ext_agent_host_id`, the stable, opaque id OpenAI asks each
    host of an app to send when signing in to use a ChatGPT plan. Generated
    once (`urn:uuid:` and a UUIDv4) and kept for the instance's lifetime. It is
    an identifier, not a credential, and identifies no one.
    """

    __tablename__ = "instance_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


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
    """An investment holding. Its cost basis and value come from its
    transactions (holding_transactions) once it has any; until then, from the
    two figures the user declared here, in the base currency."""

    __tablename__ = "holdings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(40), nullable=False)
    # ISO 4217: what it trades in, its transactions' money and its prices.
    # Not necessarily the owner's base currency (a US fund in a rupee ledger).
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Declared, in the base currency; ignored once there are transactions.
    cost_basis_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_value_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        Index("ix_holdings_user_active", "user_id", "is_active"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_holdings_currency"),
    )


class HoldingTransactionORM(Base):
    """One event in a holding's history: a buy, sale, dividend, interest
    payment, split, or transfer in (see domain/portfolio/lots.py).

    Money (fees, an income amount, a transfer's cost) is BIGINT minor units of
    the holding's currency, like every amount Salli stores. Quantities, unit
    prices, split ratios and the exchange rate are NUMERIC(38, 18): exact
    decimals, never floats, with the 18 places ether's wei needs and 20
    integer digits. The domain refuses more places than that before a value
    gets here, so the column never rounds, and a value too large for it is a
    database error rather than a silent truncation. A unit price is not
    money in minor units: a fund's NAV or a token's price has more places
    than its currency.
    """

    __tablename__ = "holding_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    holding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("holdings.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    fees_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Gross income (dividend, interest), or a transfer's total cost.
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    withholding_tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # A split turns `split_from` units into `split_to` (2-for-1 is 2 and 1).
    split_to: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    split_from: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    # A sale's named lots, [{"lot_id": …, "quantity": "1.5"}]; empty is FIFO.
    # Quantities are decimal strings: a JSON number is a float to most readers.
    lots: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # Base currency per unit of the holding's, on the transaction's date: the
    # one given, or the published one (see application/fx.py).
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=1)
    fx_rate_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('buy','sell','dividend','interest','split','transfer_in')",
            name="ck_holding_transactions_kind",
        ),
        # What each kind cannot do without; the domain checks the rest.
        CheckConstraint(
            "(kind IN ('buy','sell') AND quantity IS NOT NULL AND price IS NOT NULL)"
            " OR (kind = 'transfer_in' AND quantity IS NOT NULL AND amount_minor IS NOT NULL)"
            " OR (kind IN ('dividend','interest') AND amount_minor IS NOT NULL)"
            " OR (kind = 'split' AND split_to IS NOT NULL AND split_from IS NOT NULL)",
            name="ck_holding_transactions_fields",
        ),
        CheckConstraint(
            "(quantity IS NULL OR quantity > 0) AND (price IS NULL OR price >= 0)"
            " AND fees_minor >= 0 AND withholding_tax_minor >= 0"
            " AND (amount_minor IS NULL OR amount_minor >= 0) AND fx_rate > 0"
            " AND (split_to IS NULL OR split_to > 0) AND (split_from IS NULL OR split_from > 0)",
            name="ck_holding_transactions_signs",
        ),
        Index("ix_holding_transactions_holding_date", "holding_id", "transaction_date"),
    )


class HoldingPriceORM(Base):
    """A closing price for a symbol on a day, as the user recorded it (or a
    provider gave it, when the user asked for a refresh). One per user,
    symbol, currency and day: recording another replaces it. The price is as quoted that day,
    not adjusted for later splits (the domain adjusts), and like a
    transaction's unit price it is an exact NUMERIC(38, 18), not money in
    minor units."""

    __tablename__ = "holding_prices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Upper case; a holding's symbol matches it whatever case it was typed in.
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # "user", or the provider's name.
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        # One close a day per symbol and currency: a symbol held in two
        # currencies (a fund listed in USD and in EUR) has a price in each.
        UniqueConstraint(
            "user_id",
            "symbol",
            "currency",
            "price_date",
            name="uq_holding_prices_user_symbol_currency_date",
        ),
        CheckConstraint("close > 0", name="ck_holding_prices_close"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_holding_prices_currency"),
    )


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
    """An OAuth client: one that registered itself (RFC 7591), or one of
    Salli's own. Public clients only — no client_secret, since these are
    PKCE-only per OAuth 2.1."""

    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    redirect_uris: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Salli's own client (the `salli` CLI, seeded by core_0011), as opposed to
    # one that registered itself and may call itself anything. Only a first
    # party client's API tokens carry permissions like `tax:activate`
    # (application/permissions.py). Registration never sets it.
    first_party: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
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
    is which without revealing it. `permissions` is what the token may do
    beyond reading and writing the user's data (application/permissions.py):
    none unless the user asked for them when they made it."""

    __tablename__ = "personal_access_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    permissions: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(permissions) = 'array'",
            name="ck_personal_access_tokens_permissions",
        ),
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


class BankConnectionORM(Base):
    """A link to a user's bank through a provider (SimpleFIN, …).

    The credential the provider issued is sealed with the instance's key ring
    (AES-GCM, bound to this user and row), exactly like a stored LLM key:
    whoever reads the database alone cannot use it."""

    __tablename__ = "bank_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    credential_sealed: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # active: syncs. error: the last sync failed (last_error says why).
    # attention: it synced, but the institution reported a problem or an
    # account could not be imported (warnings, last_error).
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What the provider asked to show the user at the last sync.
    warnings: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When a sync last started, successful or not: the scheduler backs off
    # from it.
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # A sync running now holds the connection until then, so a second one
    # (an overlapping cron run, a double click) can't fetch it again.
    sync_claimed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    accounts: Mapped[list[BankConnectionAccountORM]] = relationship(
        "BankConnectionAccountORM", cascade="all, delete-orphan", lazy="selectin"
    )


class BankConnectionAccountORM(Base):
    """One account at the bank, and the Salli account it feeds (once mapped)."""

    __tablename__ = "bank_connection_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    connection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bank_connections.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    remote_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    institution: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(200), nullable=False)
    account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    # The bank's balance at its last sync, for reconciling against the ledger.
    balance_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    balance_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When its transactions were last imported in full: the next sync fetches
    # from a little before. Null until its first import (a newly mapped
    # account gets the first sync's window).
    last_imported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Why its last import failed, if it did.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint("connection_id", "remote_id", name="uq_bank_connection_accounts_remote"),
    )
