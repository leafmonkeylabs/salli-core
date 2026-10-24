"""Drafted transactions: a statement's kind.

A person's own automation (a bank's text message or email, handed to the app
by a shortcut) drafts transactions that wait for review as an import's do
(`POST /v1/statements/drafts`). They collect in one batch per account while
any of it waits, and a statement's `kind` tells such a batch ("drafts") from
an import of a file or a feed ("import", every statement before this).

Revision ID: core_0023_statement_drafts
Revises: core_0022_mobile_client
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0023_statement_drafts"
down_revision: str | None = "core_0022_mobile_client"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "statements",
        sa.Column("kind", sa.String(20), nullable=False, server_default="import"),
    )


def downgrade() -> None:
    op.drop_column("statements", "kind")
