"""Bank reconciliation, the books' start, and how long documents are kept.

- `statements` keep the bank's opening and closing balance for their period
  (in the account's currency's minor units), when an import carried them or
  the person typed them in from a paper statement.
- `postings.cleared`: matched to a statement's line. The one change a posting
  in closed books may still take, so a closed month can be reconciled:
  core_0030's trigger now lets an UPDATE through that changes nothing else.
- `reconciliations`: a statement whose cleared postings add up to its
  closing balance, who completed it and when; recorded only at a difference
  of zero.
- `user_profiles.books_start`: the day opening balances are posted on.
- `user_profiles.document_retention_years` and `agent_documents.retain_until`:
  a document is kept until then.

Revision ID: core_0034_reconcile
Revises: core_0032_account_freeze
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0034_reconcile"
down_revision: str | None = "core_0032_account_freeze"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# core_0030's function, with the cleared flag let through.
_POSTING_TRIGGER = """
    CREATE OR REPLACE FUNCTION refuse_posting_in_closed_books()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE entry_owner TEXT; entry_day TEXT; locked DATE;
    BEGIN
        IF TG_OP = 'UPDATE' AND {cleared_only} THEN
            RETURN NEW;
        END IF;
        IF TG_OP <> 'INSERT' THEN
            SELECT e.user_id, e.entry_date, p.lock_date
              INTO entry_owner, entry_day, locked
              FROM journal_entries e LEFT JOIN user_profiles p ON p.id = e.user_id
             WHERE e.id = OLD.entry_id;
            IF locked IS NOT NULL AND entry_day::date <= locked
               AND NOT (TG_OP = 'DELETE'
                        AND current_setting('salli.erase_user', true) IS NOT NULL
                        AND current_setting('salli.erase_user', true) = entry_owner) THEN
                RAISE EXCEPTION
                    'The books are closed up to and including %: % of a posting on % is refused',
                    locked, TG_OP, entry_day;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
        END IF;
        SELECT e.entry_date, p.lock_date INTO entry_day, locked
          FROM journal_entries e LEFT JOIN user_profiles p ON p.id = e.user_id
         WHERE e.id = NEW.entry_id;
        IF locked IS NOT NULL AND entry_day::date <= locked THEN
            RAISE EXCEPTION
                'The books are closed up to and including %: % of a posting on % is refused',
                locked, TG_OP, entry_day;
        END IF;
        RETURN NEW;
    END;
    $$
"""


def upgrade() -> None:
    op.add_column("statements", sa.Column("opening_balance_minor", sa.BigInteger(), nullable=True))
    op.add_column("statements", sa.Column("closing_balance_minor", sa.BigInteger(), nullable=True))
    op.add_column(
        "postings",
        sa.Column("cleared", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_table(
        "reconciliations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("statement_id", sa.String(length=36), nullable=False),
        sa.Column("cleared_total_minor", sa.BigInteger(), nullable=False),
        sa.Column("difference_minor", sa.BigInteger(), nullable=False),
        sa.Column("completed_by", sa.String(length=200), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("difference_minor = 0", name="ck_reconciliations_difference"),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("statement_id"),
    )
    op.create_index(
        op.f("ix_reconciliations_user_id"), "reconciliations", ["user_id"], unique=False
    )
    op.add_column("user_profiles", sa.Column("books_start", sa.Date(), nullable=True))
    op.add_column(
        "user_profiles", sa.Column("document_retention_years", sa.Integer(), nullable=True)
    )
    op.add_column("agent_documents", sa.Column("retain_until", sa.Date(), nullable=True))
    op.execute(
        _POSTING_TRIGGER.format(
            cleared_only="to_jsonb(NEW) - 'cleared' = to_jsonb(OLD) - 'cleared'"
        )
    )


def downgrade() -> None:
    op.execute(_POSTING_TRIGGER.format(cleared_only="false"))
    op.drop_column("agent_documents", "retain_until")
    op.drop_column("user_profiles", "document_retention_years")
    op.drop_column("user_profiles", "books_start")
    op.drop_index(op.f("ix_reconciliations_user_id"), table_name="reconciliations")
    op.drop_table("reconciliations")
    op.drop_column("postings", "cleared")
    op.drop_column("statements", "closing_balance_minor")
    op.drop_column("statements", "opening_balance_minor")
