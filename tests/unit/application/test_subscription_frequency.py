"""A subscription's frequency and due date are checked where they are stored,
whichever surface sends them: an unknown one broke every later report."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from salli.application.services.subscription_service import SubscriptionService
from salli.domain.subscription.models import normalize_due_date, normalize_frequency


def test_a_frequency_is_folded_to_its_known_spelling():
    assert normalize_frequency(" Monthly ") == "monthly"
    with pytest.raises(ValueError, match="Unknown frequency"):
        normalize_frequency("fortnightly")


def test_a_due_date_must_be_a_date():
    assert normalize_due_date("2026-10-09") == "2026-10-09"
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        normalize_due_date("10/09/2026")


def _service() -> tuple[SubscriptionService, dict[str, Any]]:
    stored: dict[str, Any] = {}

    class Subs:
        async def save(self, user_id, subscription):
            stored.update(subscription)
            return "s1"

        async def update(self, user_id, subscription_id, updates):
            stored.update(updates)

    class Profiles:
        async def base_currency(self, user_id):
            return "USD"

    @asynccontextmanager
    async def uow():
        yield SimpleNamespace(recurring_subscriptions=Subs(), user_profiles=Profiles())

    return SubscriptionService(uow), stored


async def test_the_service_stores_the_normalised_frequency_and_refuses_unknown_ones():
    service, stored = _service()
    data = {"name": "Netflix", "amount": "9.99", "next_due_date": "2026-11-01"}
    await service.add_subscription("u1", {**data, "frequency": "Monthly"})
    assert stored["frequency"] == "monthly"
    with pytest.raises(ValueError):
        await service.add_subscription("u1", {**data, "frequency": "every month"})
    with pytest.raises(ValueError):
        await service.update_subscription("u1", "s1", {"frequency": "Biannual"})
    with pytest.raises(ValueError):
        await service.update_subscription("u1", "s1", {"next_due_date": "soon"})
