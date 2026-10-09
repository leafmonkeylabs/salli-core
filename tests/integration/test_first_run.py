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


async def test_choosing_a_currency_never_creates_a_profile(uow_factory):
    # It created the missing profile, past ensure_user's may_create gate.
    from salli.application.ports import ProfileMissing

    profiles = _profiles(uow_factory)
    with pytest.raises(ProfileMissing):
        await profiles.set_base_currency("new-user", "eur")
    async with uow_factory() as uow:
        assert await uow.user_profiles.get("new-user") is None

    assert await profiles.ensure_user("new-user", None, may_create=True, base_currency="eur")
    assert await profiles.set_base_currency("new-user", "gbp") == "GBP"  # still empty


def _onboarding(uow_factory) -> tuple[OnboardingService, LedgerService]:
    ledger = LedgerService(uow_factory)
    documents = MagicMock()
    documents.save_memory = AsyncMock()
    return OnboardingService(documents, MagicMock(), ledger), ledger


async def test_onboarding_again_skips_a_starter_account_the_user_closed(uow_factory):
    onboarding, ledger = _onboarding(uow_factory)
    await _profiles(uow_factory).ensure_user("u1", None, may_create=True, base_currency="USD")
    await onboarding.complete("u1", {"name": "Sam"})
    [bank] = [a for a in await ledger.list_accounts("u1") if a.code == "1200"]
    await ledger.deactivate_account("u1", bank.id)

    again = await onboarding.complete("u1", {"name": "Sam"})
    assert "1200" in again["accounts_skipped"]
    assert again["accounts_created"] == []


async def test_two_onboardings_at_once_create_each_account_once(uow_factory):
    import asyncio

    onboarding, ledger = _onboarding(uow_factory)
    await _profiles(uow_factory).ensure_user("u2", None, may_create=True, base_currency="USD")
    first, second = await asyncio.gather(
        onboarding.complete("u2", {"name": "Sam"}), onboarding.complete("u2", {"name": "Sam"})
    )
    codes = sorted(a.code for a in await ledger.list_accounts("u2"))
    assert codes == sorted({c for c in codes})
    assert len(first["accounts_created"]) + len(second["accounts_created"]) == len(codes)


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
