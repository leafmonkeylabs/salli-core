"""Two-step sign-in: a code from an authenticator app after the password.

`logins` takes the app's secret (sealed with the key ring, and the version
that sealed it), when two-step sign-in was turned on (NULL while the person
is still proving a code, or when it is off), the time step of the last code
used, and the recovery codes' SHA-256 hashes.

Revision ID: core_0027_totp
Revises: core_0026_savings_role
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0027_totp"
down_revision: str | None = "core_0026_savings_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("logins", sa.Column("totp_secret", sa.Text(), nullable=True))
    op.add_column("logins", sa.Column("totp_key_version", sa.Integer(), nullable=True))
    op.add_column("logins", sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("logins", sa.Column("totp_last_step", sa.BigInteger(), nullable=True))
    op.add_column(
        "logins",
        sa.Column(
            "totp_recovery_codes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_check_constraint(
        "ck_logins_totp",
        "logins",
        "(totp_secret IS NULL) = (totp_key_version IS NULL)"
        " AND (totp_enabled_at IS NULL OR totp_secret IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_logins_totp", "logins", type_="check")
    for column in (
        "totp_recovery_codes",
        "totp_last_step",
        "totp_enabled_at",
        "totp_key_version",
        "totp_secret",
    ):
        op.drop_column("logins", column)
