"""A CLI command may call asyncio.run more than once with the same services.
A pooled asyncpg connection is bound to the loop that opened it, so the second
run failed with "attached to a different loop"."""

from __future__ import annotations

import asyncio

from salli.config import Settings
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres


def test_cli_services_survive_a_second_event_loop(db, monkeypatch):
    from salli.interfaces.cli import support

    monkeypatch.setattr("salli.config.get_settings", lambda: Settings(database_url=db))
    svc = support.services()
    assert asyncio.run(svc.tokens.list("u1")) == []
    assert asyncio.run(svc.tokens.list("u1")) == []  # a new loop, the same services
