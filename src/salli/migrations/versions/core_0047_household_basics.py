"""Household basics: recategorised entries, the monthly budget, push devices.

Additive: a source the entries' check allows, a profile column (empty list)
and a new table, empty on an existing instance.

Revision ID: core_0047_household_basics
Revises: core_0046_audit_chain
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0047_household_basics"
down_revision: str | None = "core_0046_audit_chain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCES = "'manual','statement','sms','system','reversal','year_end_close'"


def upgrade() -> None:
    op.drop_constraint("ck_journal_entries_source", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_entries_source", "journal_entries", f"source IN ({_SOURCES},'recategorise')"
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "monthly_budget",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_table(
        "push_devices",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=True),
        sa.Column("platform", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("platform in ('ios', 'android')", name="ck_push_devices_platform"),
    )
    op.create_index("ix_push_devices_user_id", "push_devices", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_push_devices_user_id", table_name="push_devices")
    op.drop_table("push_devices")
    op.drop_column("user_profiles", "monthly_budget")
    op.drop_constraint("ck_journal_entries_source", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_entries_source", "journal_entries", f"source IN ({_SOURCES})"
    )
