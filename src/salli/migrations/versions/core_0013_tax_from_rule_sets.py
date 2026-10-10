"""Tax is computed only from the user's own rule sets: computations reshaped.

Phase 3 of docs/design/country-neutral-core.md. The built-in Sri Lankan pack
and its engine are gone, and with them the fixed shape a computation had
(`result_json` holding `fsi_tax`, `apit_credit`, `pack_country`, …). A
computation now records:

- the rule set version that computed it (`rule_set_version_id`, NOT NULL, a
  composite foreign key with `user_id` so it can only name the user's own) and
  that version's `content_hash`;
- its jurisdiction and year (`country`, `region`, `year`);
- every line (`lines`), the inputs it was computed from (`inputs`) and its
  warnings;
- what is owed: `net_minor`, `tax_payable_minor`, `refund_due_minor`, BIGINT
  minor units of `currency`.

Dropped: `pack_version`, `inputs_hash`, `result_json`, and the old
(user_id, year) index. The old engine's computations can't be reproduced by
any rule set, and there are no real users yet, so existing rows are deleted
rather than migrated. `user_id` widens to 64 characters, as every newer table.

`tax_rule_set_versions` gains a unique (id, user_id) for the foreign key.

Reversible in shape only: the downgrade restores the old columns and deletes
the rows, which the old engine couldn't read.

Revision ID: core_0013_tax_from_rule_sets
Revises: core_0012_pat_permissions
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0013_tax_from_rule_sets"
down_revision: str | None = "core_0012_pat_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM tax_computations")

    op.drop_constraint(
        "tax_computations_rule_set_version_id_fkey", "tax_computations", type_="foreignkey"
    )
    op.drop_index("ix_tax_computations_user_year", table_name="tax_computations")
    op.drop_column("tax_computations", "pack_version")
    op.drop_column("tax_computations", "inputs_hash")
    op.drop_column("tax_computations", "result_json")

    op.alter_column(
        "tax_computations",
        "user_id",
        existing_type=sa.String(length=36),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "tax_computations",
        "year",
        existing_type=sa.String(length=10),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        "tax_computations", "rule_set_version_id", existing_type=sa.String(36), nullable=False
    )
    op.alter_column("tax_computations", "content_hash", existing_type=sa.String(64), nullable=False)
    op.alter_column(
        "tax_computations",
        "lines",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
    )
    op.add_column("tax_computations", sa.Column("country", sa.String(length=2), nullable=False))
    op.add_column("tax_computations", sa.Column("region", sa.String(length=200), nullable=True))
    op.add_column("tax_computations", sa.Column("currency", sa.String(length=3), nullable=False))
    op.add_column("tax_computations", sa.Column("net_minor", sa.BigInteger(), nullable=False))
    op.add_column(
        "tax_computations", sa.Column("tax_payable_minor", sa.BigInteger(), nullable=False)
    )
    op.add_column(
        "tax_computations", sa.Column("refund_due_minor", sa.BigInteger(), nullable=False)
    )
    op.add_column(
        "tax_computations",
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.add_column(
        "tax_computations",
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    op.create_unique_constraint(
        "uq_tax_rule_set_versions_id_user", "tax_rule_set_versions", ["id", "user_id"]
    )
    op.create_foreign_key(
        "fk_tax_computations_version",
        "tax_computations",
        "tax_rule_set_versions",
        ["rule_set_version_id", "user_id"],
        ["id", "user_id"],
    )
    op.create_index(
        "ix_tax_computations_user_jurisdiction_year",
        "tax_computations",
        ["user_id", "country", "year", "created_at"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_tax_computations_country", "tax_computations", "country ~ '^[A-Z]{2}$'"
    )
    op.create_check_constraint(
        "ck_tax_computations_amounts",
        "tax_computations",
        "tax_payable_minor >= 0 AND refund_due_minor >= 0"
        " AND net_minor = tax_payable_minor - refund_due_minor"
        " AND (tax_payable_minor = 0 OR refund_due_minor = 0)",
    )
    op.create_check_constraint(
        "ck_tax_computations_lines", "tax_computations", "jsonb_typeof(lines) = 'array'"
    )


def downgrade() -> None:
    op.execute("DELETE FROM tax_computations")

    op.drop_constraint("ck_tax_computations_lines", "tax_computations", type_="check")
    op.drop_constraint("ck_tax_computations_amounts", "tax_computations", type_="check")
    op.drop_constraint("ck_tax_computations_country", "tax_computations", type_="check")
    op.drop_index("ix_tax_computations_user_jurisdiction_year", table_name="tax_computations")
    op.drop_constraint("fk_tax_computations_version", "tax_computations", type_="foreignkey")
    op.drop_constraint("uq_tax_rule_set_versions_id_user", "tax_rule_set_versions", type_="unique")
    for column in (
        "warnings",
        "inputs",
        "refund_due_minor",
        "tax_payable_minor",
        "net_minor",
        "currency",
        "region",
        "country",
    ):
        op.drop_column("tax_computations", column)

    op.alter_column(
        "tax_computations",
        "lines",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
    )
    op.alter_column("tax_computations", "content_hash", existing_type=sa.String(64), nullable=True)
    op.alter_column(
        "tax_computations", "rule_set_version_id", existing_type=sa.String(36), nullable=True
    )
    op.alter_column(
        "tax_computations",
        "year",
        existing_type=sa.String(length=32),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.alter_column(
        "tax_computations",
        "user_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=36),
        existing_nullable=False,
    )
    op.add_column(
        "tax_computations",
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.add_column(
        "tax_computations", sa.Column("inputs_hash", sa.String(length=64), nullable=False)
    )
    op.add_column(
        "tax_computations", sa.Column("pack_version", sa.String(length=20), nullable=False)
    )
    op.create_index(
        "ix_tax_computations_user_year", "tax_computations", ["user_id", "year"], unique=False
    )
    op.create_foreign_key(
        "tax_computations_rule_set_version_id_fkey",
        "tax_computations",
        "tax_rule_set_versions",
        ["rule_set_version_id"],
        ["id"],
    )
