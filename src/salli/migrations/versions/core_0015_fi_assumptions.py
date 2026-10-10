"""FI planning assumptions are user data with sources, in one JSON column.

Decision 4 of docs/design/country-neutral-core.md: projections run in real
terms, with one neutral placeholder (always labelled as one) where the user has
not set a figure; there is no table of defaults by currency any more. What the
user (or their agent) sets is kept with where it comes from:

    fi_assumptions = {"inflation": {"value": "0.03", "source": "...",
                                    "note": "...", "set_at": "..."}, ...}

for `real_return`, `nominal_return`, `inflation` and `safe_withdrawal_rate`.
This replaces core_0008's three bare NUMERIC columns (`fi_inflation`,
`fi_real_return`, `fi_safe_withdrawal_rate`), which had no room for a source.
There are no real users yet, so their values are dropped rather than moved.

Reversible in shape only: the downgrade restores the three columns, empty.

Revision ID: core_0015_fi_assumptions
Revises: core_0014_generic_tax_ids
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0015_fi_assumptions"
down_revision: str | None = "core_0014_generic_tax_ids"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_COLUMNS = ("fi_inflation", "fi_real_return", "fi_safe_withdrawal_rate")


def upgrade() -> None:
    for column in _OLD_COLUMNS:
        op.drop_column("user_profiles", column)
    op.add_column(
        "user_profiles",
        sa.Column(
            "fi_assumptions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_user_profiles_fi_assumptions",
        "user_profiles",
        "jsonb_typeof(fi_assumptions) = 'object'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_profiles_fi_assumptions", "user_profiles", type_="check")
    op.drop_column("user_profiles", "fi_assumptions")
    for column in _OLD_COLUMNS:
        op.add_column(
            "user_profiles", sa.Column(column, sa.Numeric(precision=8, scale=6), nullable=True)
        )
