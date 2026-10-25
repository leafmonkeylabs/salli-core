"""Closed books stay closed: no entry or posting in them is changed or deleted.

- core_0025's trigger refused only a new entry on or before the lock date. It
  now refuses an UPDATE or DELETE of an entry dated there too, and a new
  trigger refuses an INSERT, UPDATE or DELETE of a posting whose entry is,
  whatever path it comes by. Two changes are let through: deleting a user's
  own rows while their account is erased (`salli.erase_user`, as core_0017
  allows for the decision journal; a posting deleted with its entry has
  passed the entry's check), and setting `reversed_by` on an original, and
  nothing else, when its reversal is dated after the lock date.

Revision ID: core_0030_lock_edits
Revises: core_0028_mcp_scopes_audit
Create Date: 2026-10-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "core_0030_lock_edits"
down_revision: str | None = "core_0028_mcp_scopes_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Autogenerate cannot see triggers; asyncpg needs each statement in its
    # own execute().
    op.execute("""
        CREATE OR REPLACE FUNCTION refuse_entry_in_closed_books()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE locked DATE; reversal_day DATE;
        BEGIN
            IF TG_OP = 'DELETE'
               AND current_setting('salli.erase_user', true) IS NOT NULL
               AND current_setting('salli.erase_user', true) = OLD.user_id THEN
                RETURN OLD;
            END IF;
            IF TG_OP <> 'INSERT' THEN
                SELECT lock_date INTO locked FROM user_profiles WHERE id = OLD.user_id;
                IF locked IS NOT NULL AND OLD.entry_date::date <= locked THEN
                    IF TG_OP = 'UPDATE' AND OLD.reversed_by IS NULL
                       AND NEW.reversed_by IS NOT NULL
                       AND to_jsonb(NEW) - 'reversed_by' = to_jsonb(OLD) - 'reversed_by' THEN
                        SELECT entry_date::date INTO reversal_day
                          FROM journal_entries WHERE id = NEW.reversed_by;
                        IF reversal_day > locked THEN
                            RETURN NEW;
                        END IF;
                    END IF;
                    RAISE EXCEPTION
                        'The books are closed up to and including %: % of an entry on % is refused',
                        locked, TG_OP, OLD.entry_date;
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
            END IF;
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
    op.execute("DROP TRIGGER IF EXISTS trg_journal_entries_closed_books ON journal_entries")
    op.execute("""
        CREATE TRIGGER trg_journal_entries_closed_books
            BEFORE INSERT OR UPDATE OR DELETE ON journal_entries
            FOR EACH ROW
            EXECUTE FUNCTION refuse_entry_in_closed_books()
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION refuse_posting_in_closed_books()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE entry_owner TEXT; entry_day TEXT; locked DATE;
        BEGIN
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
    """)
    op.execute("""
        CREATE TRIGGER trg_postings_closed_books
            BEFORE INSERT OR UPDATE OR DELETE ON postings
            FOR EACH ROW
            EXECUTE FUNCTION refuse_posting_in_closed_books()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_postings_closed_books ON postings")
    op.execute("DROP FUNCTION IF EXISTS refuse_posting_in_closed_books()")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_entries_closed_books ON journal_entries")
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
