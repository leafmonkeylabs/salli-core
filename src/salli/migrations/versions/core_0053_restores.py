"""Restores: a full export restored into a person's empty books, with the
audit rows it carried from the server it came from, kept apart from this
server's chain. Under the same row-level security as the rest of a
person's data (core_0051).

`cma_packs.content_hash` widens to hold the hash it is given ("sha256:" and
64 hex digits): at 64 characters, no pack could be imported on Postgres.

Revision ID: core_0053_restores
Revises: core_0052_support_sessions
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0053_restores"
down_revision: str | None = "core_0052_support_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "cma_packs",
        "content_hash",
        type_=sa.String(length=80),
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )
    op.create_table(
        "restores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("export_hash", sa.String(length=80), nullable=False),
        sa.Column("export_version", sa.Integer(), nullable=False),
        sa.Column("source_user_id", sa.String(length=64), nullable=False),
        sa.Column("entries", sa.Integer(), nullable=False),
        sa.Column("source_chain_head", sa.String(length=80), nullable=True),
        sa.Column("chain_head", sa.String(length=80), nullable=True),
        sa.Column("audit_rows", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_restores_user_id"), "restores", ["user_id"], unique=False)
    op.execute("ALTER TABLE restores ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE restores FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY person_rows ON restores"
        " USING (salli_row_visible(user_id)) WITH CHECK (salli_row_visible(user_id))"
    )


def downgrade() -> None:
    op.drop_table("restores")
    op.alter_column(
        "cma_packs",
        "content_hash",
        type_=sa.String(length=64),
        existing_type=sa.String(length=80),
        existing_nullable=False,
    )
