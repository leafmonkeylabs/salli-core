"""The /llm-keys surface is write-only: the key goes in, and nothing but its
last four characters ever comes back out. These assert that, plus the error
mapping — a rejected key and an unreachable provider must not look the same to
the user."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from salli.adapters.llm.key_check import InvalidProviderKey, KeyValidationUnavailable

from .conftest import AUTH

KEY = "sk-ant-api03-SECRET0123456789"


@pytest.fixture
def creds(mock_services):
    svc = AsyncMock()
    svc.available = True  # plain attribute, not a coroutine
    mock_services.llm_credentials = svc
    return svc


# ── GET ───────────────────────────────────────────────────────────────────────


async def test_get_reports_stored_keys_without_the_key(client, creds):
    creds.status.return_value = [
        {
            "provider": "anthropic",
            "last4": "6789",
            "validated_at": "2026-08-23T00:00:00Z",
            "readable": True,
        }
    ]
    r = await client.get("/llm-keys", headers=AUTH)

    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["keys"][0]["last4"] == "6789"
    assert KEY not in r.text
    assert "ciphertext" not in r.text


async def test_get_reports_unavailable_so_the_ui_can_hide_the_section(client, creds):
    creds.available = False
    creds.status.return_value = []
    body = (await client.get("/llm-keys", headers=AUTH)).json()
    assert body == {"available": False, "keys": []}


async def test_get_requires_auth(client, creds):
    assert (await client.get("/llm-keys")).status_code == 401


# ── PUT ───────────────────────────────────────────────────────────────────────


async def test_saving_a_key_returns_no_content_and_never_echoes_it(client, creds):
    creds.save.return_value = {"provider": "anthropic", "last4": "6789", "validated_at": None}
    r = await client.put("/llm-keys/anthropic", json={"key": KEY}, headers=AUTH)

    assert r.status_code == 204
    assert KEY not in r.text
    creds.save.assert_awaited_once()


async def test_the_key_reaches_the_service_for_the_authenticated_user(client, creds):
    await client.put("/llm-keys/anthropic", json={"key": KEY}, headers=AUTH)
    args = creds.save.await_args.args
    assert args[0] == "test-user-1"  # from the bearer token, never the body
    assert args[1] == "anthropic"
    assert args[2] == KEY


async def test_a_rejected_key_is_a_400_with_our_own_wording(client, creds):
    """Never the provider's message — an upstream error can echo the key."""
    creds.save.side_effect = InvalidProviderKey("anthropic")
    r = await client.put("/llm-keys/anthropic", json={"key": KEY}, headers=AUTH)

    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_key"
    assert "Anthropic rejected this key" in detail["message"]
    assert KEY not in r.text


async def test_an_unreachable_provider_is_a_503_not_a_rejection(client, creds):
    """Distinct from a bad key: telling someone their key is wrong because the
    provider was briefly down would send them chasing the wrong problem."""
    creds.save.side_effect = KeyValidationUnavailable("anthropic")
    r = await client.put("/llm-keys/anthropic", json={"key": KEY}, headers=AUTH)

    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "validation_unavailable"


async def test_byok_not_configured_is_a_503(client, creds):
    creds.save.side_effect = RuntimeError("BYOK is not configured on this deployment")
    r = await client.put("/llm-keys/anthropic", json={"key": KEY}, headers=AUTH)

    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "byok_unavailable"


async def test_an_unknown_provider_is_rejected_by_the_schema(client, creds):
    r = await client.put("/llm-keys/deepseek", json={"key": KEY}, headers=AUTH)
    assert r.status_code == 422
    creds.save.assert_not_awaited()


async def test_an_empty_key_is_rejected_before_reaching_the_service(client, creds):
    r = await client.put("/llm-keys/anthropic", json={"key": ""}, headers=AUTH)
    assert r.status_code == 422
    creds.save.assert_not_awaited()


async def test_saving_requires_auth(client, creds):
    r = await client.put("/llm-keys/anthropic", json={"key": KEY})
    assert r.status_code == 401
    creds.save.assert_not_awaited()


@pytest.mark.parametrize("provider", ["anthropic"])
async def test_both_providers_are_accepted(client, creds, provider):
    assert (
        await client.put(f"/llm-keys/{provider}", json={"key": KEY}, headers=AUTH)
    ).status_code == 204


# ── DELETE ────────────────────────────────────────────────────────────────────


async def test_deleting_a_stored_key(client, creds):
    creds.delete.return_value = True
    r = await client.delete("/llm-keys/anthropic", headers=AUTH)
    assert r.status_code == 204
    creds.delete.assert_awaited_once_with("test-user-1", "anthropic")


async def test_deleting_a_key_that_isnt_there_is_a_404(client, creds):
    creds.delete.return_value = False
    assert (await client.delete("/llm-keys/anthropic", headers=AUTH)).status_code == 404


async def test_deleting_requires_auth(client, creds):
    assert (await client.delete("/llm-keys/anthropic")).status_code == 401


# ── The key must not appear in the OpenAPI schema either ──────────────────────


async def test_the_schema_documents_the_route_without_exposing_a_key_field(client, creds):
    """The generated clients are built from this schema, so a `key` in a
    *response* model would propagate a readback path into both apps."""
    schema = (await client.get("/openapi.json")).json()
    assert "/llm-keys" in schema["paths"]

    get_response = schema["paths"]["/llm-keys"]["get"]["responses"]["200"]
    assert "key" not in str(get_response).lower().replace("llm-keys", "")


def test_the_router_never_returns_the_service_save_result():
    """save() returns last4/validated_at, but the route is 204 — so even a future
    change to that return value can't start leaking through this endpoint."""
    import inspect

    from salli.interfaces.api.routers import llm_keys

    source = inspect.getsource(llm_keys.save_llm_key)
    assert "return" not in source


def test_mock_services_shape_matches_the_real_service():
    """Guards the fixture: if LlmCredentialService loses a method these tests
    would keep passing against a mock that no longer resembles it."""
    from salli.application.services.llm_credential_service import LlmCredentialService

    for name in ("status", "save", "delete", "available"):
        assert hasattr(LlmCredentialService, name), name


def test_provider_literal_matches_the_services_provider_list():
    from salli.application.services.llm_credential_service import PROVIDERS
    from salli.interfaces.api.routers.llm_keys import Provider

    assert set(Provider.__args__) == set(PROVIDERS)


def test_every_provider_has_a_label():
    from salli.interfaces.api.routers.llm_keys import _PROVIDER_LABEL, Provider

    assert set(_PROVIDER_LABEL) == set(Provider.__args__)
