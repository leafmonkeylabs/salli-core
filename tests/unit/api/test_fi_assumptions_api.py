"""The user's own FI assumptions are set through `PATCH /v1/fi/assumptions`,
each with its source: values are decimal strings read exactly, only the fields
sent change, and an explicit null clears one."""

from __future__ import annotations

from decimal import Decimal

from tests.unit.api.conftest import AUTH

_REPORT = {
    "applied": {
        "status": "placeholder",
        "placeholders": ["real_return"],
        "message": "Using placeholder assumptions for the real return.",
        "real_return": {"value": "0.04", "origin": "placeholder", "source": "Placeholder: x"},
        "safe_withdrawal_rate": {"value": "0.035", "origin": "user", "source": "a study"},
        "inflation": {"value": "0.03", "origin": "user", "source": "a statistics office"},
        "nominal_return": None,
        "real_returns": {"conservative": "0.02", "base": "0.04", "growth": "0.06"},
        "nominal_returns": {"conservative": "0.0506", "base": "0.0712", "growth": "0.0918"},
    },
    "own": {
        "real_return": None,
        "nominal_return": None,
        "inflation": {"value": "0.03", "source": "a statistics office", "note": None},
        "safe_withdrawal_rate": None,
    },
    "placeholder_values": {
        "real_return": {"value": "0.04", "source": "Placeholder: x"},
        "safe_withdrawal_rate": {"value": "0.04", "source": "Placeholder: y"},
    },
    "scenario_spread": "0.02",
}


async def test_own_assumptions_are_set_with_sources_and_cleared(client, mock_services):
    mock_services.fi.set_assumptions.return_value = _REPORT
    r = await client.patch(
        "/v1/fi/assumptions",
        json={
            "inflation": {"value": "0.03", "source": "a statistics office"},
            "safe_withdrawal_rate": None,
        },
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    changes = mock_services.fi.set_assumptions.await_args.args[1]
    # Only what was sent: the real and nominal returns are left as they are.
    assert changes == {
        "inflation": {"value": Decimal("0.03"), "source": "a statistics office", "note": None},
        "safe_withdrawal_rate": None,
    }
    assert r.json()["applied"]["status"] == "placeholder"


async def test_an_assumption_that_is_not_a_decimal_string_is_a_422(client, mock_services):
    for body in (
        {"inflation": {"value": "3%"}},
        {"inflation": {"source": "no value"}},
        {"inflation": {"value": "0.03", "source": "x" * 501}},
    ):
        r = await client.patch("/v1/fi/assumptions", json=body, headers=AUTH)
        assert r.status_code == 422, body
    mock_services.fi.set_assumptions.assert_not_awaited()


async def test_the_profile_no_longer_takes_fi_assumptions(client, mock_services):
    r = await client.patch(
        "/v1/onboarding/profile", json={"fi_assumptions": {"inflation": "0.03"}}, headers=AUTH
    )
    assert r.status_code == 200
    mock_services.profile.update_identity.assert_awaited_once_with("test-user-1", {})
