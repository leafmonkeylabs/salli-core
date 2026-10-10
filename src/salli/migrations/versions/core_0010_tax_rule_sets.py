"""Tax rule sets: a user's own tax rules, as versioned, immutable documents.

Phase 2 of docs/design/country-neutral-core.md.

- `tax_rule_sets`: one per user, country, region and year, pointing at its
  active version (if any). Unique even when the region is NULL, by an index
  over COALESCE(region, '').
- `tax_rule_set_versions`: each version's document (JSONB), content hash,
  lifecycle status, last validation report and author. A version's owner and
  set are tied to its set's by a composite foreign key, the set's active
  version to the set by another, and at most one version of a set is active
  (a partial unique index).
- A trigger refuses any UPDATE that would change a version's content, its
  content hash, or which set, owner or number it belongs to. The repository
  never tries; this is so nothing else can either.
- `tax_computations` gains `rule_set_version_id`, `content_hash` and `lines`,
  all NULL, for phase 3. Nothing writes them yet.

New, empty tables and nullable columns: nothing existing changes. Reversible.

Revision ID: core_0010_tax_rule_sets
Revises: core_0009_investments
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0010_tax_rule_sets"
down_revision: str | None = "core_0009_investments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUSES = "'draft','validated','proposed','active','superseded','invalid'"


def upgrade() -> None:
    op.create_table(
        "tax_rule_sets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("region", sa.String(length=200), nullable=True),
        sa.Column("year_label", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("active_version_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("country ~ '^[A-Z]{2}$'", name="ck_tax_rule_sets_country"),
        sa.CheckConstraint("region IS NULL OR region <> ''", name="ck_tax_rule_sets_region"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_tax_rule_sets_id_user"),
    )
    op.create_index("ix_tax_rule_sets_user_id", "tax_rule_sets", ["user_id"], unique=False)
    op.create_index(
        "uq_tax_rule_sets_jurisdiction_year",
        "tax_rule_sets",
        ["user_id", "country", sa.text("COALESCE(region, '')"), "year_label"],
        unique=True,
    )

    op.create_table(
        "tax_rule_set_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rule_set_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("author_kind", sa.String(length=10), nullable=False),
        sa.Column("author_name", sa.String(length=200), nullable=True),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version > 0", name="ck_tax_rule_set_versions_version"),
        sa.CheckConstraint(f"status IN ({_STATUSES})", name="ck_tax_rule_set_versions_status"),
        sa.CheckConstraint(
            "author_kind IN ('user','agent')", name="ck_tax_rule_set_versions_author_kind"
        ),
        sa.CheckConstraint(
            "(status <> 'active' OR activated_at IS NOT NULL)"
            " AND (status <> 'superseded' OR superseded_at IS NOT NULL)"
            " AND (status <> 'proposed' OR proposed_at IS NOT NULL)",
            name="ck_tax_rule_set_versions_timestamps",
        ),
        sa.ForeignKeyConstraint(
            ["rule_set_id", "user_id"],
            ["tax_rule_sets.id", "tax_rule_sets.user_id"],
            name="fk_tax_rule_set_versions_rule_set",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_set_id", "version", name="uq_tax_rule_set_versions_number"),
        sa.UniqueConstraint("rule_set_id", "id", name="uq_tax_rule_set_versions_set_id"),
    )
    op.create_index(
        "ix_tax_rule_set_versions_user_id", "tax_rule_set_versions", ["user_id"], unique=False
    )
    op.create_index(
        "uq_tax_rule_set_versions_one_active",
        "tax_rule_set_versions",
        ["rule_set_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    # Created after both tables: each refers to the other.
    op.create_foreign_key(
        "fk_tax_rule_sets_active_version",
        "tax_rule_sets",
        "tax_rule_set_versions",
        ["id", "active_version_id"],
        ["rule_set_id", "id"],
    )

    # A version's document is immutable: an edit is a new version. Autogenerate
    # cannot see triggers. asyncpg needs each statement in its own execute().
    op.execute("""
        CREATE OR REPLACE FUNCTION refuse_rule_set_content_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'Tax rule set version % is immutable: its content, content hash, set, '
                'owner and number cannot change (create a new version instead)', OLD.id;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_rule_set_content_immutable
            BEFORE UPDATE ON tax_rule_set_versions
            FOR EACH ROW
            WHEN (OLD.content IS DISTINCT FROM NEW.content
                  OR OLD.content_hash IS DISTINCT FROM NEW.content_hash
                  OR OLD.rule_set_id IS DISTINCT FROM NEW.rule_set_id
                  OR OLD.user_id IS DISTINCT FROM NEW.user_id
                  OR OLD.version IS DISTINCT FROM NEW.version)
            EXECUTE FUNCTION refuse_rule_set_content_update()
    """)

    op.add_column(
        "tax_computations",
        sa.Column("rule_set_version_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "tax_computations", sa.Column("content_hash", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "tax_computations",
        sa.Column("lines", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_foreign_key(
        "tax_computations_rule_set_version_id_fkey",
        "tax_computations",
        "tax_rule_set_versions",
        ["rule_set_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "tax_computations_rule_set_version_id_fkey", "tax_computations", type_="foreignkey"
    )
    op.drop_column("tax_computations", "lines")
    op.drop_column("tax_computations", "content_hash")
    op.drop_column("tax_computations", "rule_set_version_id")
    op.execute("DROP TRIGGER IF EXISTS trg_rule_set_content_immutable ON tax_rule_set_versions")
    op.execute("DROP FUNCTION IF EXISTS refuse_rule_set_content_update()")
    op.drop_constraint("fk_tax_rule_sets_active_version", "tax_rule_sets", type_="foreignkey")
    op.drop_index("uq_tax_rule_set_versions_one_active", table_name="tax_rule_set_versions")
    op.drop_index("ix_tax_rule_set_versions_user_id", table_name="tax_rule_set_versions")
    op.drop_table("tax_rule_set_versions")
    op.drop_index("uq_tax_rule_sets_jurisdiction_year", table_name="tax_rule_sets")
    op.drop_index("ix_tax_rule_sets_user_id", table_name="tax_rule_sets")
    op.drop_table("tax_rule_sets")
