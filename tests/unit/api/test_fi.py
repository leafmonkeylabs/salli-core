import pytest

from tests.unit.api.conftest import AUTH

# ── POST /fi/simulate-purchase ────────────────────────────────────────────────


def _impact() -> dict:
    return {
        "amount": "450000.00",
        "currency": "LKR",
        "baseline_months_to_fi": 404,
        "payable_from_liquid": True,
        "emergency_months_before": "8.00",
        "emergency_months_after_cash": "5.75",
        "emergency_fund_target_months": 6,
        "options": [{"key": "cash", "months_delay": 8}],
        "cheapest_option_key": "cash",
        "is_stale": False,
        "data_as_of": "2026-07-23",
    }


@pytest.mark.asyncio
async def test_simulate_purchase_parses_money_as_decimal(client, mock_services):
    """Money crosses the wire as a string and must reach the service as Decimal."""
    from decimal import Decimal

    mock_services.fi.simulate_purchase.return_value = _impact()

    r = await client.post(
        "/fi/simulate-purchase",
        json={"amount": "450000", "term_months": 12, "annual_interest_rate": "0.18"},
        headers=AUTH,
    )

    assert r.status_code == 200
    assert r.json()["cheapest_option_key"] == "cash"

    args, kwargs = mock_services.fi.simulate_purchase.call_args
    amount = args[1]
    assert isinstance(amount, Decimal), f"money reached the service as {type(amount).__name__}"
    assert amount == Decimal("450000")
    assert kwargs["annual_interest_rate"] == Decimal("0.18")
    assert kwargs["term_months"] == 12


@pytest.mark.asyncio
async def test_simulate_purchase_rejects_a_percentage_as_a_rate(client, mock_services):
    """18 instead of 0.18 would overstate the finance cost ~100x — reject at the edge."""
    r = await client.post(
        "/fi/simulate-purchase",
        json={"amount": "450000", "term_months": 12, "annual_interest_rate": "18"},
        headers=AUTH,
    )
    assert r.status_code == 422
    mock_services.fi.simulate_purchase.assert_not_called()


@pytest.mark.asyncio
async def test_simulate_purchase_rejects_negative_and_bad_terms(client, mock_services):
    for body in (
        {"amount": "-1"},
        {"amount": "450000", "term_months": 0},
        {"amount": "450000", "term_months": 601},
        {"amount": "not a number"},
    ):
        r = await client.post("/fi/simulate-purchase", json=body, headers=AUTH)
        assert r.status_code == 422, body
    mock_services.fi.simulate_purchase.assert_not_called()


@pytest.mark.asyncio
async def test_simulate_purchase_needs_auth(client, mock_services):
    r = await client.post("/fi/simulate-purchase", json={"amount": "450000"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_simulate_purchase_is_not_metered(client, mock_services):
    """
    Pure engine math with no LLM call. Metering it would teach users not to ask
    the one question the product exists to answer.
    """
    mock_services.fi.simulate_purchase.return_value = _impact()

    r = await client.post("/fi/simulate-purchase", json={"amount": "450000"}, headers=AUTH)

    assert r.status_code == 200
    mock_services.usage.charge.assert_not_called()
