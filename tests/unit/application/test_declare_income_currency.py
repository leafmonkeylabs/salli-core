"""
Declared income keeps the currency it was earned in.

`declare_income` used to hardcode "LKR" on both postings, so a foreign
remittance declared during onboarding was booked at face value in rupees: a
$2,000 month became Rs. 2,000. That is a ~300x understatement of income, and it
flows straight into the FI projection and the tax estimate, which is why this is
pinned rather than left to a manual check.

It also used to book the amount at a rate of 1 when no rate could be found.
That is the same understatement by another route, so now there is no rate of 1
for a foreign amount: the caller's own rate, the published one, or an error.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from salli.application.ports import FxQuote, FxUnavailableError
from salli.application.services.user_profile_service import UserProfileService

USER = "user-1"


def _service(fx=None, base: str = "LKR") -> tuple[UserProfileService, AsyncMock]:
    ledger = MagicMock()
    ledger.base_currency = AsyncMock(return_value=base)
    ledger.list_accounts = AsyncMock(return_value=[])
    ledger.add_account = AsyncMock(side_effect=lambda *a, **k: f"acct-{k.get('code', 'x')}")
    ledger.add_entry = AsyncMock(return_value="entry-1")
    svc = UserProfileService(
        uow_factory=MagicMock(),
        ledger_service=ledger,
        fi_service=MagicMock(),
        document_service=MagicMock(),
        fx_service=fx,
    )
    return svc, ledger


def _fx(rate: str, source: str = "ecb") -> MagicMock:
    fx = MagicMock()
    fx.rate = AsyncMock(return_value=FxQuote(rate=Decimal(rate), source=source, as_of="2026-10-09"))
    return fx


def _postings(ledger: MagicMock) -> list[dict]:
    return ledger.add_entry.await_args.args[4]


@pytest.mark.asyncio
async def test_income_in_the_base_currency_is_at_par():
    svc, ledger = _service()
    await svc.declare_income(USER, [{"code": "4100", "name": "Employment", "amount": 250000}])

    for posting in _postings(ledger):
        assert posting["currency"] == "LKR"
        assert posting["fx_rate"] == Decimal(1)
        assert posting["fx_rate_source"] is None


@pytest.mark.asyncio
async def test_foreign_income_keeps_its_currency_and_carries_the_rate_and_its_source():
    fx = _fx("302.50")
    svc, ledger = _service(fx)

    await svc.declare_income(
        USER,
        [{"code": "4500", "name": "Foreign Service Income", "amount": 2000, "currency": "USD"}],
    )

    postings = _postings(ledger)
    assert [p["currency"] for p in postings] == ["USD", "USD"]
    # Both sides carry the same rate, so the entry still balances in base terms.
    assert {p["fx_rate"] for p in postings} == {Decimal("302.50")}
    assert {p["fx_rate_source"] for p in postings} == {"ecb"}
    fx.rate.assert_awaited_once()
    assert fx.rate.await_args.args[:2] == ("USD", "LKR")


@pytest.mark.asyncio
async def test_the_rate_is_into_the_users_own_base_currency():
    fx = _fx("0.92")
    svc, ledger = _service(fx, base="EUR")

    await svc.declare_income(
        USER, [{"code": "4500", "name": "Contract", "amount": 5000, "currency": "USD"}]
    )

    assert fx.rate.await_args.args[:2] == ("USD", "EUR")
    assert {p["fx_rate"] for p in _postings(ledger)} == {Decimal("0.92")}


@pytest.mark.asyncio
async def test_a_rate_the_user_gives_wins_and_is_not_looked_up():
    fx = _fx("302.50")
    svc, ledger = _service(fx)

    await svc.declare_income(
        USER,
        [{"code": "4500", "name": "FSI", "amount": 2000, "currency": "USD", "fx_rate": "298.10"}],
    )

    assert {p["fx_rate"] for p in _postings(ledger)} == {Decimal("298.10")}
    assert {p["fx_rate_source"] for p in _postings(ledger)} == {"user"}
    fx.rate.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_rate_anywhere_refuses_rather_than_booking_at_par():
    fx = MagicMock()
    fx.rate = AsyncMock(side_effect=FxUnavailableError("No USD→LKR rate"))
    svc, ledger = _service(fx)

    with pytest.raises(FxUnavailableError):
        await svc.declare_income(
            USER, [{"code": "4500", "name": "FSI", "amount": 2000, "currency": "USD"}]
        )
    ledger.add_entry.assert_not_awaited()


@pytest.mark.asyncio
async def test_currency_is_normalised_and_optional():
    svc, ledger = _service(_fx("2"))

    await svc.declare_income(
        USER, [{"code": "4500", "name": "FSI", "amount": 100, "currency": "usd"}]
    )
    assert {p["currency"] for p in _postings(ledger)} == {"USD"}


@pytest.mark.asyncio
async def test_an_unknown_currency_is_refused():
    svc, ledger = _service(_fx("2"))

    with pytest.raises(ValueError, match="ISO 4217"):
        await svc.declare_income(
            USER, [{"code": "4500", "name": "FSI", "amount": 100, "currency": "XYZ"}]
        )
    ledger.add_entry.assert_not_awaited()
