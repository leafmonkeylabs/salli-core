"""The decision lab's baseline: an asset account's role, and a debt's account.

Phase 1a of docs/design/decision-lab.md reconciles FI, insights, the cash
forecast and debt onto one model of a user's money. Two things it needs are
stored:

- `accounts.asset_role`: what an asset account holds, `cash`, `investment` or
  `other` (a home, a car). It replaces the pattern on account names that
  decided what counted as an investment. Every asset account has one, no
  other account does; existing asset accounts become `cash`, which is what
  the old pattern made of most of them. There are no real users yet, so no
  account is classified from its name.
- `debts.account_id`: the liability account in the ledger that holds a
  declared debt, so its balance is counted once (the account's) and its rate
  and minimum payment add the schedule. Nullable: a debt the ledger doesn't
  know counts as declared. At most one active debt per account.

Revision ID: core_0016_decision_baseline
Revises: core_0015_fi_assumptions
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0016_decision_baseline"
down_revision: str | None = "core_0015_fi_assumptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("asset_role", sa.String(length=20), nullable=True))
    op.execute("UPDATE accounts SET asset_role = 'cash' WHERE type = 'asset'")
    # Written so a NULL can't slip through: a CHECK passes when its expression
    # is NULL, and `NULL IN (...)` is.
    op.create_check_constraint(
        "ck_accounts_asset_role",
        "accounts",
        "(type = 'asset' AND asset_role IS NOT NULL"
        " AND asset_role IN ('cash','investment','other'))"
        " OR (type <> 'asset' AND asset_role IS NULL)",
    )

    op.add_column("debts", sa.Column("account_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("debts_account_id_fkey", "debts", "accounts", ["account_id"], ["id"])
    op.create_index(
        "uq_debts_active_account",
        "debts",
        ["user_id", "account_id"],
        unique=True,
        postgresql_where=sa.text("account_id IS NOT NULL AND is_active"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_debts_active_account",
        table_name="debts",
        postgresql_where=sa.text("account_id IS NOT NULL AND is_active"),
    )
    op.drop_constraint("debts_account_id_fkey", "debts", type_="foreignkey")
    op.drop_column("debts", "account_id")
    op.drop_constraint("ck_accounts_asset_role", "accounts", type_="check")
    op.drop_column("accounts", "asset_role")
