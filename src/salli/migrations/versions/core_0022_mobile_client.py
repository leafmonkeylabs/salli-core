"""The phone app's sign-in: Salli's third first-party client.

`salli-mobile` is the free Salli app for iPhone and Android, a client of the
API like the CLI and the console (docs/design/mobile.md):

- first party, public (PKCE, no secret), signed in only on Salli's own page
  with the person's password;
- its one redirect is a native app's private-use URI scheme (RFC 8252,
  section 7.1), `money.salli.app:/oauth/callback`, the reverse of the
  salli.money domain, stored and matched exactly;
- its powerful permissions (`tax:activate`) only within 300 seconds of the
  password check, as the console's;
- no absolute lifetime: a sign-in on a phone lasts while its refresh token
  keeps rotating, and ends as every grant does (signing out, revoking it in
  the sign-ins list, a reused refresh token).

Revision ID: core_0022_mobile_client
Revises: core_0021_console_sign_in
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0022_mobile_client"
down_revision: str | None = "core_0021_console_sign_in"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MOBILE_CLIENT_ID = "salli-mobile"
MOBILE_REDIRECT_URI = "money.salli.app:/oauth/callback"


def upgrade() -> None:
    # A plain INSERT, as core_0011's and core_0021's: should a client with
    # this id somehow exist already, the migration fails rather than making
    # an unknown client first party.
    op.execute(
        sa.text(
            "INSERT INTO oauth_clients (client_id, client_name, redirect_uris, first_party,"
            " step_up_seconds, created_at)"
            " VALUES (:id, 'Salli app', CAST(:redirects AS jsonb), true, 300, now())"
        ).bindparams(id=MOBILE_CLIENT_ID, redirects=f'["{MOBILE_REDIRECT_URI}"]')
    )


def downgrade() -> None:
    for sql in (
        "DELETE FROM oauth_refresh_tokens WHERE client_id = :id",
        "DELETE FROM oauth_access_tokens WHERE client_id = :id",
        "DELETE FROM oauth_authorization_codes WHERE client_id = :id",
        "DELETE FROM oauth_device_codes WHERE client_id = :id",
        "DELETE FROM oauth_grants WHERE client_id = :id",
        "DELETE FROM oauth_clients WHERE client_id = :id",
    ):
        op.execute(sa.text(sql).bindparams(id=MOBILE_CLIENT_ID))
