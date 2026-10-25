"""Capital-market assumptions as user data, and the FI plan.

`cma_packs` holds the `salli.cma/1` packs a user imports: a document is
never changed once written (a trigger refuses an UPDATE of its content, as
core_0010 does for tax rule versions), and at most one pack of a user's is
active. `user_profiles.fi_plan` holds their guaranteed income streams and
spending phases.

Revision ID: core_0039_cma_packs
Revises: core_0038_reconcile
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0039_cma_packs"
down_revision: str | None = "core_0038_reconcile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cma_packs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("version", sa.String(500), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "content_hash", name="uq_cma_packs_user_hash"),
    )
    op.create_index("ix_cma_packs_user_id", "cma_packs", ["user_id"])
    op.create_index(
        "uq_cma_packs_one_active",
        "cma_packs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION refuse_cma_pack_content_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.content IS DISTINCT FROM OLD.content
               OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
               OR NEW.user_id IS DISTINCT FROM OLD.user_id THEN
                RAISE EXCEPTION 'A capital-market assumptions pack never changes: import a new one';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_cma_packs_immutable
            BEFORE UPDATE ON cma_packs
            FOR EACH ROW
            EXECUTE FUNCTION refuse_cma_pack_content_change()
    """)
    op.add_column(
        "user_profiles",
        sa.Column(
            "fi_plan",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "fi_plan")
    op.execute("DROP TRIGGER IF EXISTS trg_cma_packs_immutable ON cma_packs")
    op.execute("DROP FUNCTION IF EXISTS refuse_cma_pack_content_change()")
    op.drop_table("cma_packs")
