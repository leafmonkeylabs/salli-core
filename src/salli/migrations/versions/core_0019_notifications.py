"""Digests: a person's time zone, their digest preferences and the delivery log.

Phase 3d of the decision lab (docs/design/decision-lab-phase-3.md, section 4):

- `user_profiles.time_zone`: an IANA name, or NULL while the person has not
  said. Their digest goes at their own local hour, so turning it on needs one.
- `notification_preferences`: one row per person who has set any: on or off,
  weekly or monthly, the weekday, the local hour, and which kinds of item.
- `notification_deliveries`: the delivery log, one row per person and period
  at most (`uq_notification_deliveries_user_period`), which is what keeps a
  rerun of the job, or two servers running it, to one digest a period. It
  keeps the items (kinds, counts, dates) and the message's hash, never the
  message.

Nothing here says where a message goes: that is a deployment's notifier's,
in its own tables.

Revision ID: core_0019_notifications
Revises: core_0018_local_auth
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0019_notifications"
down_revision: str | None = "core_0018_local_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("time_zone", sa.String(length=64), nullable=True))

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("cadence", sa.String(length=10), nullable=False),
        sa.Column("weekday", sa.String(length=9), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "cadence in ('weekly', 'monthly')", name="ck_notification_preferences_cadence"
        ),
        sa.CheckConstraint(
            "weekday in ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', "
            "'saturday', 'sunday')",
            name="ck_notification_preferences_weekday",
        ),
        sa.CheckConstraint("hour between 0 and 23", name="ck_notification_preferences_hour"),
        sa.CheckConstraint(
            "jsonb_typeof(items) = 'array'", name="ck_notification_preferences_items"
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("period", sa.String(length=10), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hash", sa.String(length=71), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('sending', 'sent', 'no_destination', 'failed')",
            name="ck_notification_deliveries_status",
        ),
        sa.CheckConstraint("attempts between 1 and 3", name="ck_notification_deliveries_attempts"),
        sa.CheckConstraint(
            "hash ~ '^sha256:[0-9a-f]{64}$'", name="ck_notification_deliveries_hash"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(items) = 'array'", name="ck_notification_deliveries_items"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "period", name="uq_notification_deliveries_user_period"),
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("notification_preferences")
    op.drop_column("user_profiles", "time_zone")
