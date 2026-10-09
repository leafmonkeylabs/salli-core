"""Sign-in for clients that are not a browser: device codes and personal tokens.

`oauth_device_codes` holds pending device authorizations (RFC 8628), so a CLI
on a machine without a browser can be approved from a phone.
`personal_access_tokens` holds hashed long-lived tokens for scripts and CI.

Both tables are new and empty; nothing existing changes.

Revision ID: core_0003_client_auth
Revises: core_0002_base_currency
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0003_client_auth"
down_revision: str | None = "core_0002_base_currency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_device_codes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_code_hash", sa.String(length=64), nullable=False),
        sa.Column("user_code", sa.String(length=16), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=200), nullable=False),
        sa.Column("resource", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','approved','denied','consumed')",
            name="ck_oauth_device_codes_status",
        ),
        sa.ForeignKeyConstraint(["client_id"], ["oauth_clients.client_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_code_hash"),
        sa.UniqueConstraint("user_code"),
    )
    op.create_table(
        "personal_access_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_personal_access_tokens_user_id", "personal_access_tokens", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_personal_access_tokens_user_id", table_name="personal_access_tokens")
    op.drop_table("personal_access_tokens")
    op.drop_table("oauth_device_codes")
