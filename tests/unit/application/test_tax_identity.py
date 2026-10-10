"""
Where a user is taxed, and their tax ids, through UserProfileService.

The legacy fields `ird_number` and `nic` are how the web and mobile apps write
Sri Lankan numbers. They now land in the tax ids ("LK-TIN", "LK-NIC"), the
`ird_number` column keeps mirroring the TIN, and a Sri Lankan number given to a
profile with no residency makes it LK, the rule migration core_0008 applied to
existing users.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest

from salli.application.services.onboarding_service import OnboardingService
from salli.application.services.user_profile_service import UserProfileService
from salli.domain.jurisdiction import InvalidTaxIdError, UnknownCountryError

pytestmark = pytest.mark.asyncio

USER = "u1"


class _Profiles:
    """The profile repository's tax-identity slice, over one stored row."""

    def __init__(self, **row: Any) -> None:
        self.row: dict[str, Any] = {
            "id": USER,
            "base_currency": "LKR",
            "tax_residency": None,
            "tax_ids": [],
            "ird_number": None,
            **row,
        }

    async def get(self, user_id: str) -> dict[str, Any] | None:
        return dict(self.row) if user_id == USER else None

    async def upsert(self, user_id: str, fields: dict[str, Any]) -> None:
        self.row.update({k: v for k, v in fields.items() if v is not None})

    async def set_tax_identity(self, user_id, *, tax_residency, tax_ids, ird_number) -> None:
        self.row.update(tax_residency=tax_residency, tax_ids=tax_ids, ird_number=ird_number)


def _service(**row: Any) -> tuple[UserProfileService, _Profiles]:
    profiles = _Profiles(**row)

    class _UoW:
        user_profiles = profiles

    @asynccontextmanager
    async def factory():
        yield _UoW()

    documents = AsyncMock()
    documents.get_memory.return_value = None
    return UserProfileService(factory, AsyncMock(), AsyncMock(), documents), profiles


async def test_an_ird_number_becomes_the_lk_tin_and_makes_the_user_sri_lankan():
    svc, profiles = _service()
    await svc.update_identity(USER, {"ird_number": " 123456789 "})
    assert profiles.row["tax_ids"] == [{"scheme": "LK-TIN", "value": "123456789"}]
    assert profiles.row["ird_number"] == "123456789"  # the column mirrors it
    assert profiles.row["tax_residency"] == "LK"


async def test_a_nic_becomes_the_lk_nic():
    svc, profiles = _service()
    await svc.update_identity(USER, {"nic": "200012345678"})
    assert profiles.row["tax_ids"] == [{"scheme": "LK-NIC", "value": "200012345678"}]
    assert profiles.row["tax_residency"] == "LK"


async def test_a_residency_the_user_gave_is_never_overridden():
    svc, profiles = _service(tax_residency="GB")
    await svc.update_identity(USER, {"ird_number": "123456789"})
    assert profiles.row["tax_residency"] == "GB"

    svc, profiles = _service()
    await svc.update_identity(USER, {"ird_number": "123456789", "tax_residency": "IN"})
    assert profiles.row["tax_residency"] == "IN"

    # Clearing it in the same request is honoured too.
    svc, profiles = _service(tax_residency="LK")
    await svc.update_identity(USER, {"ird_number": "123456789", "tax_residency": None})
    assert profiles.row["tax_residency"] is None


async def test_a_number_given_through_tax_ids_implies_no_residency():
    """Only the legacy fields carry the Sri Lankan rule; the new API is explicit."""
    svc, profiles = _service()
    await svc.update_identity(USER, {"tax_ids": [{"scheme": "LK-TIN", "value": "1"}]})
    assert profiles.row["tax_residency"] is None
    assert profiles.row["ird_number"] == "1"


