"""Investment policy statements, holdings' cost method and expense ratio, and
the risk questionnaire's horizon.

Additive and safe on existing data:

- `investment_policies` is a new, empty table: a user's investment policy
  statement (target allocation with bands, rebalancing rule, horizon,
  objectives, constraints, review date), one row a version, never updated.
- `holdings.cost_method` (fifo or average; NULL: the rule set's, else fifo)
  and `holdings.expense_ratio` (a yearly fraction, the user's own figure) are
  NULL on every existing holding, so nothing about one changes.
- `user_profiles.risk_horizon_years` keeps the questionnaire's horizon for
  the risk capacity measure; NULL until it is answered again.

Revision ID: core_0037_investment_policy
Revises: core_0032_account_freeze
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0037_investment_policy"
down_revision: str | None = "core_0032_account_freeze"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investment_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "version", name="uq_investment_policies_user_version"),
    )
    op.create_index(
        "ix_investment_policies_user_id", "investment_policies", ["user_id"], unique=False
    )
    op.add_column("holdings", sa.Column("cost_method", sa.String(length=16), nullable=True))
    op.add_column("holdings", sa.Column("expense_ratio", sa.Numeric(10, 6), nullable=True))
    op.create_check_constraint(
        "ck_holdings_cost_method", "holdings", "cost_method IN ('fifo', 'average')"
    )
    op.create_check_constraint(
        "ck_holdings_expense_ratio", "holdings", "expense_ratio >= 0 AND expense_ratio < 1"
    )
    op.add_column("user_profiles", sa.Column("risk_horizon_years", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "risk_horizon_years")
    op.drop_constraint("ck_holdings_expense_ratio", "holdings", type_="check")
    op.drop_constraint("ck_holdings_cost_method", "holdings", type_="check")
    op.drop_column("holdings", "expense_ratio")
    op.drop_column("holdings", "cost_method")
    op.drop_index("ix_investment_policies_user_id", table_name="investment_policies")
    op.drop_table("investment_policies")
