"""An account with entries in closed books keeps its type and tax role.

They decide what its postings count as, so changing either would change the
closed books' statements and tax. LedgerService refuses it; this trigger
refuses it by any other path, whenever any posting to the account is dated
on or before the lock date (even postings netting to zero). As core_0030
does, a change while the user's own account is erased (`salli.erase_user`)
is let through.

Revision ID: core_0032_account_freeze
Revises: core_0031_grant_lifetime
Create Date: 2026-10-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "core_0032_account_freeze"
down_revision: str | None = "core_0031_grant_lifetime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION refuse_account_change_in_closed_books()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE locked DATE;
        BEGIN
            IF NEW.type IS NOT DISTINCT FROM OLD.type
               AND NEW.tax_role IS NOT DISTINCT FROM OLD.tax_role THEN
                RETURN NEW;
            END IF;
            IF current_setting('salli.erase_user', true) IS NOT NULL
               AND current_setting('salli.erase_user', true) = OLD.user_id THEN
                RETURN NEW;
            END IF;
            SELECT lock_date INTO locked FROM user_profiles WHERE id = OLD.user_id;
            IF locked IS NOT NULL AND EXISTS (
                SELECT 1 FROM postings p JOIN journal_entries e ON e.id = p.entry_id
                 WHERE p.account_id = OLD.id AND e.entry_date::date <= locked
            ) THEN
                RAISE EXCEPTION
                    'The books are closed up to and including %: this account has entries there, so its type and tax role can''t change',
                    locked;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_accounts_closed_books
            BEFORE UPDATE ON accounts
            FOR EACH ROW
            EXECUTE FUNCTION refuse_account_change_in_closed_books()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_accounts_closed_books ON accounts")
    op.execute("DROP FUNCTION IF EXISTS refuse_account_change_in_closed_books()")
