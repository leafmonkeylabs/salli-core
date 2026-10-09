"""Updating something that does not exist is a 404, not a 200 that changed nothing."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.unit.api.conftest import AUTH

CASES = [
    # (service, getter, updater, path, body)
    ("debt", "get_debt", "update_debt", "/v1/debt/nope", {"name": "x"}),
    ("budget", "get_budget", "update_budget", "/v1/budget/nope", {"period_end": "2026-12-31"}),
    ("portfolio", "get_holding", "update_holding", "/v1/portfolio/nope", {"name": "x"}),
    (
        "subscription",
        "get_subscription",
        "update_subscription",
        "/v1/subscriptions/nope",
        {"name": "x"},
    ),
    ("insurance", "get_policy", "update_policy", "/v1/insurance/policies/nope", {"name": "x"}),
    ("fi", "list_goals", "update_goal", "/v1/fi/goals/nope", {"name": "x"}),
]


@pytest.mark.parametrize(("service", "getter", "updater", "path", "body"), CASES)
async def test_updating_a_missing_item_is_not_found(
    client, mock_services, service, getter, updater, path, body
):
    svc = AsyncMock()
    getattr(svc, getter).return_value = [] if getter == "list_goals" else None
    setattr(mock_services, service, svc)

    r = await client.patch(path, json=body, headers=AUTH)

    assert r.status_code == 404
    getattr(svc, updater).assert_not_awaited()
