"""Investments: a currency per holding, and each holding's transactions.

A holding was two figures the user typed, its cost basis and its current value,
in the base currency. It now also has a currency of its own and a history of
transactions (buys, sales, dividends, interest, splits, transfers in) from which
its lots, gains and value are worked out.

Additive and safe on existing data:

- `holdings.currency` is added and filled with each owner's base currency,
  which is what every existing holding's figures were always in, so nothing
  about an existing holding changes. (A holding whose owner has no profile
  cannot exist since core_0002 gave every data owner one; if one somehow did,
  it gets LKR, as core_0002 would have given its owner.)
- `holding_transactions` is a new, empty table. A holding without
  transactions keeps its declared figures, exactly as before.

Revision ID: core_0009_investments
Revises: core_0008_jurisdiction
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0009_investments"
down_revision: str | None = "core_0008_jurisdiction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("holdings", sa.Column("currency", sa.String(length=3), nullable=True))
    op.execute(
        "UPDATE holdings SET currency = COALESCE("
        " (SELECT p.base_currency FROM user_profiles p WHERE p.id = holdings.user_id), 'LKR')"
    )
    op.alter_column("holdings", "currency", nullable=False)
    op.create_check_constraint("ck_holdings_currency", "holdings", "currency ~ '^[A-Z]{3}$'")

    op.create_table(
        "holding_transactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("holding_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("price", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("fees_minor", sa.BigInteger(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("withholding_tax_minor", sa.BigInteger(), nullable=False),
        sa.Column("split_to", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("split_from", sa.Numeric(precision=38, scale=18), nullable=True),
        sa.Column("lots", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fx_rate", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("fx_rate_source", sa.String(length=50), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('buy','sell','dividend','interest','split','transfer_in')",
            name="ck_holding_transactions_kind",
        ),
        sa.CheckConstraint(
            "(kind IN ('buy','sell') AND quantity IS NOT NULL AND price IS NOT NULL)"
            " OR (kind = 'transfer_in' AND quantity IS NOT NULL AND amount_minor IS NOT NULL)"
            " OR (kind IN ('dividend','interest') AND amount_minor IS NOT NULL)"
            " OR (kind = 'split' AND split_to IS NOT NULL AND split_from IS NOT NULL)",
            name="ck_holding_transactions_fields",
        ),
        sa.CheckConstraint(
            "(quantity IS NULL OR quantity > 0) AND (price IS NULL OR price >= 0)"
            " AND fees_minor >= 0 AND withholding_tax_minor >= 0"
            " AND (amount_minor IS NULL OR amount_minor >= 0) AND fx_rate > 0"
            " AND (split_to IS NULL OR split_to > 0) AND (split_from IS NULL OR split_from > 0)",
            name="ck_holding_transactions_signs",
        ),
        sa.ForeignKeyConstraint(["holding_id"], ["holdings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_holding_transactions_user_id", "holding_transactions", ["user_id"], unique=False
    )
    op.create_index(
        "ix_holding_transactions_holding_date",
        "holding_transactions",
        ["holding_id", "transaction_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_holding_transactions_holding_date", table_name="holding_transactions")
    op.drop_index("ix_holding_transactions_user_id", table_name="holding_transactions")
    op.drop_table("holding_transactions")
    op.drop_constraint("ck_holdings_currency", "holdings", type_="check")
    op.drop_column("holdings", "currency")
