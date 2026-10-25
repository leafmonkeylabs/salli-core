"""Owners' invitations to join (`salli-server members invite`).

Additive: a new table, empty on an existing instance.

Revision ID: core_0043_invitations
Revises: core_0042_holding_allocation
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0043_invitations"
down_revision: str | None = "core_0042_holding_allocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("invitations")
