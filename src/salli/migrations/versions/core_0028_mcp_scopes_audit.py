"""An audit trail of AI connections' writes, and a client_ref that books once.

- `audit_logs.client_id`: the OAuth client of the MCP connection that asked
  for a write. Every MCP write records the person, the client, the tool, its
  arguments and the outcome (succeeded, refused, failed).
- `audit_logs` is append-only: a trigger refuses UPDATE, DELETE and TRUNCATE,
  except deleting a user's own rows while their account is erased, in a
  transaction with `set_config('salli.erase_user', <user id>, true)` (as
  core_0017 does for the decision journal).
- `uq_journal_entries_client_ref`: a manual entry's client_ref (its
  external_ref after "client-ref:") is unique per user, so two retries sent
  at once book one entry.

Revision ID: core_0028_mcp_scopes_audit
Revises: core_0027_totp
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0028_mcp_scopes_audit"
down_revision: str | None = "core_0027_totp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("client_id", sa.String(length=64), nullable=True))
    op.create_index(
        "uq_journal_entries_client_ref",
        "journal_entries",
        ["user_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("source = 'manual' AND external_ref LIKE 'client-ref:%'"),
    )

    # Autogenerate cannot see triggers; asyncpg needs each statement in its
    # own execute().
    op.execute("""
        CREATE OR REPLACE FUNCTION refuse_audit_log_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE'
               AND current_setting('salli.erase_user', true) IS NOT NULL
               AND current_setting('salli.erase_user', true) = OLD.user_id THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'The audit log is append-only: % on % is refused',
                TG_OP, TG_TABLE_NAME;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_logs_append_only
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION refuse_audit_log_change()
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_logs_no_truncate
            BEFORE TRUNCATE ON audit_logs
            FOR EACH STATEMENT
            EXECUTE FUNCTION refuse_audit_log_change()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_no_truncate ON audit_logs")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS refuse_audit_log_change()")
    op.drop_index("uq_journal_entries_client_ref", table_name="journal_entries")
    op.drop_column("audit_logs", "client_id")
