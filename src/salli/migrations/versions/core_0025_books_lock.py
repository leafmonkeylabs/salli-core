"""Closed books: a lock date, and reversals that say why.

- `user_profiles.lock_date`: the books are closed up to and including this
  day. A trigger refuses any journal entry dated on or before it, whatever
  path inserts it, so a year that is filed stays as filed. NULL closes
  nothing.
- `journal_entries.source` takes "reversal": a reversal is dated the day it
  is made, not the original's, and its description says why. Reversals made
  before keep "manual" and their "REVERSAL: " description.

Revision ID: core_0025_books_lock
Revises: core_0024_briefings
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0025_books_lock"
down_revision: str | None = "core_0024_briefings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCES = "'manual','statement','sms','system'"


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("lock_date", sa.Date(), nullable=True))
    op.drop_constraint("ck_journal_entries_source", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_entries_source", "journal_entries", f"source IN ({_SOURCES},'reversal')"
    )

    # Autogenerate cannot see triggers; asyncpg needs each statement in its
    # own execute().
    op.execute("""
        CREATE OR REPLACE FUNCTION refuse_entry_in_closed_books()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE locked DATE;
        BEGIN
            SELECT lock_date INTO locked FROM user_profiles WHERE id = NEW.user_id;
            IF locked IS NOT NULL AND NEW.entry_date::date <= locked THEN
                RAISE EXCEPTION
                    'The books are closed up to and including %: an entry on % is refused',
                    locked, NEW.entry_date;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_journal_entries_closed_books
            BEFORE INSERT ON journal_entries
            FOR EACH ROW
            EXECUTE FUNCTION refuse_entry_in_closed_books()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_journal_entries_closed_books ON journal_entries")
    op.execute("DROP FUNCTION IF EXISTS refuse_entry_in_closed_books()")
    op.execute("UPDATE journal_entries SET source = 'manual' WHERE source = 'reversal'")
    op.drop_constraint("ck_journal_entries_source", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_entries_source", "journal_entries", f"source IN ({_SOURCES})"
    )
    op.drop_column("user_profiles", "lock_date")
