"""AI connections: a user's sign-in with a provider that pays from their own plan (ChatGPT).

Two new tables: `ai_connections`, one sealed sign-in per user and provider;
and `instance_settings`, facts about the instance itself (its ChatGPT host
id, generated on first use). And two nullable columns on `user_profiles`:
which provider powers a user's AI (NULL is "auto"), and their own choice of
model per provider. Nothing existing changes.

Revision ID: core_0007_ai_connections
Revises: core_0006_bank_connections
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0007_ai_connections"
down_revision: str | None = "core_0006_bank_connections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("sealed", sa.Text(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("status_detail", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_ai_connections_user_provider"),
    )
    op.create_index("ix_ai_connections_user_id", "ai_connections", ["user_id"], unique=False)
    op.create_table(
        "instance_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.add_column("user_profiles", sa.Column("ai_provider", sa.String(length=16), nullable=True))
    op.add_column(
        "user_profiles",
        sa.Column("ai_models", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "ai_models")
    op.drop_column("user_profiles", "ai_provider")
    op.drop_table("instance_settings")
    op.drop_index("ix_ai_connections_user_id", table_name="ai_connections")
    op.drop_table("ai_connections")
