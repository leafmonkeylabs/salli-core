"""Briefings: what a monthly briefing was written from.

The advisor no longer recommends. A report is a briefing: its summary, and in
`briefing` its notes, the figures, signals and assumptions it was written
from. Reports stored before keep their `recommendations`, with no `briefing`.

Revision ID: core_0024_briefings
Revises: core_0023_statement_drafts
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0024_briefings"
down_revision: str | None = "core_0023_statement_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "advisory_reports",
        sa.Column("briefing", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("advisory_reports", "briefing")
