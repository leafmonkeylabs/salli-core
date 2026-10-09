"""Statements belong to an account: the bank or card account a statement is for.

One nullable column. Statements uploaded before it have no account, and
neither do imports that still don't name one.

And the two indexes every import's duplicate check needs: parsed
transactions by statement (the join to their statement and its account) and
by the date in their JSON (the window of history searched). Without them each
import scanned the whole table, across all users.

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
    op.create_index("ix_parsed_transactions_statement_id", "parsed_transactions", ["statement_id"])
    op.create_index(
        "ix_parsed_transactions_date",
        "parsed_transactions",
        [sa.text("(extracted_json ->> 'date')")],
    )


def downgrade() -> None:
    op.drop_index("ix_parsed_transactions_date", table_name="parsed_transactions")
    op.drop_index("ix_parsed_transactions_statement_id", table_name="parsed_transactions")
    op.drop_constraint("statements_account_id_fkey", "statements", type_="foreignkey")
    op.drop_column("statements", "account_id")
