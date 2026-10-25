"""Filed years, a year-end close, a hash-chained ledger and who posted what.

- `tax_returns` and `tax_return_payments`: each version of a return (draft,
  filed, amended) with a snapshot of its computation and the snapshot's
  hash, and the payments against it. Append-only, like the decision journal
  (core_0017): UPDATE, DELETE and TRUNCATE are refused except while the
  user's own account is erased (`salli.erase_user`).
- `accounts.equity_role`: `retained_earnings`, on at most one equity account
  a user's; a year-end close (source `year_end_close`) moves earnings to it.
- Journal entries record who posted them (`created_by`, `created_via`) and
  form a per-user hash chain (`seq`, `prev_hash`, `hash`;
  domain/accounting/chain.py). The entries stored before are chained here,
  in the order they were stored, as posted by their owner via "unrecorded".
- A reversal names its original (`reverses_id`, once); the original's
  `reversed_by` column goes, read from the reversal instead, so nothing ever
  writes to a stored entry. Entries and postings now refuse any UPDATE, and
  any DELETE but erasure, open books or closed; core_0030's closed-books
  trigger loses the `reversed_by` exception it no longer needs.

Revision ID: core_0037_filed_years
Revises: core_0036_access_grants
Create Date: 2026-10-25
"""

import hashlib
import json
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0037_filed_years"
down_revision: str | None = "core_0036_access_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCES = "'manual','statement','sms','system','reversal'"
_APPEND_ONLY = ("tax_returns", "tax_return_payments")


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _hash(content: dict[str, object]) -> str:
    """chain.entry_hash as of this migration: the SHA-256 of the canonical
    JSON (sorted keys, compact, ASCII) of plain text and integers."""
    text = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(text.encode("ascii")).hexdigest()


def _chain_existing_entries() -> None:
    conn = op.get_bind()
    legs: dict[str, list[dict[str, object]]] = {}
    for p in conn.execute(
        sa.text(
            "SELECT entry_id, account_id, direction, amount_minor, currency, fx_rate FROM postings"
        )
    ):
        rate = Decimal(str(p.fx_rate)).quantize(Decimal("1e-8"), rounding=ROUND_HALF_UP)
        legs.setdefault(p.entry_id, []).append(
            {
                "account_id": p.account_id,
                "direction": int(p.direction),
                "amount_minor": int(p.amount_minor),
                "currency": p.currency,
                "fx_rate": _decimal_text(rate),
            }
        )
    rows = conn.execute(
        sa.text(
            "SELECT id, user_id, entry_date, description, source, external_ref, reverses_id "
            "FROM journal_entries ORDER BY user_id, created_at, id"
        )
    )
    user: str | None = None
    seq, prev = 0, None
    for row in rows.fetchall():
        if row.user_id != user:
            user, seq, prev = row.user_id, 0, None
        seq += 1
        postings = sorted(legs.get(row.id, []), key=lambda leg: json.dumps(leg, sort_keys=True))
        own = _hash(
            {
                "schema": "salli.entry/1",
                "seq": seq,
                "prev_hash": prev,
                "id": row.id,
                "user_id": row.user_id,
                "entry_date": row.entry_date,
                "description": row.description,
                "source": row.source,
                "external_ref": row.external_ref,
                "reverses": row.reverses_id,
                "created_by": row.user_id,
                "created_via": "unrecorded",
                "postings": postings,
            }
        )
        conn.execute(
            sa.text(
                "UPDATE journal_entries SET seq = :seq, prev_hash = :prev, hash = :hash, "
                "created_by = user_id, created_via = 'unrecorded' WHERE id = :id"
            ),
            {"seq": seq, "prev": prev, "hash": own, "id": row.id},
        )
        prev = own


_CLOSED_BOOKS = """
    CREATE OR REPLACE FUNCTION refuse_entry_in_closed_books()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE locked DATE;
    BEGIN
        IF TG_OP = 'DELETE'
           AND current_setting('salli.erase_user', true) IS NOT NULL
           AND current_setting('salli.erase_user', true) = OLD.user_id THEN
            RETURN OLD;
        END IF;
        IF TG_OP <> 'INSERT' THEN
            SELECT lock_date INTO locked FROM user_profiles WHERE id = OLD.user_id;
            IF locked IS NOT NULL AND OLD.entry_date::date <= locked THEN
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
"""


