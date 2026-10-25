"""The CLI's and the phone app's sign-ins end: existing ones get the default.

A grant of `salli-cli` or `salli-mobile` now ends SALLI_APP_SIGN_IN_DAYS
after its password was checked, as the console's and an AI client's do.
Grants started before had no end; they are given the default, 90 days after
their sign-in, so one from long ago is refused at its next refresh and the
person signs in again. No column changes.

Revision ID: core_0050_app_grant_lifetime
Revises: core_0049_push_preferences
Create Date: 2026-10-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "core_0050_app_grant_lifetime"
down_revision: str | None = "core_0049_push_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APPS = "client_id IN ('salli-cli', 'salli-mobile')"


def upgrade() -> None:
    op.execute(
        "UPDATE oauth_grants SET expires_at = authenticated_at + interval '90 days'"
        f" WHERE expires_at IS NULL AND {_APPS}"
    )


def downgrade() -> None:
    op.execute(f"UPDATE oauth_grants SET expires_at = NULL WHERE {_APPS}")
