"""A holding's account: the investment account in the ledger that holds it.

Phase 3b of the decision lab (docs/design/decision-lab-phase-3.md, section 2,
decision 17): a scenario may sell part of a holding, and the sale's value
must come out of something the baseline counts. The ledger stays the only
source of balances; `holdings.account_id` says which of the owner's
investment-role asset accounts a holding sits in. Nullable: a holding no
account holds can still be invested into, but not sold in a scenario.

The service checks that the account is the owner's own asset account with
the `investment` role (`PortfolioService.update_holding`); the database,
that it exists. An account may hold many holdings (a brokerage holds
several).

Revision ID: core_0020_holding_account
Revises: core_0019_notifications
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0020_holding_account"
down_revision: str | None = "core_0019_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("holdings", sa.Column("account_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "holdings_account_id_fkey", "holdings", "accounts", ["account_id"], ["id"]
    )
    op.create_index("ix_holdings_account", "holdings", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_holdings_account", table_name="holdings")
    op.drop_constraint("holdings_account_id_fkey", "holdings", type_="foreignkey")
    op.drop_column("holdings", "account_id")
