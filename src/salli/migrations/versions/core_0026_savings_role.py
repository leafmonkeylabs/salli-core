"""Savings: an asset role for cash you keep, not spend.

`accounts.asset_role` may be `savings` (a savings account, an emergency fund, a
term deposit): counted as cash in net worth, FI and the emergency fund, never
in the daily cash forecast or what is free to spend. No account changes role.

Revision ID: core_0026_savings_role
Revises: core_0025_books_lock
Create Date: 2026-10-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "core_0026_savings_role"
down_revision: str | None = "core_0025_books_lock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _check(roles: str) -> None:
    op.drop_constraint("ck_accounts_asset_role", "accounts", type_="check")
    op.create_check_constraint(
        "ck_accounts_asset_role",
        "accounts",
        "(type = 'asset' AND asset_role IS NOT NULL"
        f" AND asset_role IN ({roles}))"
        " OR (type <> 'asset' AND asset_role IS NULL)",
    )


def upgrade() -> None:
    _check("'cash','savings','investment','other'")


def downgrade() -> None:
    # A savings account was cash before there was a role for it.
    op.execute("UPDATE accounts SET asset_role = 'cash' WHERE asset_role = 'savings'")
    _check("'cash','investment','other'")
