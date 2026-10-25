"""The operator's support sessions: a time-boxed, read-only look at one
person's books, for a reason, which the person sees and may end. Under the
same row-level security as the rest of a person's data (core_0051).

Revision ID: core_0052_support_sessions
Revises: core_0051_row_security
Create Date: 2026-10-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0052_support_sessions"
down_revision: str | None = "core_0051_row_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by", sa.String(length=20), nullable=True),
        sa.CheckConstraint(
            "ended_by IS NULL OR ended_by IN ('person', 'operator', 'expiry')",
            name="ck_support_sessions_ended_by",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_support_sessions_user_id"), "support_sessions", ["user_id"], unique=False
    )
    op.execute("ALTER TABLE support_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE support_sessions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY person_rows ON support_sessions"
        " USING (salli_row_visible(user_id)) WITH CHECK (salli_row_visible(user_id))"
    )


def downgrade() -> None:
    op.drop_table("support_sessions")
