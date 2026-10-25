"""Push preferences: which alerts a person's phone takes, and quiet hours.

Additive: one nullable column; null reads as every alert, no quiet hours.

Revision ID: core_0049_push_preferences
Revises: core_0048_entry_corrects
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0049_push_preferences"
down_revision: str | None = "core_0048_entry_corrects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("push", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_preferences", "push")
