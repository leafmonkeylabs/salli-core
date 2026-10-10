"""Bank connections: links to people's banks through a provider, and their accounts.

Two new, empty tables; nothing existing changes.

Revision ID: core_0006_bank_connections
Revises: core_0005_statement_account
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0006_bank_connections"
down_revision: str | None = "core_0005_statement_account"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bank_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("credential_sealed", sa.Text(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_claimed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bank_connections_user_id", "bank_connections", ["user_id"], unique=False)
    op.create_table(
        "bank_connection_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("connection_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("remote_id", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("institution", sa.String(length=200), nullable=False),
        sa.Column("currency", sa.String(length=200), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=True),
        sa.Column("balance_minor", sa.BigInteger(), nullable=True),
        sa.Column("balance_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["connection_id"], ["bank_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connection_id", "remote_id", name="uq_bank_connection_accounts_remote"
        ),
    )
    op.create_index(
        "ix_bank_connection_accounts_user_id", "bank_connection_accounts", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_bank_connection_accounts_user_id", table_name="bank_connection_accounts")
    op.drop_table("bank_connection_accounts")
    op.drop_index("ix_bank_connections_user_id", table_name="bank_connections")
    op.drop_table("bank_connections")
