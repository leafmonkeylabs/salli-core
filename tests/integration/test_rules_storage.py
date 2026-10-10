"""Categorisation rules in a real database."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

RULE = {
    "name": "Uber",
    "priority": 10,
    "match_all": True,
    "enabled": True,
    "conditions": [{"field": "description", "operator": "contains", "value": "uber"}],
    "actions": {"account_id": "transport", "need": "essential"},
}


async def test_a_rule_round_trips_and_counts_its_hits(uow_factory):
    async with uow_factory() as uow:
        rule_id = await uow.rules.save("u1", RULE)
    async with uow_factory() as uow:
        await uow.rules.record_hits("u1", {rule_id: 3}, datetime.now(UTC))
        assert await uow.rules.update("u1", rule_id, {"priority": 5})
        assert await uow.rules.get("u2", rule_id) is None  # another user's
    async with uow_factory() as uow:
        [row] = await uow.rules.list("u1")
    assert row["conditions"] == RULE["conditions"]
    assert row["actions"] == RULE["actions"]
    assert (row["priority"], row["hits"]) == (5, 3)
    async with uow_factory() as uow:
        assert await uow.rules.delete("u1", rule_id)
        assert await uow.rules.list("u1") == []
