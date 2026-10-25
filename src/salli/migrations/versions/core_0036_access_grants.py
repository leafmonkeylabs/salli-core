"""Read-only access grants: one member lets another read their books.

A grant is live until either member revokes it; at most one live grant per
pair (a partial unique index), and never to oneself.

Revision ID: core_0036_access_grants
Revises: core_0032_account_freeze
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0036_access_grants"
down_revision: str | None = "core_0032_account_freeze"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "access_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("grantor_id", sa.String(64), nullable=False),
        sa.Column("grantee_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("grantor_id <> grantee_id", name="ck_access_grants_not_self"),
    )
    op.create_index("ix_access_grants_grantor_id", "access_grants", ["grantor_id"])
    op.create_index("ix_access_grants_grantee_id", "access_grants", ["grantee_id"])
    op.create_index(
        "uq_access_grants_live_pair",
        "access_grants",
        ["grantor_id", "grantee_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("access_grants")
