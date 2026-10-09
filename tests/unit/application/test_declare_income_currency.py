"""
Declared income keeps the currency it was earned in.

`declare_income` used to hardcode "LKR" on both postings, so a foreign
remittance declared during onboarding was booked at face value in rupees: a
$2,000 month became Rs. 2,000. That is a ~300x understatement of income, and it
flows straight into the FI projection and the tax estimate, which is why this is
pinned rather than left to a manual check.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from salli.application.services.user_profile_service import UserProfileService

USER = "user-1"


def _service(fx=None) -> tuple[UserProfileService, AsyncMock]:
    ledger = MagicMock()
    # One existing account so `_ensure_account` resolves without creating.
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


def _postings(ledger: MagicMock) -> list[dict]:
    return ledger.add_entry.await_args.args[4]


@pytest.mark.asyncio
async def test_local_income_stays_in_the_base_currency_at_par():
    svc, ledger = _service()
    await svc.declare_income(USER, [{"code": "4100", "name": "Employment", "amount": 250000}])

    for posting in _postings(ledger):
        assert posting["currency"] == "LKR"
        assert posting["fx_rate"] == Decimal(1)


@pytest.mark.asyncio
async def test_foreign_income_keeps_its_currency_and_carries_the_rate():
    fx = MagicMock()
    fx.get_buying_rate = AsyncMock(return_value=Decimal("302.50"))
    svc, ledger = _service(fx)

    await svc.declare_income(
        USER,
        [{"code": "4500", "name": "Foreign Service Income", "amount": 2000, "currency": "USD"}],
    )

    postings = _postings(ledger)
    assert [p["currency"] for p in postings] == ["USD", "USD"]
    # Both sides carry the same rate, so the entry still balances in base terms.
    assert {p["fx_rate"] for p in postings} == {Decimal("302.50")}
    fx.get_buying_rate.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_broken_rate_service_does_not_dead_end_onboarding():
    """Rate lookup is best-effort.

    Falling back to 1 records a visibly wrong number the user can correct. The
    alternative, raising, strands someone mid-signup because a third-party
    exchange-rate endpoint is down.
    """
    fx = MagicMock()
    fx.get_buying_rate = AsyncMock(side_effect=RuntimeError("CBSL unreachable"))
    svc, ledger = _service(fx)

    await svc.declare_income(
        USER, [{"code": "4500", "name": "FSI", "amount": 2000, "currency": "USD"}]
    )

    postings = _postings(ledger)
    assert [p["currency"] for p in postings] == ["USD", "USD"]
    assert {p["fx_rate"] for p in postings} == {Decimal(1)}


@pytest.mark.asyncio
async def test_currency_is_normalised_and_optional():
    fx = MagicMock()
    fx.get_buying_rate = AsyncMock(return_value=Decimal("2"))
    svc, ledger = _service(fx)

    await svc.declare_income(
        USER, [{"code": "4500", "name": "FSI", "amount": 100, "currency": "usd"}]
    )
    assert {p["currency"] for p in _postings(ledger)} == {"USD"}
