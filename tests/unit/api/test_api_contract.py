"""
The REST API over HTTP: versioned paths, deprecated aliases, problem details,
and the public server description.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.unit.api.conftest import AUTH


async def test_the_old_path_still_answers_and_points_to_v1(client, mock_services):
    mock_services.ledger.get_trial_balance.return_value = {}
    old = await client.get("/ledger/trial-balance", headers=AUTH)
    new = await client.get("/v1/ledger/trial-balance", headers=AUTH)

    assert old.status_code == new.status_code == 200
    assert old.json() == new.json()
    assert old.headers["Deprecation"] == "true"
    assert old.headers["Link"] == '</v1/ledger/trial-balance>; rel="successor-version"'
    assert "Deprecation" not in new.headers


async def test_meta_is_public_and_describes_the_server(client):
    r = await client.get("/v1/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["api_version"] == "1"
    assert body["oauth"]["token_endpoint"].endswith("/mcp/oauth/token")
    # No country's tax is built in: a user's rule sets are theirs, not the server's.
    assert "tax_packs" not in body
    assert len(body["default_currency"]) == 3


async def test_health_and_identity_keep_their_shapes(client, mock_services):
    mock_services.logins.get_login = AsyncMock(return_value=None)
    health = await client.get("/healthz")
    assert health.status_code == 200
    assert set(health.json()) == {"status", "version"}

    me = await client.get("/v1/auth/me", headers=AUTH)
    assert me.status_code == 200
    # user_id as before; how they signed in, and their email when known, since.
    assert me.json() == {
        "user_id": "test-user-1",
        "email": None,
        "method": "dev",
        "permissions": ["tax:activate"],
        # And, since two-step sign-in, whether it is on.
        "totp_enabled": False,
    }


async def test_errors_are_problem_details_that_keep_their_detail(client):
    r = await client.get("/v1/ledger/trial-balance")  # no credentials
    assert r.status_code == 401
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert (body["type"], body["status"], body["title"]) == ("about:blank", 401, "Not signed in")
    assert body["detail"] == "Not authenticated"


@pytest.mark.parametrize(
    ("code", "title"),
    [
        (400, "Salli didn't do this"),
        (404, "Not found"),
        (409, "Not possible right now"),
        (422, "Salli couldn't use what was sent"),
        (418, "Salli didn't do this"),
        (599, "Salli hit an error it didn't expect"),
    ],
)
def test_a_plain_http_error_is_titled_in_salli_s_words_not_its_reason_phrase(code, title):
    from salli.interfaces.api.main import _status_title  # pyright: ignore[reportPrivateUsage]

    assert _status_title(code) == title


async def test_validation_errors_keep_the_field_list(client):
    r = await client.get("/v1/ledger/income-statement", headers=AUTH)  # dates missing
    assert r.status_code == 422
    body = r.json()
    assert body["type"] == "/problems/validation"
    assert {e["loc"][-1] for e in body["detail"]} == {"from_date", "to_date"}


async def test_a_domain_error_names_its_kind(client, mock_services):
    from salli.application.services.user_profile_service import BaseCurrencyLockedError

    mock_services.profile.set_base_currency.side_effect = BaseCurrencyLockedError("kept in EUR")
    r = await client.patch("/v1/onboarding/profile", json={"base_currency": "GBP"}, headers=AUTH)
    assert r.status_code == 409
    assert r.json()["type"] == "/problems/base-currency-locked"
