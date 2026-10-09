"""`/v1/ai`: the instance's host id, and a ChatGPT plan connection handed
over from another computer. Nothing here ever returns a token."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from salli.adapters.llm.chatgpt_oauth import OAuthUnavailable, SignInError
from salli.application.services.chatgpt_connection_service import ChatGPTUnavailable
from salli.domain.llm import LLMKeyRejected, LLMNotEligible

from .conftest import AUTH

HOST = "urn:uuid:7f2c1e9a-3b4d-4c5e-8f60-0a1b2c3d4e5f"

STATUS = {
    "available": True,
    "status": "active",
    "connected": True,
    "email": "me@example.com",
    "client_id": "oaiapp_test",
    "scopes": ["chatgpt.tokens.use.direct", "offline_access"],
    "expires_at": "2026-10-09T13:00:00+00:00",
    "paused_until": None,
    "detail": None,
    "readable": True,
}

CREDENTIAL = {
    "client_id": "oaiapp_test",
    "access_token": "access-SECRET",
    "refresh_token": "refresh-SECRET",
    "id_token": "id-token-SECRET",
    "token_type": "Bearer",
    "expires_in": 3600,
    "scope": "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct",
}


@pytest.fixture
def chatgpt(mock_services):
    svc = AsyncMock()
    svc.host_id.return_value = HOST
    svc.status.return_value = dict(STATUS)
    mock_services.chatgpt = svc
    return svc


async def test_members_can_read_the_host_id(client, chatgpt):
    r = await client.get("/v1/ai/host", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"ext_agent_host_id": HOST}


async def test_the_host_id_needs_a_signed_in_member(client, chatgpt):
    assert (await client.get("/v1/ai/host")).status_code == 401


async def test_the_connection_is_described_without_a_token(client, chatgpt):
    chatgpt.status.return_value = {**STATUS, "access_token": "access-SECRET"}

    r = await client.get("/v1/ai/connections/chatgpt", headers=AUTH)

    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "me@example.com"
    assert body["manage_usage_url"] == "https://chatgpt.com/settings/usage"
    assert "SECRET" not in r.text
    chatgpt.status.assert_awaited_once_with("test-user-1")


async def test_the_schema_has_no_token_field_to_return(client, chatgpt):
    schema = (await client.get("/openapi.json")).json()
    ref = schema["paths"]["/v1/ai/connections/chatgpt"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"]
    fields = set(schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]["properties"])
    assert not fields & {"access_token", "refresh_token", "id_token"}


async def test_a_credential_from_another_computer_is_handed_to_the_service(client, chatgpt):
    chatgpt.import_credential.return_value = {**STATUS, "first_time": True}

    r = await client.put(
        "/v1/ai/connections/chatgpt",
        json={**CREDENTIAL, "ext_agent_host_id": "urn:uuid:the-laptops"},
        headers=AUTH,
    )

    assert r.status_code == 200
    assert r.json()["first_time"] is True
    assert "SECRET" not in r.text
    user, credential = chatgpt.import_credential.await_args.args
    assert user == "test-user-1"  # from the bearer token, never the body
    assert credential["refresh_token"] == "refresh-SECRET"
    assert credential["client_id"] == "oaiapp_test"


@pytest.mark.parametrize("missing", ["client_id", "access_token", "refresh_token", "id_token"])
async def test_a_credential_needs_all_of_its_tokens(client, chatgpt, missing):
    body = {k: v for k, v in CREDENTIAL.items() if k != missing}
    r = await client.put("/v1/ai/connections/chatgpt", json=body, headers=AUTH)
    assert r.status_code == 422
    chatgpt.import_credential.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (SignInError("The ChatGPT sign-in could not be verified."), 400, "sign_in_rejected"),
        (ChatGPTUnavailable("needs an encryption key"), 503, "chatgpt_unavailable"),
        (OAuthUnavailable("down"), 503, "openai_unreachable"),
        (LLMKeyRejected("ChatGPT didn't accept your sign-in.", provider="chatgpt"), 502, None),
        (LLMNotEligible("not here", provider="chatgpt"), 403, "chatgpt_not_eligible"),
    ],
)
async def test_a_refused_credential_says_why(client, chatgpt, error, status, code):
    chatgpt.import_credential.side_effect = error

    r = await client.put("/v1/ai/connections/chatgpt", json=CREDENTIAL, headers=AUTH)

    assert r.status_code == status
    detail = r.json()["detail"]
    assert detail["error"] == (code or "ai_credential_rejected")
    assert detail["message"]
    assert "SECRET" not in r.text


async def test_disconnecting(client, chatgpt):
    chatgpt.disconnect.return_value = {
        "disconnected": True,
        "revoked": True,
        "message": "Disconnected from ChatGPT.",
    }
    r = await client.delete("/v1/ai/connections/chatgpt", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["revoked"] is True


async def test_disconnecting_what_is_not_connected_is_a_404(client, chatgpt):
    chatgpt.disconnect.return_value = {"disconnected": False, "revoked": False, "message": "x"}
    r = await client.delete("/v1/ai/connections/chatgpt", headers=AUTH)
    assert r.status_code == 404


# ── The provider and its models ───────────────────────────────────────────────

SETTINGS = {
    "provider": "auto",
    "active": {"provider": "chatgpt", "source": "user"},
    "keys": ["anthropic"],
    "chatgpt": "active",
    "chatgpt_available": True,
    "platform_key": True,
    "models": {"chatgpt": {"best": "gpt-test-best"}},
}


@pytest.fixture
def credentials(mock_services):
    svc = mock_services.llm_credentials
    svc.settings.return_value = SETTINGS
    svc.set_provider.return_value = {**SETTINGS, "provider": "chatgpt"}
    svc.models.return_value = {
        "provider": "chatgpt",
        "models": [
            {"id": "gpt-test-best", "name": "Best"},
            {"id": "gpt-test-mini", "name": "Mini"},
        ],
        "fast": "gpt-test-mini",
        "best": "gpt-test-best",
        "chosen": {},
    }
    svc.set_models.return_value = svc.models.return_value
    return svc


async def test_the_setting_and_what_it_resolves_to(client, credentials):
    r = await client.get("/v1/ai/settings", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["active"] == {"provider": "chatgpt", "source": "user"}


async def test_choosing_a_provider(client, credentials):
    r = await client.put("/v1/ai/settings", json={"provider": "chatgpt"}, headers=AUTH)
    assert r.status_code == 200
    credentials.set_provider.assert_awaited_once_with("test-user-1", "chatgpt")
    bad = await client.put("/v1/ai/settings", json={"provider": "gemini"}, headers=AUTH)
    assert bad.status_code == 422


async def test_listing_a_providers_models(client, credentials):
    r = await client.get("/v1/ai/models/chatgpt", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["best"] == "gpt-test-best"
    credentials.models.assert_awaited_once_with("test-user-1", "chatgpt")


async def test_listing_models_of_a_plan_that_needs_signing_in(client, credentials):
    from salli.domain.llm import LLMSignInRequired

    credentials.models.side_effect = LLMSignInRequired("Sign in again.", provider="chatgpt")
    r = await client.get("/v1/ai/models/chatgpt", headers=AUTH)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "ai_sign_in_required"


async def test_naming_a_model_is_for_openai_providers_only(client, credentials):
    r = await client.put("/v1/ai/models/openai", json={"best": "gpt-x"}, headers=AUTH)
    assert r.status_code == 200
    credentials.set_models.assert_awaited_once_with(
        "test-user-1", "openai", fast=None, best="gpt-x"
    )
    assert (
        await client.put("/v1/ai/models/anthropic", json={"best": "x"}, headers=AUTH)
    ).status_code == 422
