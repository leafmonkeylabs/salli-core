"""
Salli's database migrations, shipped inside the package so an installed Salli
can migrate its own database (`salli db upgrade`) without a source checkout.

This directory is an Alembic script directory as well as a Python package. An
extension that owns tables ships its own script directory and version table
(see `ExtensionSpec.migrations`); `salli db upgrade` runs Salli's first, then
each enabled extension's.
"""
