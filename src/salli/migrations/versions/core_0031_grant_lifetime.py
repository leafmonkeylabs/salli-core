"""An AI client's connection ends: existing ones get the default lifetime.

A grant of any client but Salli's own (`oauth_clients.first_party`) now ends
MCP_GRANT_LIFETIME_DAYS after the person approved it. Grants started before
had no end; they are given the default, 90 days after their approval, so one
approved long ago is refused at its next refresh and the person reconnects.
No column changes: `oauth_grants.expires_at` is core_0021's.

Revision ID: core_0031_grant_lifetime
Revises: core_0030_lock_edits
Create Date: 2026-10-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "core_0031_grant_lifetime"
down_revision: str | None = "core_0030_lock_edits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_THIRD_PARTY = "client_id IN (SELECT client_id FROM oauth_clients WHERE NOT first_party)"


def upgrade() -> None:
    op.execute(
        "UPDATE oauth_grants SET expires_at = authenticated_at + interval '90 days'"
        f" WHERE expires_at IS NULL AND {_THIRD_PARTY}"
    )


def downgrade() -> None:
    op.execute(f"UPDATE oauth_grants SET expires_at = NULL WHERE {_THIRD_PARTY}")
