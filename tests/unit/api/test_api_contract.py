"""
The REST API over HTTP: versioned paths, deprecated aliases, problem details,
and the public server description.
"""

from __future__ import annotations

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
    lk = body["tax_packs"][0]
    assert (lk["country"], lk["year"], lk["currency"]) == ("LK", "2025/26", "LKR")
    assert len(body["default_currency"]) == 3


async def test_health_and_identity_keep_their_shapes(client):
    health = await client.get("/healthz")
    assert health.status_code == 200
    assert set(health.json()) == {"status", "version"}

    me = await client.get("/v1/auth/me", headers=AUTH)
    assert me.status_code == 200
    # user_id as before; how they signed in, and their email when known, since.
    assert me.json() == {"user_id": "test-user-1", "email": None, "method": "dev"}


async def test_errors_are_problem_details_that_keep_their_detail(client):
    r = await client.get("/v1/ledger/trial-balance")  # no credentials
    assert r.status_code == 401
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert (body["type"], body["status"], body["title"]) == ("about:blank", 401, "Unauthorized")
    assert body["detail"] == "Not authenticated"


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
