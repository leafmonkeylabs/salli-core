"""
Account deletion reaches extensions' tables, inside the same session.

An extension's per-user rows (salli/extensions.py) are deleted by its own
purger, but they must go in the same transaction as Salli's: a purger that
committed separately could leave a half-deleted account behind.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from salli.adapters.db.repositories import SQLDataPortabilityRepository

pytestmark = pytest.mark.asyncio


class _FakeSession:
    async def execute(self, statement):
        return SimpleNamespace(rowcount=0)


async def test_purgers_run_in_the_same_session_and_report_their_counts():
    session = _FakeSession()
    seen = []

    async def purge(s, user_id):
        seen.append((s, user_id))
        return {"extension_table": 3}

    counts = await SQLDataPortabilityRepository(session, [purge]).delete_all("u1")

    assert seen == [(session, "u1")]
    assert counts["extension_table"] == 3
    assert "user_profiles" in counts  # Salli's own deletion still ran


async def test_a_failing_purger_fails_the_deletion():
    """So the unit of work rolls the whole thing back rather than committing
    Salli's half."""

    async def purge(s, user_id):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await SQLDataPortabilityRepository(_FakeSession(), [purge]).delete_all("u1")


async def test_no_extensions_means_no_purgers():
    counts = await SQLDataPortabilityRepository(_FakeSession()).delete_all("u1")
    assert "user_profiles" in counts