async def test_tax_ids_replace_the_list_and_the_column_follows():
    svc, profiles = _service(
        tax_ids=[{"scheme": "LK-TIN", "value": "1"}, {"scheme": "LK-NIC", "value": "2"}],
        ird_number="1",
    )
    await svc.update_identity(USER, {"tax_ids": [{"scheme": "gb-utr", "value": "3"}]})
    assert profiles.row["tax_ids"] == [{"scheme": "GB-UTR", "value": "3"}]
    assert profiles.row["ird_number"] is None


async def test_a_blank_legacy_field_removes_its_number():
    svc, profiles = _service(tax_ids=[{"scheme": "LK-TIN", "value": "1"}], ird_number="1")
    await svc.update_identity(USER, {"ird_number": ""})
    assert profiles.row["tax_ids"] == []
    assert profiles.row["ird_number"] is None


async def test_a_number_only_the_column_held_survives_an_unrelated_change():
    """A server that predates tax ids writes only the column; changing the
    residency must not clear what it wrote."""
    svc, profiles = _service(ird_number="777")
    await svc.update_identity(USER, {"tax_residency": "lk"})
    assert profiles.row["tax_residency"] == "LK"
    assert profiles.row["tax_ids"] == [{"scheme": "LK-TIN", "value": "777"}]
    assert profiles.row["ird_number"] == "777"


async def test_nothing_is_written_when_something_does_not_validate():
    svc, profiles = _service()
    before = dict(profiles.row)
    with pytest.raises(UnknownCountryError):
        await svc.update_identity(USER, {"tax_residency": "XX", "ird_number": "1"})
    with pytest.raises(InvalidTaxIdError, match="disagree"):
        await svc.update_identity(
            USER,
            {"tax_ids": [{"scheme": "LK-TIN", "value": "1"}], "ird_number": "2"},
        )
    with pytest.raises(InvalidTaxIdError):
        await svc.update_identity(USER, {"tax_ids": [{"scheme": "TIN", "value": "1"}]})
    assert profiles.row == before


async def test_the_profile_reads_the_legacy_fields_from_the_tax_ids():
    svc, _ = _service(
        tax_residency="LK",
        tax_ids=[{"scheme": "LK-TIN", "value": "1"}, {"scheme": "LK-NIC", "value": "2"}, "bad"],
        ird_number="1",
    )
    profile = await svc.get_profile(USER)
    assert profile["tax_residency"] == "LK"
    assert profile["tax_ids"] == [
        {"scheme": "LK-TIN", "value": "1"},
        {"scheme": "LK-NIC", "value": "2"},
    ]
    assert (profile["ird_number"], profile["nic"]) == ("1", "2")


async def test_the_column_stands_in_for_a_missing_tin():
    svc, _ = _service(ird_number=" 555 ")
    profile = await svc.get_profile(USER)
    assert profile["ird_number"] == "555"
    assert profile["tax_ids"] == []


# ── Onboarding writes the numbers it collects ────────────────────────────────


def _onboarding() -> tuple[OnboardingService, AsyncMock]:
    documents, fi, ledger, profile = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    ledger.list_accounts.return_value = []
    profile.get_tax_residency.return_value = None
    return OnboardingService(documents, fi, ledger, profile), profile


async def test_onboarding_puts_the_numbers_and_the_residency_on_the_profile():
    svc, profile = _onboarding()
    await svc.complete(
        USER,
        {"name": "Asha", "ird_number": "123456789", "nic": "200012345678", "tax_residency": "LK"},
    )
    profile.update_identity.assert_awaited_once_with(
        USER, {"tax_residency": "LK", "ird_number": "123456789", "nic": "200012345678"}
    )


async def test_onboarding_keeps_a_number_it_cannot_store_as_a_memory_only():
    """The legacy flow always took any text: a NIC too long to be one must not
    fail the whole onboarding."""
    svc, profile = _onboarding()
    await svc.complete(USER, {"name": "Asha", "nic": "x" * 40})
    profile.update_identity.assert_not_awaited()


async def test_onboarding_without_tax_answers_leaves_the_profile_alone():
    svc, profile = _onboarding()
    await svc.complete(USER, {"name": "Asha"})
    profile.update_identity.assert_not_awaited()
