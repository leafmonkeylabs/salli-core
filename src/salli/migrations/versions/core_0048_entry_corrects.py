"""Corrected entries link to the entry they correct.

Additive: `journal_entries.corrects_id`, null on every existing entry, so no
stored hash changes (the chain covers it only when set). A corrected copy
keeps the original's source and external_ref, so a client_ref is unique
among entries that correct nothing.

Revision ID: core_0048_entry_corrects
Revises: core_0047_household_basics
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0048_entry_corrects"
down_revision: str | None = "core_0047_household_basics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLIENT_REF = "source = 'manual' AND external_ref LIKE 'client-ref:%'"


def upgrade() -> None:
    op.add_column(
        "journal_entries",
        sa.Column("corrects_id", sa.String(36), sa.ForeignKey("journal_entries.id"), nullable=True),
    )
    op.drop_index("uq_journal_entries_client_ref", table_name="journal_entries")
    op.create_index(
        "uq_journal_entries_client_ref",
        "journal_entries",
        ["user_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text(f"{_CLIENT_REF} AND corrects_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_journal_entries_client_ref", table_name="journal_entries")
    op.create_index(
        "uq_journal_entries_client_ref",
        "journal_entries",
        ["user_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text(_CLIENT_REF),
    )
    op.drop_column("journal_entries", "corrects_id")
