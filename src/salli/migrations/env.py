"""Alembic environment for Salli's own tables (version table `alembic_version`)."""

from alembic import context

from salli.adapters.db.models import Base
from salli.migrations.support import run_env

run_env(context, Base.metadata, version_table="alembic_version")
