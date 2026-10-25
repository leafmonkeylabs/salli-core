"""A return filed on provisional values keeps the filer's acknowledgement.

Additive and safe on existing data: `tax_returns.provisional_note` is what
the filer said when they filed (or amended) a return whose computation used
values its rules mark provisional; the values themselves are in the
version's snapshot. NULL on every existing version.

Revision ID: core_0043_return_provisional
Revises: core_0042_holding_allocation
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0043_return_provisional"
down_revision: str | None = "core_0042_holding_allocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tax_returns", sa.Column("provisional_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tax_returns", "provisional_note")
