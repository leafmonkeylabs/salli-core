"""Holdings' look-through allocation.

Additive and safe on existing data: `holdings.allocation` (asset class →
share, summing to 1, as the person tags a fund) is NULL on every existing
holding, which then counts toward its own asset class as before.

Revision ID: core_0042_holding_allocation
Revises: core_0041_return_chain_head
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0042_holding_allocation"
down_revision: str | None = "core_0041_return_chain_head"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("holdings", sa.Column("allocation", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("holdings", "allocation")
