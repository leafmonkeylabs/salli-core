"""The console's sign-in: OAuth grants, reuse detection and step-up.

C0 of the console (docs/design/console.md, section 2; decisions 3, 5, 6, 8):

- `oauth_grants`: one row per sign-in, carried through every refresh. Each
  access and refresh token now belongs to one (`grant_id`), so revoking a
  sign-in revokes the grant, a rotated refresh token presented again revokes
  its whole grant, and the list of sign-ins can show each one. A grant records
  `authenticated_at` (when the password was checked) and, for the console, an
  absolute `expires_at` (SALLI_CONSOLE_SIGN_IN_HOURS after the sign-in).
- `oauth_authorization_codes.authenticated_at` and
  `oauth_device_codes.authenticated_at`: when the person's password was
  checked to approve the code, which the grant takes.
- `oauth_clients.step_up_seconds`: how recent a first-party client's password
  check must be for its powerful permissions (`tax:activate`).
- The console's client, `salli-console`: first party, public (PKCE, no
  secret), its powerful permissions only within 300 seconds of the password
  check. Its one redirect, `{SALLI_PUBLIC_URL}/console/callback`, is computed
  from the setting and matched exactly, so none is stored.

Tokens issued before this get one grant per user, client and resource, as
signed in when the earliest of them was issued: they keep working.

Revision ID: core_0021_console_sign_in
Revises: core_0020_holding_account
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0021_console_sign_in"
down_revision: str | None = "core_0020_holding_account"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSOLE_CLIENT_ID = "salli-console"
TOKEN_TABLES = ("oauth_access_tokens", "oauth_refresh_tokens")


def upgrade() -> None:
    op.create_table(
        "oauth_grants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column(
            "client_id",
            sa.String(length=64),
            sa.ForeignKey("oauth_clients.client_id"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=200), nullable=False),
        sa.Column("resource", sa.String(length=500), nullable=True),
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oauth_grants_user_id", "oauth_grants", ["user_id"])

    for table in TOKEN_TABLES:
        op.add_column(table, sa.Column("grant_id", sa.String(length=36), nullable=True))

    # A grant for the tokens already issued: one per user, client and
    # resource, as the old revoke_client_grant treated them.
    op.execute(
        """
        INSERT INTO oauth_grants
            (id, user_id, client_id, scope, resource, authenticated_at, created_at)
        SELECT gen_random_uuid()::text, user_id, client_id, min(scope), resource,
               min(created_at), min(created_at)
        FROM (
            SELECT user_id, client_id, scope, resource, created_at FROM oauth_access_tokens
            UNION ALL
            SELECT user_id, client_id, scope, resource, created_at FROM oauth_refresh_tokens
        ) AS issued
        GROUP BY user_id, client_id, resource
        """
    )
    for table in TOKEN_TABLES:
        op.execute(
            f"""
            UPDATE {table} AS t SET grant_id = g.id
            FROM oauth_grants AS g
            WHERE g.user_id = t.user_id AND g.client_id = t.client_id
              AND g.resource IS NOT DISTINCT FROM t.resource
            """
        )
        op.alter_column(table, "grant_id", nullable=False)
        op.create_foreign_key(f"{table}_grant_id_fkey", table, "oauth_grants", ["grant_id"], ["id"])
        op.create_index(f"ix_{table}_grant_id", table, ["grant_id"])

    # Codes live for minutes; any waiting now is simply asked for again.
    op.execute("DELETE FROM oauth_authorization_codes")
    op.add_column(
        "oauth_authorization_codes",
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "oauth_device_codes",
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column("oauth_clients", sa.Column("step_up_seconds", sa.Integer(), nullable=True))
    # A plain INSERT, as core_0011's: should a client with this id somehow
    # exist already, the migration fails rather than making an unknown client
    # first party.
    op.execute(
        sa.text(
            "INSERT INTO oauth_clients (client_id, client_name, redirect_uris, first_party,"
            " step_up_seconds, created_at)"
            " VALUES (:id, 'Salli console', CAST('[]' AS jsonb), true, 300, now())"
        ).bindparams(id=CONSOLE_CLIENT_ID)
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
        op.execute(sa.text(sql).bindparams(id=CONSOLE_CLIENT_ID))
    op.drop_column("oauth_clients", "step_up_seconds")
    op.drop_column("oauth_device_codes", "authenticated_at")
    op.drop_column("oauth_authorization_codes", "authenticated_at")
    for table in TOKEN_TABLES:
        op.drop_index(f"ix_{table}_grant_id", table_name=table)
        op.drop_constraint(f"{table}_grant_id_fkey", table, type_="foreignkey")
        op.drop_column(table, "grant_id")
    op.drop_index("ix_oauth_grants_user_id", table_name="oauth_grants")
    op.drop_table("oauth_grants")
