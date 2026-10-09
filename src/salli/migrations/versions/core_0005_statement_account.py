"""Statements belong to an account: the bank or card account a statement is for.

One nullable column. Statements uploaded before it have no account, and
neither do imports that still don't name one.

Revision ID: core_0005_statement_account
Revises: core_0004_categorization_rules
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0005_statement_account"
down_revision: str | None = "core_0004_categorization_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("statements", sa.Column("account_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "statements_account_id_fkey", "statements", "accounts", ["account_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("statements_account_id_fkey", "statements", type_="foreignkey")
    op.drop_column("statements", "account_id")
