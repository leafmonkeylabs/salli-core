"""A new user's first steps, against a real database: a CLI user may be no
more than SALLI_USER_ID, with no profile row yet."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from salli.application.services.ledger_service import LedgerService
from salli.application.services.onboarding_service import OnboardingService
from salli.application.services.user_profile_service import UserProfileService
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres


def _profiles(uow_factory) -> UserProfileService:
    documents = MagicMock()
    documents.get_memory = AsyncMock(return_value={"content": "Sam Roe"})
    return UserProfileService(uow_factory, LedgerService(uow_factory), MagicMock(), documents)


async def test_choosing_a_currency_first_starts_the_profile_in_it(uow_factory):
    profiles = _profiles(uow_factory)
    assert await profiles.set_base_currency("new-user", "eur") == "EUR"
    assert await profiles.get_base_currency("new-user") == "EUR"


async def test_reading_a_profile_that_does_not_exist_creates_nothing(uow_factory):
    # It used to try to save legacy memories into a profile row it had to
    # create without a currency, and failed.
    profile = await _profiles(uow_factory).get_profile("ghost")
    assert profile["id"] == "ghost"
    async with uow_factory() as uow:
        assert await uow.user_profiles.get("ghost") is None


async def test_onboarding_without_a_profile_fails_loudly_not_with_zero_accounts(uow_factory):
    ledger = LedgerService(uow_factory)
    documents = MagicMock()
    documents.save_memory = AsyncMock()
    onboarding = OnboardingService(documents, MagicMock(), ledger)
    with pytest.raises(LookupError, match="has no profile"):
        await onboarding.complete("nobody", {"name": "No One"})
