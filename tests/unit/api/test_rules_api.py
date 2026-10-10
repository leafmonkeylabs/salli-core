"""/v1/rules over HTTP."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from salli.domain.rules.engine import InvalidRule
from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio

_NOW = datetime(2026, 10, 9, tzinfo=UTC)
_RULE = {
    "id": "r1",
    "name": "Uber",
    "priority": 100,
    "match_all": True,
    "enabled": True,
    "conditions": [{"field": "description", "operator": "contains", "value": "uber"}],
    "actions": {"account_id": "transport"},
    "hits": 4,
    "last_hit_at": _NOW,
    "created_at": _NOW,
    "updated_at": _NOW,
}
_DRAFT = {
    "name": "Uber",
    "conditions": [{"field": "description", "operator": "contains", "value": "uber"}],
    "actions": {"account_id": "transport"},
}


@pytest.fixture
def rules(mock_services):
    mock_services.rules = AsyncMock()
    return mock_services.rules


async def test_rules_are_listed_in_full(client, rules):
    rules.list.return_value = [_RULE]
    body = (await client.get("/v1/rules", headers=AUTH)).json()
    assert body[0]["conditions"][0]["value"] == "uber" and body[0]["hits"] == 4


async def test_a_rule_is_created(client, rules):
    rules.create.return_value = "r9"
    r = await client.post("/v1/rules", json=_DRAFT, headers=AUTH)
    assert (r.status_code, r.json()) == (201, {"id": "r9"})


async def test_an_invalid_rule_is_a_422_that_says_why(client, rules):
    rules.create.side_effect = InvalidRule("The rule's account doesn't exist or isn't active")
    r = await client.post("/v1/rules", json=_DRAFT, headers=AUTH)
    assert r.status_code == 422 and "account" in r.json()["detail"]


async def test_an_unknown_operator_never_reaches_the_service(client, rules):
    bad = {
        **_DRAFT,
        "conditions": [{"field": "description", "operator": "sounds_like", "value": "x"}],
    }
    assert (await client.post("/v1/rules", json=bad, headers=AUTH)).status_code == 422
    rules.create.assert_not_called()


async def test_testing_and_suggestions(client, rules):
    rules.test.return_value = {
        "total": 1,
        "agreeing": 0,
        "matches": [
            {
                "entry_id": "e1",
                "entry_date": "2026-10-01",
                "description": "UBER *TRIP",
                "amount": "12.00",
                "currency": "USD",
                "direction": "out",
                "account_id": "food",
            }
        ],
    }
    r = await client.post("/v1/rules/test", json=_DRAFT, headers=AUTH)
    assert r.status_code == 200 and r.json()["matches"][0]["amount"] == "12.00"

    rules.suggestions.return_value = [
        {**_DRAFT, "support": 3, "agreement": 3, "examples": ["UBER"]}
    ]
    r = await client.get("/v1/rules/suggestions", headers=AUTH)
    assert r.status_code == 200 and r.json()[0]["support"] == 3


async def test_a_missing_rule_is_a_404(client, rules):
    rules.get.return_value = None
    rules.update.return_value = False
    rules.delete.return_value = False
    assert (await client.get("/v1/rules/x", headers=AUTH)).status_code == 404
    assert (
        await client.patch("/v1/rules/x", json={"priority": 1}, headers=AUTH)
    ).status_code == 404
    assert (await client.delete("/v1/rules/x", headers=AUTH)).status_code == 404
