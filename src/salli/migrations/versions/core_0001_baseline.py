"""Salli's schema, as of the split from the hosted service.

Squashes the 28 revisions that built it (initial_schema through
add_credit_purchases_and_preferred_model), minus the hosted service's tables,
which now belong to that service's own history. A fresh database gets exactly
this; the hosted production database, which already has it, is stamped here
rather than replayed.

Generated from the schema those 28 revisions actually produce, not from the
ORM, so column order, server defaults and constraint names match a database
built the old way byte for byte.

Revision ID: core_0001_baseline
Revises:
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision: str = "core_0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("code", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column("type", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("currency", sa.VARCHAR(length=3), autoincrement=False, nullable=False),
        sa.Column("parent_id", sa.VARCHAR(length=36), autoincrement=False, nullable=True),
        sa.Column("is_active", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column("tax_role", sa.VARCHAR(length=30), autoincrement=False, nullable=True),
        sa.CheckConstraint(
            "tax_role IS NULL OR tax_role IN ('apit_credit','ait_credit','foreign_tax_credit','qualifying_payment','fsi_income')",
            name="ck_accounts_tax_role",
        ),
        sa.CheckConstraint(
            "type IN ('asset','liability','equity','income','expense')", name="ck_accounts_type"
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["accounts.id"], name="accounts_parent_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="accounts_pkey"),
        sa.UniqueConstraint(
            "user_id",
            "code",
            name="uq_accounts_user_code",
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
        postgresql_ignore_search_path=False,
    )
    op.create_index(
        "ix_accounts_user_id", "accounts", ["user_id"], unique=False, postgresql_include=[]
    )
    op.create_table(
        "advisory_reports",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("trigger", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("fi_score_id", sa.VARCHAR(length=36), autoincrement=False, nullable=True),
        sa.Column("summary", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column(
            "recommendations",
            postgresql.JSONB(astext_type=Text()),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="advisory_reports_pkey"),
    )
    op.create_index(
        "ix_advisory_reports_user_date",
        "advisory_reports",
        ["user_id", "created_at"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_advisory_reports_user_id",
        "advisory_reports",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "agent_documents",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("title", sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column("content", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column("storage_key", sa.VARCHAR(length=500), autoincrement=False, nullable=True),
        sa.Column("mime_type", sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column(
            "tags", postgresql.JSONB(astext_type=Text()), autoincrement=False, nullable=False
        ),
        sa.Column("source", sa.VARCHAR(length=30), autoincrement=False, nullable=False),
        sa.Column("namespace", sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column("slug", sa.VARCHAR(length=200), autoincrement=False, nullable=True),
        sa.Column("description", sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="agent_documents_pkey"),
        sa.UniqueConstraint(
            "user_id",
            "namespace",
            "slug",
            name="uq_agent_docs_user_ns_slug",
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(
        "ix_agent_documents_namespace",
        "agent_documents",
        ["user_id", "namespace"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_agent_documents_user_id",
        "agent_documents",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("thread_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("title", sa.VARCHAR(length=200), autoincrement=False, nullable=True),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "last_active_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "persona",
            sa.VARCHAR(length=20),
            server_default=sa.text("'scrooge'::character varying"),
            autoincrement=False,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="agent_sessions_pkey"),
        sa.UniqueConstraint(
            "user_id",
            "thread_id",
            name="uq_agent_sessions_user_thread",
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(
        "ix_agent_sessions_user_active",
        "agent_sessions",
        ["user_id", "last_active_at"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("action", sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column(
            "params", postgresql.JSONB(astext_type=Text()), autoincrement=False, nullable=False
        ),
        sa.Column("decision", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="audit_logs_pkey"),
    )
    op.create_index(
        "ix_audit_logs_user_created",
        "audit_logs",
        ["user_id", "created_at"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_audit_logs_user_id", "audit_logs", ["user_id"], unique=False, postgresql_include=[]
    )
    op.create_table(
        "budgets",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("period_start", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column("period_end", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column(
            "lines", postgresql.JSONB(astext_type=Text()), autoincrement=False, nullable=False
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="budgets_pkey"),
    )
    op.create_index(
        "ix_budgets_user_id", "budgets", ["user_id"], unique=False, postgresql_include=[]
    )
    op.create_index(
        "ix_budgets_user_period",
        "budgets",
        ["user_id", "period_start"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "debts",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column("principal_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("apr", sa.NUMERIC(precision=6, scale=4), autoincrement=False, nullable=False),
        sa.Column("minimum_payment_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("is_active", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="debts_pkey"),
    )
    op.create_index(
        "ix_debts_user_active",
        "debts",
        ["user_id", "is_active"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index("ix_debts_user_id", "debts", ["user_id"], unique=False, postgresql_include=[])
    op.create_table(
        "documents",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("kind", sa.VARCHAR(length=50), autoincrement=False, nullable=False),
        sa.Column("storage_key", sa.VARCHAR(length=500), autoincrement=False, nullable=False),
        sa.Column("year", sa.VARCHAR(length=10), autoincrement=False, nullable=True),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="documents_pkey"),
    )
    op.create_index(
        "ix_documents_user_id", "documents", ["user_id"], unique=False, postgresql_include=[]
    )
    op.create_table(
        "fi_goals",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column("kind", sa.VARCHAR(length=40), autoincrement=False, nullable=False),
        sa.Column("target_amount_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("current_amount_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("target_date", sa.VARCHAR(length=10), autoincrement=False, nullable=True),
        sa.Column("priority", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("is_active", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column(
            "extra", postgresql.JSONB(astext_type=Text()), autoincrement=False, nullable=False
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="fi_goals_pkey"),
    )
    op.create_index(
        "ix_fi_goals_user_active",
        "fi_goals",
        ["user_id", "is_active"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_fi_goals_user_id", "fi_goals", ["user_id"], unique=False, postgresql_include=[]
    )
    op.create_table(
        "fi_scores",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("score", sa.NUMERIC(precision=5, scale=2), autoincrement=False, nullable=False),
        sa.Column("pack_version", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("inputs_hash", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column(
            "result_json", postgresql.JSONB(astext_type=Text()), autoincrement=False, nullable=False
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="fi_scores_pkey"),
    )
    op.create_index(
        "ix_fi_scores_user_date",
        "fi_scores",
        ["user_id", "created_at"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_fi_scores_user_id", "fi_scores", ["user_id"], unique=False, postgresql_include=[]
    )
    op.create_table(
        "fire_strategies",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("version", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "strategy", postgresql.JSONB(astext_type=Text()), autoincrement=False, nullable=False
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="fire_strategies_pkey"),
    )
    op.create_index(
        "ix_fire_strategies_user_id",
        "fire_strategies",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_fire_strategies_user_version",
        "fire_strategies",
        ["user_id", "version"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "holdings",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("symbol", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column("asset_class", sa.VARCHAR(length=40), autoincrement=False, nullable=False),
        sa.Column("cost_basis_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("current_value_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("is_active", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="holdings_pkey"),
    )
    op.create_index(
        "ix_holdings_user_active",
        "holdings",
        ["user_id", "is_active"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_holdings_user_id", "holdings", ["user_id"], unique=False, postgresql_include=[]
    )
    op.create_table(
        "insurance_targets",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("policy_type", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("target_amount_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="insurance_targets_pkey"),
        sa.UniqueConstraint(
            "user_id",
            "policy_type",
            name="uq_insurance_targets_user_type",
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(
        "ix_insurance_targets_user_id",
        "insurance_targets",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("entry_date", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column("description", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("source", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("external_ref", sa.VARCHAR(length=200), autoincrement=False, nullable=True),
        sa.Column("reversed_by", sa.VARCHAR(length=36), autoincrement=False, nullable=True),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.CheckConstraint(
            "source IN ('manual','statement','sms','system')", name="ck_journal_entries_source"
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by"], ["journal_entries.id"], name="journal_entries_reversed_by_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="journal_entries_pkey"),
    )
    op.create_index(
        "ix_journal_entries_user_date",
        "journal_entries",
        ["user_id", "entry_date"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_journal_entries_user_id",
        "journal_entries",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "oauth_clients",
        sa.Column("client_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("client_name", sa.VARCHAR(length=200), autoincrement=False, nullable=True),
        sa.Column(
            "redirect_uris",
            postgresql.JSONB(astext_type=Text()),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("client_id", name="oauth_clients_pkey"),
    )
    op.create_table(
        "policies",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column("policy_type", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("provider", sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column("coverage_amount_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("premium_amount_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("premium_frequency", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("expiry_date", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column("is_active", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="policies_pkey"),
    )
    op.create_index(
        "ix_policies_user_active",
        "policies",
        ["user_id", "is_active"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_policies_user_id", "policies", ["user_id"], unique=False, postgresql_include=[]
    )
    op.create_table(
        "reminders",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("due_date", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column("kind", sa.VARCHAR(length=500), autoincrement=False, nullable=False),
        sa.Column("status", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column("alert_type", sa.VARCHAR(length=40), autoincrement=False, nullable=True),
        sa.Column("source_domain", sa.VARCHAR(length=40), autoincrement=False, nullable=True),
        sa.Column("source_id", sa.VARCHAR(length=200), autoincrement=False, nullable=True),
        sa.Column("severity", sa.VARCHAR(length=20), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint("id", name="reminders_pkey"),
    )
    op.create_index(
        "ix_reminders_user_alert_source",
        "reminders",
        ["user_id", "source_domain", "source_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_reminders_user_id", "reminders", ["user_id"], unique=False, postgresql_include=[]
    )
    op.create_table(
        "statements",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("storage_key", sa.VARCHAR(length=500), autoincrement=False, nullable=False),
        sa.Column("bank", sa.VARCHAR(length=100), autoincrement=False, nullable=True),
        sa.Column("period_start", sa.VARCHAR(length=10), autoincrement=False, nullable=True),
        sa.Column("period_end", sa.VARCHAR(length=10), autoincrement=False, nullable=True),
        sa.Column("status", sa.VARCHAR(length=30), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="statements_pkey"),
        postgresql_ignore_search_path=False,
    )
    op.create_index(
        "ix_statements_user_id", "statements", ["user_id"], unique=False, postgresql_include=[]
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("slug", sa.VARCHAR(length=60), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=120), autoincrement=False, nullable=False),
        sa.Column("kind", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column(
            "color",
            sa.VARCHAR(length=20),
            server_default=sa.text("''::character varying"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "is_system",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('category','need')", name="ck_tags_kind"),
        sa.PrimaryKeyConstraint("id", name="tags_pkey"),
        sa.UniqueConstraint(
            "user_id",
            "kind",
            "slug",
            name="uq_tags_user_kind_slug",
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
        postgresql_ignore_search_path=False,
    )
    op.create_index("ix_tags_user_id", "tags", ["user_id"], unique=False, postgresql_include=[])
    op.create_table(
        "tax_computations",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("year", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column("pack_version", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("inputs_hash", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column(
            "result_json", postgresql.JSONB(astext_type=Text()), autoincrement=False, nullable=False
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="tax_computations_pkey"),
    )
    op.create_index(
        "ix_tax_computations_user_id",
        "tax_computations",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_tax_computations_user_year",
        "tax_computations",
        ["user_id", "year"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "user_llm_credentials",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("provider", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("ciphertext", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("key_version", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("last4", sa.VARCHAR(length=4), autoincrement=False, nullable=False),
        sa.Column(
            "validated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="user_llm_credentials_pkey"),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            name="uq_llm_cred_user_provider",
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(
        "ix_user_llm_credentials_user_id",
        "user_llm_credentials",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("email", sa.VARCHAR(length=320), autoincrement=False, nullable=True),
        sa.Column("display_name", sa.VARCHAR(length=200), autoincrement=False, nullable=True),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column("date_of_birth", sa.DATE(), autoincrement=False, nullable=True),
        sa.Column("dependents_count", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("employment_status", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column("residency_status", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column("employer", sa.VARCHAR(length=200), autoincrement=False, nullable=True),
        sa.Column("employment_type", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column("ird_number", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column("risk_score", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column("risk_category", sa.VARCHAR(length=16), autoincrement=False, nullable=True),
        sa.Column("life_stage", sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column("mcp_enabled", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column("daily_briefing_enabled", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column("preferred_model", sa.VARCHAR(length=40), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint("id", name="user_profiles_pkey"),
    )
    op.create_table(
        "goal_allocations",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("goal_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("account_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column(
            "allocated_minor",
            sa.BIGINT(),
            server_default=sa.text("'0'::bigint"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.CheckConstraint("allocated_minor >= 0", name="ck_goal_allocations_non_negative"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="goal_allocations_account_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["goal_id"], ["fi_goals.id"], name="goal_allocations_goal_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="goal_allocations_pkey"),
        sa.UniqueConstraint(
            "goal_id",
            "account_id",
            name="uq_goal_allocations_goal_account",
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(
        "ix_goal_allocations_goal",
        "goal_allocations",
        ["goal_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_goal_allocations_user_id",
        "goal_allocations",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "oauth_access_tokens",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("token_hash", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("client_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("scope", sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column("resource", sa.VARCHAR(length=500), autoincrement=False, nullable=True),
        sa.Column(
            "expires_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "revoked_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["client_id"], ["oauth_clients.client_id"], name="oauth_access_tokens_client_id_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="oauth_access_tokens_pkey"),
    )
    op.create_index(
        "ix_oauth_access_tokens_token_hash",
        "oauth_access_tokens",
        ["token_hash"],
        unique=True,
        postgresql_include=[],
    )
    op.create_index(
        "ix_oauth_access_tokens_user_id",
        "oauth_access_tokens",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "oauth_authorization_codes",
        sa.Column("code", sa.VARCHAR(length=128), autoincrement=False, nullable=False),
        sa.Column("client_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("redirect_uri", sa.VARCHAR(length=500), autoincrement=False, nullable=False),
        sa.Column("code_challenge", sa.VARCHAR(length=128), autoincrement=False, nullable=False),
        sa.Column("resource", sa.VARCHAR(length=500), autoincrement=False, nullable=True),
        sa.Column("scope", sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column(
            "expires_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["oauth_clients.client_id"],
            name="oauth_authorization_codes_client_id_fkey",
        ),
        sa.PrimaryKeyConstraint("code", name="oauth_authorization_codes_pkey"),
    )
    op.create_index(
        "ix_oauth_authorization_codes_user_id",
        "oauth_authorization_codes",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "parsed_transactions",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("statement_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("raw", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column(
            "extracted_json",
            postgresql.JSONB(astext_type=Text()),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "confidence", sa.NUMERIC(precision=4, scale=3), autoincrement=False, nullable=True
        ),
        sa.Column("dedup_key", sa.VARCHAR(length=64), autoincrement=False, nullable=True),
        sa.Column("dedup_status", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("posted_entry_id", sa.VARCHAR(length=36), autoincrement=False, nullable=True),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["posted_entry_id"],
            ["journal_entries.id"],
            name="parsed_transactions_posted_entry_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"],
            ["statements.id"],
            name="parsed_transactions_statement_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="parsed_transactions_pkey"),
    )
    op.create_index(
        "ix_parsed_transactions_dedup_key",
        "parsed_transactions",
        ["dedup_key"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "postings",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("entry_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("account_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("direction", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("amount_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("currency", sa.VARCHAR(length=3), autoincrement=False, nullable=False),
        sa.Column(
            "fx_rate", sa.NUMERIC(precision=20, scale=8), autoincrement=False, nullable=False
        ),
        sa.Column("fx_rate_source", sa.VARCHAR(length=50), autoincrement=False, nullable=True),
        sa.Column("base_amount_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.CheckConstraint(
            "direction = ANY (ARRAY[1, '-1'::integer])", name="ck_postings_direction"
        ),
        sa.CheckConstraint("amount_minor > 0", name="ck_postings_amount_positive"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="postings_account_id_fkey"),
        sa.ForeignKeyConstraint(
            ["entry_id"], ["journal_entries.id"], name="postings_entry_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="postings_pkey"),
    )
    op.create_index(
        "ix_postings_account", "postings", ["account_id"], unique=False, postgresql_include=[]
    )
    op.create_index(
        "ix_postings_entry", "postings", ["entry_id"], unique=False, postgresql_include=[]
    )
    op.create_table(
        "recurring_subscriptions",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column("amount_minor", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("frequency", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("next_due_date", sa.VARCHAR(length=10), autoincrement=False, nullable=False),
        sa.Column("account_id", sa.VARCHAR(length=36), autoincrement=False, nullable=True),
        sa.Column("grace_days", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "amount_tolerance_pct",
            sa.NUMERIC(precision=5, scale=4),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("is_active", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="recurring_subscriptions_account_id_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="recurring_subscriptions_pkey"),
    )
    op.create_index(
        "ix_recurring_subscriptions_user_active",
        "recurring_subscriptions",
        ["user_id", "is_active"],
        unique=False,
        postgresql_include=[],
    )
    op.create_index(
        "ix_recurring_subscriptions_user_id",
        "recurring_subscriptions",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("token_hash", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("access_token_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("client_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=64), autoincrement=False, nullable=False),
        sa.Column("scope", sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column("resource", sa.VARCHAR(length=500), autoincrement=False, nullable=True),
        sa.Column(
            "expires_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "revoked_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["access_token_id"],
            ["oauth_access_tokens.id"],
            name="oauth_refresh_tokens_access_token_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="oauth_refresh_tokens_pkey"),
    )
    op.create_index(
        "ix_oauth_refresh_tokens_token_hash",
        "oauth_refresh_tokens",
        ["token_hash"],
        unique=True,
        postgresql_include=[],
    )
    op.create_index(
        "ix_oauth_refresh_tokens_user_id",
        "oauth_refresh_tokens",
        ["user_id"],
        unique=False,
        postgresql_include=[],
    )
    op.create_table(
        "posting_tags",
        sa.Column("posting_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.Column("kind", sa.VARCHAR(length=20), autoincrement=False, nullable=False),
        sa.Column("tag_id", sa.VARCHAR(length=36), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["posting_id"], ["postings.id"], name="posting_tags_posting_id_fkey", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name="posting_tags_tag_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("posting_id", "kind", name="posting_tags_pkey"),
    )
    op.create_index(
        "ix_posting_tags_tag", "posting_tags", ["tag_id"], unique=False, postgresql_include=[]
    )

    # Double-entry balance constraint: sum(direction * base_amount_minor) per
    # entry = 0, checked at commit. Autogenerate cannot see triggers.
    # asyncpg requires each statement in its own execute() call.
    op.execute("""
        CREATE OR REPLACE FUNCTION check_entry_balance()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE net BIGINT;
        BEGIN
            SELECT COALESCE(SUM(direction * base_amount_minor), 0)
              INTO net
              FROM postings
             WHERE entry_id = COALESCE(NEW.entry_id, OLD.entry_id);
            IF net <> 0 THEN
                RAISE EXCEPTION 'Unbalanced journal entry %: net = %',
                    COALESCE(NEW.entry_id, OLD.entry_id), net;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_posting_balance
            AFTER INSERT OR UPDATE OR DELETE ON postings
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION check_entry_balance()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_posting_balance ON postings")
    op.execute("DROP FUNCTION IF EXISTS check_entry_balance()")
    op.drop_table("posting_tags")
    op.drop_table("oauth_refresh_tokens")
    op.drop_table("recurring_subscriptions")
    op.drop_table("postings")
    op.drop_table("parsed_transactions")
    op.drop_table("oauth_authorization_codes")
    op.drop_table("oauth_access_tokens")
    op.drop_table("goal_allocations")
    op.drop_table("user_profiles")
    op.drop_table("user_llm_credentials")
    op.drop_table("tax_computations")
    op.drop_table("tags")
    op.drop_table("statements")
    op.drop_table("reminders")
    op.drop_table("policies")
    op.drop_table("oauth_clients")
    op.drop_table("journal_entries")
    op.drop_table("insurance_targets")
    op.drop_table("holdings")
    op.drop_table("fire_strategies")
    op.drop_table("fi_scores")
    op.drop_table("fi_goals")
    op.drop_table("documents")
    op.drop_table("debts")
    op.drop_table("budgets")
    op.drop_table("audit_logs")
    op.drop_table("agent_sessions")
    op.drop_table("agent_documents")
    op.drop_table("advisory_reports")
    op.drop_table("accounts")
