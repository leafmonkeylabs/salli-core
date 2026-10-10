"""First-party OAuth clients: Salli's own CLI, known to the server.

Every OAuth client so far registered itself (RFC 7591), the `salli` CLI
included, so the server could not tell its own CLI from any other client that
calls itself "Salli CLI". Activating a tax rule set needs that distinction
(application/permissions.py): the user's own CLI may, another application or
an AI connector may not.

- `oauth_clients.first_party` (false for every existing client, and for every
  client that registers itself from now on);
- the CLI's client, `salli-cli`, seeded as first party: a public client (PKCE,
  no secret) whose only redirect is a loopback address, so a code issued to it
  can only reach a program on the user's own machine, or a device sign-in the
  user approves on the device page.

Reversible: the downgrade signs out every session of the seeded client before
removing it.

Revision ID: core_0011_first_party_clients
Revises: core_0010_tax_rule_sets
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0011_first_party_clients"
down_revision: str | None = "core_0010_tax_rule_sets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CLI_CLIENT_ID = "salli-cli"


def upgrade() -> None:
    op.add_column(
        "oauth_clients",
        sa.Column("first_party", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    # A plain INSERT: should a client with this id somehow exist already, the
    # migration fails rather than making an unknown client first party.
    op.execute(
        sa.text(
            "INSERT INTO oauth_clients (client_id, client_name, redirect_uris, first_party,"
            " created_at) VALUES (:id, 'Salli CLI', CAST(:uris AS jsonb), true, now())"
        ).bindparams(id=CLI_CLIENT_ID, uris='["http://127.0.0.1/callback"]')
    )


def downgrade() -> None:
    for sql in (
        "DELETE FROM oauth_refresh_tokens WHERE client_id = :id",
        "DELETE FROM oauth_access_tokens WHERE client_id = :id",
        "DELETE FROM oauth_authorization_codes WHERE client_id = :id",
        "DELETE FROM oauth_device_codes WHERE client_id = :id",
        "DELETE FROM oauth_clients WHERE client_id = :id",
    ):
        op.execute(sa.text(sql).bindparams(id=CLI_CLIENT_ID))
    op.drop_column("oauth_clients", "first_party")
