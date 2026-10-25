"""An agent's client_ref per MCP write, so a retried write is not made twice.

Additive: a new table, empty on an existing instance.

Revision ID: core_0044_mcp_client_refs
Revises: core_0043_invitations
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "core_0044_mcp_client_refs"
down_revision: str | None = "core_0043_invitations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_client_refs",
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("tool", sa.String(50), primary_key=True),
        sa.Column("client_ref", sa.String(180), primary_key=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("mcp_client_refs")
