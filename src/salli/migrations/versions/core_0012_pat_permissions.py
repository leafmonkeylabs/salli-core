"""Personal access tokens hold only the permissions they were made with.

Until now a personal access token carried `tax:activate` because it was a
token, and tokens are what people hand to scripts and agents. Now it holds
exactly what it stores (application/permissions.py):

- `personal_access_tokens.permissions`, a JSON array of permission names,
  empty by default. Every existing token gets none: one that should activate
  tax rule sets is made again, asking for it.

Reversible: the downgrade drops the column (tokens keep working; what they
may do is then decided as before).

Revision ID: core_0012_pat_permissions
Revises: core_0011_first_party_clients
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0012_pat_permissions"
down_revision: str | None = "core_0011_first_party_clients"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "personal_access_tokens",
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_personal_access_tokens_permissions",
        "personal_access_tokens",
        "jsonb_typeof(permissions) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_personal_access_tokens_permissions", "personal_access_tokens", type_="check"
    )
    op.drop_column("personal_access_tokens", "permissions")
