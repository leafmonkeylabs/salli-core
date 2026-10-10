"""Tax ids are generic only: the profile's legacy `ird_number` column goes.

Phase 3 of docs/design/country-neutral-core.md. A user's tax ids are the
generic `tax_ids` list (`[{"scheme": "XX-KIND", "value": ...}]`), and nothing
else: salli-core knows no country's schemes. The `ird_number` column, kept
since core_0008 as a mirror of one country's taxpayer number, is dropped. (The
matching `nic` field never had a column.) There are no real users yet, so
nothing is copied anywhere first: a number that was in the column is already
in `tax_ids`, where core_0008 put it.

Reversible in shape only: the downgrade restores an empty column.

Revision ID: core_0014_generic_tax_ids
Revises: core_0013_tax_from_rule_sets
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0014_generic_tax_ids"
down_revision: str | None = "core_0013_tax_from_rule_sets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("user_profiles", "ird_number")


def downgrade() -> None:
    op.add_column("user_profiles", sa.Column("ird_number", sa.VARCHAR(length=32), nullable=True))
