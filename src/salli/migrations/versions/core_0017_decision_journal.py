"""The decision lab's decisions: principles, the decision journal and reviews.

Phase 2a of docs/design/decision-lab.md (docs/decisions.md):

- `principles`: a user's own rules of thumb, a label and a check over the
  decision figures. Preferences: edited (with a version) and archived,
  never deleted.
- `decisions`: the decision journal's entries, each a self-describing
  document (`salli.decision/1`) with its content hash.
- `decision_notes` and `decision_reviews`: what is appended to an entry
  later, each a document naming the entry's hash. A composite foreign key
  keeps each one's owner the entry's.

The journal is append-only. The repository has no update or delete path,
and a trigger refuses any UPDATE, DELETE or TRUNCATE on the three journal
tables, as defence in depth. The one exception is erasing a user's account
(`SQLDataPortabilityRepository.delete_all`), which names the user for the
transaction with `set_config('salli.erase_user', <user id>, true)`: a
DELETE of that user's rows, and only theirs, goes through.

Revision ID: core_0017_decision_journal
Revises: core_0016_decision_baseline
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0017_decision_journal"
down_revision: str | None = "core_0016_decision_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HASH = "hash ~ '^sha256:[0-9a-f]{64}$'"
_JOURNAL = ("decisions", "decision_notes", "decision_reviews")


def upgrade() -> None:
    op.create_table(
        "principles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("author_kind", sa.String(length=10), nullable=False),
        sa.Column("author_name", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version > 0", name="ck_principles_version"),
        sa.CheckConstraint("author_kind IN ('user','agent')", name="ck_principles_author_kind"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_principles_user_id", "principles", ["user_id"], unique=False)

    op.create_table(
        "decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("chosen", sa.String(length=200), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("review_on", sa.Date(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hash", sa.String(length=80), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("jsonb_typeof(content) = 'object'", name="ck_decisions_content"),
        sa.CheckConstraint(_HASH, name="ck_decisions_hash"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", name="uq_decisions_id_user"),
    )
    op.create_index(
        "ix_decisions_user_review_on", "decisions", ["user_id", "review_on"], unique=False
    )

    for table, extra in (
        ("decision_notes", []),
        ("decision_reviews", [sa.Column("as_of", sa.Date(), nullable=False)]),
    ):
        op.create_table(
            table,
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("decision_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            *extra,
            sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("hash", sa.String(length=80), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("jsonb_typeof(content) = 'object'", name=f"ck_{table}_content"),
            sa.CheckConstraint(_HASH, name=f"ck_{table}_hash"),
            sa.ForeignKeyConstraint(
                ["decision_id", "user_id"],
                ["decisions.id", "decisions.user_id"],
                name=f"fk_{table}_decision",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            f"ix_{table}_user_decision", table, ["user_id", "decision_id"], unique=False
        )

    # Append-only, whatever a caller does. Autogenerate cannot see triggers;
    # asyncpg needs each statement in its own execute().
    op.execute("""
        CREATE OR REPLACE FUNCTION refuse_decision_journal_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE'
               AND current_setting('salli.erase_user', true) IS NOT NULL
               AND current_setting('salli.erase_user', true) = OLD.user_id THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION
                'The decision journal is append-only: % on % is refused (append a note '
                'or a review instead)', TG_OP, TG_TABLE_NAME;
        END;
        $$
    """)
    for table in _JOURNAL:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_append_only
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION refuse_decision_journal_change()
        """)
        op.execute(f"""
            CREATE TRIGGER trg_{table}_no_truncate
                BEFORE TRUNCATE ON {table}
                FOR EACH STATEMENT
                EXECUTE FUNCTION refuse_decision_journal_change()
        """)


def downgrade() -> None:
    for table in reversed(_JOURNAL):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_truncate ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS refuse_decision_journal_change()")
    for table in ("decision_reviews", "decision_notes"):
        op.drop_index(f"ix_{table}_user_decision", table_name=table)
        op.drop_table(table)
    op.drop_index("ix_decisions_user_review_on", table_name="decisions")
    op.drop_table("decisions")
    op.drop_index("ix_principles_user_id", table_name="principles")
    op.drop_table("principles")
