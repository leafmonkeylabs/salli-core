"""The user's own FI assumptions are set through the profile, as decimal
strings read exactly."""

from __future__ import annotations

from decimal import Decimal

from tests.unit.api.conftest import AUTH


async def test_own_assumptions_are_set_and_cleared_through_the_profile(client, mock_services):
    r = await client.patch(
        "/v1/onboarding/profile",
        json={"fi_assumptions": {"inflation": "0.03", "safe_withdrawal_rate": None}},
        headers=AUTH,
    )
    assert r.status_code == 200
    data = mock_services.profile.update_identity.await_args.args[1]
    # Only what was sent: the real return is left as it is.
    assert data == {"fi_assumptions": {"inflation": Decimal("0.03"), "safe_withdrawal_rate": None}}


async def test_an_assumption_that_is_not_a_decimal_string_is_a_422(client, mock_services):
    r = await client.patch(
        "/v1/onboarding/profile", json={"fi_assumptions": {"inflation": "3%"}}, headers=AUTH
    )
    assert r.status_code == 422
    mock_services.profile.update_identity.assert_not_awaited()
