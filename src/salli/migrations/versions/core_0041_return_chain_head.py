"""A return version keeps the ledger's chain head when it was recorded.

Additive and safe on existing data: `tax_returns.chain_head_hash` is the hash
of the user's last journal entry when the version was recorded, so the
ledger a filing was made from can be checked against its hash chain later.
NULL on every existing version and for a user with no entries.

Revision ID: core_0041_return_chain_head
Revises: core_0040_investment_policy
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0041_return_chain_head"
down_revision: str | None = "core_0040_investment_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tax_returns", sa.Column("chain_head_hash", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("tax_returns", "chain_head_hash")
