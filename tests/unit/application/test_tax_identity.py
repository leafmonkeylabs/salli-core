"""
Where a user is taxed, and their tax ids, through UserProfileService and
onboarding.

Tax ids are generic only: `{scheme, value}`, the scheme "XX-KIND". Salli knows
no country's schemes, and neither a tax id nor a currency ever implies a tax
residency: the residency is only what the user said.
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
            "base_currency": "EUR",
            "tax_residency": None,
            "tax_ids": [],
            **row,
        }

    async def get(self, user_id: str) -> dict[str, Any] | None:
        return dict(self.row) if user_id == USER else None

    async def upsert(self, user_id: str, fields: dict[str, Any]) -> None:
        self.row.update({k: v for k, v in fields.items() if v is not None})

    async def set_tax_identity(self, user_id, *, tax_residency, tax_ids) -> None:
        self.row.update(tax_residency=tax_residency, tax_ids=tax_ids)


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


async def test_tax_ids_are_stored_generically_and_imply_no_residency():
    svc, profiles = _service()
    await svc.update_identity(
        USER,
        {"tax_ids": [{"scheme": "ke-pin", "value": " A001 "}, {"scheme": "DE-IDNR", "value": "7"}]},
    )
    assert profiles.row["tax_ids"] == [
        {"scheme": "KE-PIN", "value": "A001"},
        {"scheme": "DE-IDNR", "value": "7"},
    ]
    assert profiles.row["tax_residency"] is None


async def test_the_residency_is_only_what_the_user_said():
    svc, profiles = _service()
    await svc.update_identity(USER, {"tax_residency": "nz"})
    assert profiles.row["tax_residency"] == "NZ"

    # Clearing it is honoured, and leaves the tax ids alone.
    svc, profiles = _service(tax_residency="NZ", tax_ids=[{"scheme": "NZ-X", "value": "1"}])
    await svc.update_identity(USER, {"tax_residency": None})
    assert profiles.row["tax_residency"] is None
    assert profiles.row["tax_ids"] == [{"scheme": "NZ-X", "value": "1"}]


async def test_tax_ids_replace_the_list():
    svc, profiles = _service(
        tax_ids=[{"scheme": "BR-CPF", "value": "1"}, {"scheme": "BR-X", "value": "2"}]
    )
    await svc.update_identity(USER, {"tax_ids": [{"scheme": "gb-utr", "value": "3"}]})
    assert profiles.row["tax_ids"] == [{"scheme": "GB-UTR", "value": "3"}]

    await svc.update_identity(USER, {"tax_ids": []})
    assert profiles.row["tax_ids"] == []


async def test_an_unrelated_change_keeps_the_tax_ids():
    svc, profiles = _service(tax_ids=[{"scheme": "JP-MN", "value": "9"}])
    await svc.update_identity(USER, {"tax_residency": "JP"})
    assert profiles.row["tax_ids"] == [{"scheme": "JP-MN", "value": "9"}]


async def test_the_legacy_fields_are_gone():
    """`ird_number` and `nic` were one country's numbers: they are no longer
    read, written or served."""
    svc, profiles = _service()
    await svc.update_identity(USER, {"ird_number": "123456789", "nic": "200012345678"})
    assert profiles.row["tax_ids"] == []
    assert profiles.row["tax_residency"] is None
    profile = await svc.get_profile(USER)
    assert "ird_number" not in profile
    assert "nic" not in profile


async def test_nothing_is_written_when_something_does_not_validate():
    svc, profiles = _service()
    before = dict(profiles.row)
    with pytest.raises(UnknownCountryError):
        await svc.update_identity(
            USER, {"tax_residency": "XX", "tax_ids": [{"scheme": "FR-SPI", "value": "1"}]}
        )
    with pytest.raises(InvalidTaxIdError, match="more than once"):
        await svc.update_identity(
            USER,
            {"tax_ids": [{"scheme": "FR-SPI", "value": "1"}, {"scheme": "fr-spi", "value": "2"}]},
        )
    with pytest.raises(InvalidTaxIdError):
        await svc.update_identity(USER, {"tax_ids": [{"scheme": "TIN", "value": "1"}]})
    assert profiles.row == before


async def test_the_profile_reads_clean_tax_ids():
    svc, _ = _service(
        tax_residency="MX",
        tax_ids=[{"scheme": "MX-RFC", "value": "1"}, {"scheme": "MX-CURP", "value": "2"}, "bad"],
    )
    profile = await svc.get_profile(USER)
    assert profile["tax_residency"] == "MX"
    assert profile["tax_ids"] == [
        {"scheme": "MX-RFC", "value": "1"},
        {"scheme": "MX-CURP", "value": "2"},
    ]


# ── Onboarding asks for both explicitly ──────────────────────────────────────


def _onboarding() -> tuple[OnboardingService, AsyncMock, AsyncMock]:
    documents, fi, ledger, profile = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    ledger.list_accounts.return_value = []
    documents.get_memory.return_value = None
    return OnboardingService(documents, fi, ledger, profile), profile, documents


async def test_onboarding_puts_the_residency_and_tax_ids_on_the_profile():
    svc, profile, documents = _onboarding()
    await svc.complete(
        USER,
        {
            "name": "Asha",
            "tax_residency": "ca",
            "tax_ids": [{"scheme": "ca-sin", "value": "123 456 789"}],
        },
    )
    profile.update_identity.assert_awaited_once_with(
        USER,
        {"tax_residency": "CA", "tax_ids": [{"scheme": "CA-SIN", "value": "123 456 789"}]},
    )
    # Tax ids live on the profile only, never as memories.
    slugs = {call.kwargs["slug"] for call in documents.save_memory.await_args_list}
    assert not slugs & {"ird_number", "nic_number", "tax_ids"}


async def test_onboarding_refuses_a_bad_tax_id_before_saving_anything():
    svc, profile, documents = _onboarding()
    with pytest.raises(InvalidTaxIdError):
        await svc.complete(USER, {"name": "Asha", "tax_ids": [{"scheme": "TIN", "value": "1"}]})
    with pytest.raises(UnknownCountryError):
        await svc.complete(USER, {"name": "Asha", "tax_residency": "XX"})
    profile.update_identity.assert_not_awaited()
    documents.save_memory.assert_not_awaited()


async def test_onboarding_without_tax_answers_leaves_the_profile_alone():
    svc, profile, _ = _onboarding()
    await svc.complete(USER, {"name": "Asha"})
    profile.update_identity.assert_not_awaited()
