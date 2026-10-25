"""A hash-chained audit trail that erasure pseudonymises instead of deleting.

- `audit_logs.seq`, `prev_hash`, `body_hash`, `hash`: one chain over every
  row on the instance (domain/audit_chain.py). The rows stored before are
  chained here in the order they were stored.
- The append-only trigger (core_0028's) now refuses every DELETE. While an
  account is erased (`salli.erase_user`, and `salli.erase_also`: the hashes
  its failed sign-ins were logged by) it allows an UPDATE of that account's
  rows that only replaces the user id with a pseudonym (`erased:`) and
  empties the arguments.

Revision ID: core_0046_audit_chain
Revises: core_0045_mcp_client_refs
Create Date: 2026-10-25
"""

from collections.abc import Sequence
from datetime import UTC

import sqlalchemy as sa
from alembic import op

from salli.domain import audit_chain

revision: str = "core_0046_audit_chain"
down_revision: str | None = "core_0045_mcp_client_refs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in ("prev_hash", "body_hash", "hash"):
        op.add_column("audit_logs", sa.Column(name, sa.String(80), nullable=True))
    op.add_column("audit_logs", sa.Column("seq", sa.BigInteger(), nullable=True))

    # Chaining the rows already there updates them: the trigger steps aside.
    op.execute("ALTER TABLE audit_logs DISABLE TRIGGER trg_audit_logs_append_only")
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, user_id, action, params, decision, client_id, created_at"
            " FROM audit_logs ORDER BY created_at, id"
        )
    ).all()
    prev = None
    for seq, r in enumerate(rows, start=1):
        body = audit_chain.body_hash(r.user_id, r.params or {})
        own = audit_chain.row_hash(
            seq=seq,
            prev_hash=prev,
            row_id=r.id,
            action=r.action,
            decision=r.decision,
            client_id=r.client_id,
            created_at=r.created_at.astimezone(UTC).isoformat(),
            body=body,
        )
        bind.execute(
            sa.text(
                "UPDATE audit_logs SET seq = :seq, prev_hash = :prev, body_hash = :body,"
                " hash = :hash WHERE id = :id"
            ),
            {"seq": seq, "prev": prev, "body": body, "hash": own, "id": r.id},
        )
        prev = own
    op.execute("ALTER TABLE audit_logs ENABLE TRIGGER trg_audit_logs_append_only")

    for name in ("seq", "body_hash", "hash"):
        op.alter_column("audit_logs", name, nullable=False)
    op.create_unique_constraint("uq_audit_logs_seq", "audit_logs", ["seq"])

    op.execute("""
        CREATE OR REPLACE FUNCTION refuse_audit_log_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE'
               AND current_setting('salli.erase_user', true) IS NOT NULL
               AND (OLD.user_id = current_setting('salli.erase_user', true)
                    OR OLD.user_id = ANY (string_to_array(
                        coalesce(current_setting('salli.erase_also', true), ''), ',')))
               AND NEW.user_id LIKE 'erased:%'
               AND NEW.params = '{}'::jsonb
               AND (NEW.id, NEW.action, NEW.decision, NEW.client_id, NEW.created_at,
                    NEW.seq, NEW.prev_hash, NEW.body_hash, NEW.hash)
                   IS NOT DISTINCT FROM
                   (OLD.id, OLD.action, OLD.decision, OLD.client_id, OLD.created_at,
                    OLD.seq, OLD.prev_hash, OLD.body_hash, OLD.hash) THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'The audit log is append-only: % on % is refused',
                TG_OP, TG_TABLE_NAME;
        END;
        $$
    """)


def downgrade() -> None:
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
    op.drop_constraint("uq_audit_logs_seq", "audit_logs")
    for name in ("seq", "hash", "body_hash", "prev_hash"):
        op.drop_column("audit_logs", name)