def upgrade() -> None:
    # Accounts: the retained earnings role.
    op.add_column("accounts", sa.Column("equity_role", sa.String(length=30), nullable=True))
    op.create_check_constraint(
        "ck_accounts_equity_role",
        "accounts",
        "equity_role IS NULL OR (type = 'equity' AND equity_role = 'retained_earnings')",
    )
    op.create_index(
        "uq_accounts_user_equity_role",
        "accounts",
        ["user_id", "equity_role"],
        unique=True,
        postgresql_where=sa.text("equity_role IS NOT NULL"),
    )

    # Journal entries: the close's source, the reversal link, the author and
    # the chain.
    op.drop_constraint("ck_journal_entries_source", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_entries_source",
        "journal_entries",
        f"source IN ({_SOURCES},'year_end_close')",
    )
    op.add_column("journal_entries", sa.Column("reverses_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "journal_entries_reverses_id_fkey",
        "journal_entries",
        "journal_entries",
        ["reverses_id"],
        ["id"],
    )
    for name, kind in (
        ("created_by", sa.String(length=64)),
        ("created_via", sa.String(length=120)),
        ("seq", sa.BigInteger()),
        ("prev_hash", sa.String(length=80)),
        ("hash", sa.String(length=80)),
    ):
        op.add_column("journal_entries", sa.Column(name, kind, nullable=True))

    op.execute("ALTER TABLE journal_entries DISABLE TRIGGER trg_journal_entries_closed_books")
    op.execute("""
        UPDATE journal_entries r SET reverses_id = o.id
          FROM journal_entries o WHERE o.reversed_by = r.id
    """)
    _chain_existing_entries()
    op.execute("ALTER TABLE journal_entries ENABLE TRIGGER trg_journal_entries_closed_books")

    for name in ("created_by", "created_via", "seq", "hash"):
        op.alter_column("journal_entries", name, nullable=False)
    op.create_unique_constraint(
        "uq_journal_entries_user_seq", "journal_entries", ["user_id", "seq"]
    )
    op.create_index(
        "uq_journal_entries_reverses",
        "journal_entries",
        ["reverses_id"],
        unique=True,
        postgresql_where=sa.text("reverses_id IS NOT NULL"),
    )
    op.execute(_CLOSED_BOOKS)
    op.drop_constraint("journal_entries_reversed_by_fkey", "journal_entries", type_="foreignkey")
    op.drop_column("journal_entries", "reversed_by")

    # Nothing stored in the ledger changes, open books or closed.
    op.execute("""
        CREATE OR REPLACE FUNCTION refuse_ledger_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE owner TEXT;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF TG_TABLE_NAME = 'postings' THEN
                    SELECT user_id INTO owner FROM journal_entries WHERE id = OLD.entry_id;
                    -- Deleted with its entry, which passed the entry's check.
                    IF owner IS NULL THEN
                        RETURN OLD;
                    END IF;
                ELSE
                    owner := OLD.user_id;
                END IF;
                IF current_setting('salli.erase_user', true) IS NOT NULL
                   AND current_setting('salli.erase_user', true) = owner THEN
                    RETURN OLD;
                END IF;
            END IF;
            RAISE EXCEPTION
                'The ledger keeps every entry as posted: % on % is refused (post a reversal)',
                TG_OP, TG_TABLE_NAME;
        END;
        $$
    """)
    for table in ("journal_entries", "postings"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_unchanged
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION refuse_ledger_change()
        """)

    # Tax returns and their payments.
    op.create_table(
        "tax_returns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("region", sa.String(length=200), nullable=True),
        sa.Column("year", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("computation_id", sa.String(length=36), nullable=False),
        sa.Column("rule_set_version_id", sa.String(length=36), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=80), nullable=False),
        sa.Column("reference", sa.String(length=200), nullable=True),
        sa.Column("filed_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('draft','filed','amended')", name="ck_tax_returns_status"),
        sa.CheckConstraint(
            "status <> 'filed' OR filed_on IS NOT NULL", name="ck_tax_returns_filed_on"
        ),
        sa.CheckConstraint(
            "status <> 'amended' OR (reason IS NOT NULL AND supersedes_id IS NOT NULL)",
            name="ck_tax_returns_amendment",
        ),
        sa.ForeignKeyConstraint(["computation_id"], ["tax_computations.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["tax_returns.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supersedes_id", name="uq_tax_returns_supersedes"),
    )
    op.create_index(
        "uq_tax_returns_year_version",
        "tax_returns",
        ["user_id", "country", sa.text("coalesce(region, '')"), "year", "version"],
        unique=True,
    )
    op.create_table(
        "tax_return_payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("return_id", sa.String(length=36), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reference", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_minor > 0", name="ck_tax_return_payments_amount"),
        sa.ForeignKeyConstraint(["return_id"], ["tax_returns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tax_return_payments_return_id", "tax_return_payments", ["return_id"], unique=False
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION refuse_tax_return_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE'
               AND current_setting('salli.erase_user', true) IS NOT NULL
               AND current_setting('salli.erase_user', true) = OLD.user_id THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION
                'Tax returns are append-only: % on % is refused (record a new version)',
                TG_OP, TG_TABLE_NAME;
        END;
        $$
    """)
    for table in _APPEND_ONLY:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_append_only
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION refuse_tax_return_change()
        """)
        op.execute(f"""
            CREATE TRIGGER trg_{table}_no_truncate
                BEFORE TRUNCATE ON {table}
                FOR EACH STATEMENT
                EXECUTE FUNCTION refuse_tax_return_change()
        """)


def downgrade() -> None:
    for table in reversed(_APPEND_ONLY):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_truncate ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS refuse_tax_return_change()")
    op.drop_index("ix_tax_return_payments_return_id", table_name="tax_return_payments")
    op.drop_table("tax_return_payments")
    op.drop_index("uq_tax_returns_year_version", table_name="tax_returns")
    op.drop_table("tax_returns")

    for table in ("journal_entries", "postings"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_unchanged ON {table}")
    op.execute("DROP FUNCTION IF EXISTS refuse_ledger_change()")
    op.add_column("journal_entries", sa.Column("reversed_by", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "journal_entries_reversed_by_fkey",
        "journal_entries",
        "journal_entries",
        ["reversed_by"],
        ["id"],
    )
    op.execute("ALTER TABLE journal_entries DISABLE TRIGGER trg_journal_entries_closed_books")
    op.execute("""
        UPDATE journal_entries o SET reversed_by = r.id
          FROM journal_entries r WHERE r.reverses_id = o.id
    """)
    op.execute("UPDATE journal_entries SET source = 'system' WHERE source = 'year_end_close'")
    op.execute("ALTER TABLE journal_entries ENABLE TRIGGER trg_journal_entries_closed_books")
    op.drop_index("uq_journal_entries_reverses", table_name="journal_entries")
    op.drop_constraint("uq_journal_entries_user_seq", "journal_entries", type_="unique")
    for name in ("hash", "prev_hash", "seq", "created_via", "created_by"):
        op.drop_column("journal_entries", name)
    op.drop_constraint("journal_entries_reverses_id_fkey", "journal_entries", type_="foreignkey")
    op.drop_column("journal_entries", "reverses_id")
    op.drop_constraint("ck_journal_entries_source", "journal_entries", type_="check")
    op.create_check_constraint(
        "ck_journal_entries_source", "journal_entries", f"source IN ({_SOURCES})"
    )

    op.drop_index("uq_accounts_user_equity_role", table_name="accounts")
    op.drop_constraint("ck_accounts_equity_role", "accounts", type_="check")
    op.drop_column("accounts", "equity_role")
    # core_0030's closed-books function, with its reversed_by exception.
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
