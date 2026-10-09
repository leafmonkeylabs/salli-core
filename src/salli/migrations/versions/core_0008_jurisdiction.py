"""Where each user is taxed, and the numbers their tax authorities know them by.

`user_profiles` gains `tax_residency` (an ISO 3166-1 alpha-2 code, NULL until
the user says) and `tax_ids` (a JSON list of {"scheme", "value"}, empty by
default).

The profile's two Sri Lankan numbers become tax ids, and stay where they were:

- "LK-TIN" is the `ird_number` column, or, where that was never filled, the
  `ird_number` memory onboarding saved. The column is filled from the memory
  too, so the two agree.
- "LK-NIC" is the `nic_number` memory: onboarding never had a column for it.

A user with Sri Lankan data (either number, or a stored Sri Lankan tax
computation) is tax resident in LK. Everyone else's residency stays NULL:
nothing is assumed about them.

Additive and safe on a live database: two new columns (the NOT NULL one has a
constant default, so adding it rewrites no rows), and updates that touch only
rows with Sri Lankan data. Values that could never have been valid tax ids
(blank, or longer than 32 characters) are left where they are and not copied.
Downgrading drops the new columns, and with them any tax id that is not one
of the two Sri Lankan numbers, which stay in the column and the memory.

Revision ID: core_0008_jurisdiction
Revises: core_0007_ai_connections
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0008_jurisdiction"
down_revision: str | None = "core_0007_ai_connections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _memory(slug: str) -> str:
    """The latest value of an onboarding memory, per user, trimmed."""
    return (
        "SELECT DISTINCT ON (d.user_id) d.user_id, btrim(d.content) AS value"
        "  FROM agent_documents d"
        f" WHERE d.namespace = 'memories' AND d.slug = '{slug}'"
        " ORDER BY d.user_id, d.updated_at DESC"
    )


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("tax_residency", sa.String(length=2), nullable=True))
    op.add_column(
        "user_profiles",
        sa.Column(
            "tax_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_user_profiles_tax_residency",
        "user_profiles",
        "tax_residency IS NULL OR tax_residency ~ '^[A-Z]{2}$'",
    )
    op.create_check_constraint(
        "ck_user_profiles_tax_ids", "user_profiles", "jsonb_typeof(tax_ids) = 'array'"
    )

    # LK-TIN: the column, or the onboarding memory where the column is empty.
    op.execute(
        "UPDATE user_profiles p"
        "   SET tax_ids = jsonb_build_array("
        "         jsonb_build_object('scheme', 'LK-TIN', 'value', tin.value))"
        "  FROM ("
        "    SELECT p2.id,"
        "           COALESCE(NULLIF(btrim(p2.ird_number), ''), NULLIF(m.value, '')) AS value"
        "      FROM user_profiles p2"
        f"     LEFT JOIN ({_memory('ird_number')}) m ON m.user_id = p2.id"
        "  ) AS tin"
        " WHERE tin.id = p.id AND tin.value IS NOT NULL AND char_length(tin.value) <= 32"
    )
    # The column agrees with the LK-TIN it now mirrors.
    op.execute(
        "UPDATE user_profiles"
        "   SET ird_number = ("
        "         SELECT e->>'value' FROM jsonb_array_elements(tax_ids) e"
        "          WHERE e->>'scheme' = 'LK-TIN')"
        " WHERE NULLIF(btrim(ird_number), '') IS NULL"
        '   AND tax_ids @> \'[{"scheme": "LK-TIN"}]\'::jsonb'
    )
    # LK-NIC: only ever kept as an onboarding memory.
    op.execute(
        "UPDATE user_profiles p"
        "   SET tax_ids = p.tax_ids || jsonb_build_array("
        "         jsonb_build_object('scheme', 'LK-NIC', 'value', nic.value))"
        f"  FROM ({_memory('nic_number')}) AS nic"
        " WHERE nic.user_id = p.id AND nic.value <> '' AND char_length(nic.value) <= 32"
        '   AND NOT p.tax_ids @> \'[{"scheme": "LK-NIC"}]\'::jsonb'
    )
    # Sri Lankan data makes a Sri Lankan tax resident. Every computation stored
    # so far is Sri Lankan; the oldest do not record a country at all.
    op.execute(
        "UPDATE user_profiles p"
        "   SET tax_residency = 'LK'"
        " WHERE p.tax_residency IS NULL"
        '   AND (p.tax_ids @> \'[{"scheme": "LK-TIN"}]\'::jsonb'
        '     OR p.tax_ids @> \'[{"scheme": "LK-NIC"}]\'::jsonb'
        "     OR EXISTS (SELECT 1 FROM tax_computations t"
        "                 WHERE t.user_id = p.id"
        "                   AND COALESCE(t.result_json->>'pack_country', 'LK') = 'LK'))"
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_profiles_tax_ids", "user_profiles", type_="check")
    op.drop_constraint("ck_user_profiles_tax_residency", "user_profiles", type_="check")
    op.drop_column("user_profiles", "tax_ids")
    op.drop_column("user_profiles", "tax_residency")
