"""A base currency per user.

Every posting is measured in its owner's base currency (Posting.fx_rate converts
into it). Until now that was LKR for everyone, written into the code rather than
stored. This makes it a column on the profile.

Existing profiles get LKR, which is what their data was always measured in, so
nothing about them changes. The default is then dropped: a new profile must name
its currency explicitly (UserProfileService.ensure_user does), so no one is
silently put on LKR again.

Anyone who owns data but has no profile row yet (their data predates profiles,
and they have not signed in since) gets an LKR profile here too. Otherwise their
first request after this release would create a profile in the deployment's
default currency, and every amount they had would be read in the wrong one.

Revision ID: core_0002_base_currency
Revises: core_0001_baseline
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0002_base_currency"
down_revision: str | None = "core_0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Tables whose rows belong to a user and hold money or the ledger itself.
_DATA_TABLES = (
    "accounts",
    "journal_entries",
    "budgets",
    "debts",
    "holdings",
    "recurring_subscriptions",
    "policies",
    "insurance_targets",
    "fi_goals",
    "statements",
)


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("base_currency", sa.String(length=3), nullable=False, server_default="LKR"),
    )
    owners = " UNION ".join(f"SELECT user_id FROM {table}" for table in _DATA_TABLES)
    op.execute(
        "INSERT INTO user_profiles"
        " (id, base_currency, mcp_enabled, daily_briefing_enabled, created_at, updated_at)"
        f" SELECT owner.user_id, 'LKR', false, false, now(), now() FROM ({owners}) AS owner"
        " WHERE NOT EXISTS (SELECT 1 FROM user_profiles p WHERE p.id = owner.user_id)"
    )
    op.alter_column("user_profiles", "base_currency", server_default=None)
    op.create_check_constraint(
        "ck_user_profiles_base_currency", "user_profiles", "base_currency ~ '^[A-Z]{3}$'"
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_profiles_base_currency", "user_profiles", type_="check")
    op.drop_column("user_profiles", "base_currency")
