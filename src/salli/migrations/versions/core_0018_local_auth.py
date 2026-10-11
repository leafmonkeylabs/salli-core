"""Salli's own sign-in: logins, sessions and failed attempts.

Salli no longer leans on an outside auth service: it keeps its own accounts
(decision D13, docs/self-host.md), so signing in needs nothing but Postgres.

- `logins`: one per user, keyed by the profile's id (cascading with it): the
  email they sign in with (lower-cased, unique), an argon2id hash of their
  password, when it last changed, and whether they own the instance (at most
  one does).
- `login_sessions`: the sessions a sign-in starts, stored as SHA-256 hashes
  of their tokens, each with an expiry and, once ended, when it was revoked.
- `login_failures`: failed sign-ins by a hash of the email or address tried,
  for throttling.

There are no real users yet, so nothing is carried over from the auth
service an instance used before: its owner runs `salli-server setup` again.

Revision ID: core_0018_local_auth
Revises: core_0017_decision_journal
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0018_local_auth"
down_revision: str | None = "core_0017_decision_journal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "logins",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_owner", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("email = lower(email)", name="ck_logins_email_lower"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("uq_logins_email", "logins", ["email"], unique=True)
    op.create_index(
        "uq_logins_owner",
        "logins",
        ["is_owner"],
        unique=True,
        postgresql_where=sa.text("is_owner"),
    )

    op.create_table(
        "login_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["logins.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_login_sessions_user_id", "login_sessions", ["user_id"])

    op.create_table(
        "login_failures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_failures_key_at", "login_failures", ["key_hash", "at"])


def downgrade() -> None:
    op.drop_index("ix_login_failures_key_at", table_name="login_failures")
    op.drop_table("login_failures")
    op.drop_index("ix_login_sessions_user_id", table_name="login_sessions")
    op.drop_table("login_sessions")
    op.drop_index("uq_logins_owner", table_name="logins")
    op.drop_index("uq_logins_email", table_name="logins")
    op.drop_table("logins")
