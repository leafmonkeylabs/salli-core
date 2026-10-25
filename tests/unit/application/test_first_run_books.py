"""
First run books only what is true. An asset is opened with the role it was
given, and one without a role is "other", never cash: a brokerage account or
a car booked as cash would count as money to spend. An income source opens
accounts and posts nothing: a made-up month of pay dated today would count as
real income.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from salli.application.services.user_profile_service import UserProfileService

USER = "user-1"


def _service() -> tuple[UserProfileService, MagicMock]:
    ledger = MagicMock()
    ledger.base_currency = AsyncMock(return_value="EUR")
    ledger.list_accounts = AsyncMock(return_value=[])
    ledger.add_account = AsyncMock(side_effect=lambda user_id, code, *a, **k: f"acct-{code}")
    ledger.add_entry = AsyncMock(return_value="entry-1")
    svc = UserProfileService(
        uow_factory=MagicMock(),
        ledger_service=ledger,
        fi_service=MagicMock(),
        document_service=MagicMock(),
    )
    return svc, ledger


def _roles(ledger: MagicMock) -> dict[str, object]:
    return {c.args[1]: c.kwargs.get("asset_role") for c in ledger.add_account.await_args_list}


async def test_each_asset_is_opened_with_its_role_and_unknown_is_other():
    svc, ledger = _service()
    await svc.declare_opening_balances(
        USER,
        [
            {
                "code": "1500",
                "name": "Current account",
                "type": "asset",
                "amount": "900",
                "asset_role": "cash",
            },
            {
                "code": "1510",
                "name": "Index funds",
                "type": "asset",
                "amount": "12000",
                "asset_role": "investment",
            },
            {"code": "1520", "name": "Car", "type": "asset", "amount": "8000"},
            {"code": "2500", "name": "Card", "type": "liability", "amount": "300"},
        ],
    )
    roles = _roles(ledger)
    assert (roles["1500"], roles["1510"], roles["1520"]) == ("cash", "investment", "other")
    assert roles["2500"] is None


async def test_an_income_source_opens_accounts_and_posts_nothing():
    svc, ledger = _service()
    ids = await svc.open_income_accounts(
        USER,
        [
            {
                "code": "4700",
                "name": "Salary",
                "deposit_account_code": "1500",
                "deposit_account_name": "Current account",
            }
        ],
    )
    assert ids == ["acct-4700"]
    ledger.add_entry.assert_not_awaited()
    assert _roles(ledger) == {"4700": None, "1500": "cash"}


def _currencies(ledger: MagicMock) -> dict[str, object]:
    return {c.args[1]: c.kwargs.get("currency") for c in ledger.add_account.await_args_list}


async def test_a_foreign_balance_opens_an_account_in_its_own_currency():
    svc, ledger = _service()
    await svc.declare_opening_balances(
        USER,
        [
            {
                "code": "1500",
                "name": "Dollar account",
                "type": "asset",
                "amount": "1000",
                "currency": "usd",
                "fx_rate": "0.92",
                "asset_role": "cash",
            },
            {
                "code": "1510",
                "name": "Current account",
                "type": "asset",
                "amount": "900",
                "asset_role": "cash",
            },
        ],
    )
    held_in = _currencies(ledger)
    assert (held_in["1500"], held_in["1510"]) == ("USD", "EUR")


async def test_an_existing_account_in_another_currency_is_refused():
    import pytest

    from salli.domain.accounting.models import Account

    svc, ledger = _service()
    ledger.list_accounts = AsyncMock(
        return_value=[
            Account(
                id="a1", user_id=USER, code="1500", name="Current", type="asset", currency="EUR"
            )
        ]
    )
    with pytest.raises(ValueError, match="held in EUR"):
        await svc.declare_opening_balances(
            USER,
            [
                {
                    "code": "1500",
                    "name": "Dollar account",
                    "type": "asset",
                    "amount": "10",
                    "currency": "USD",
                    "fx_rate": "0.9",
                }
            ],
        )
    ledger.add_entry.assert_not_awaited()
