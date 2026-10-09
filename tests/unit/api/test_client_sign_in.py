"""
Signing in clients that are not the web app: personal access tokens, device
sign-in, and the consent and device pages for the CLI.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from salli.application.services.mcp_oauth_service import ConsentError, DeviceFlowError
from salli.interfaces.api.deps import Principal, get_principal
from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio

_ROW = {
    "id": "p1",
    "name": "laptop",
    "prefix": "salli_pat_AbCd",
    "created_at": datetime(2026, 10, 9, tzinfo=UTC),
    "expires_at": None,
    "last_used_at": None,
}


def _as(app, method: str) -> None:
    app.dependency_overrides[get_principal] = lambda: Principal("test-user-1", None, method)


# ── /v1/tokens ────────────────────────────────────────────────────────────────


async def test_a_token_is_created_and_shown_once(app, client, mock_services):
    _as(app, "session")
    mock_services.tokens = AsyncMock()
    mock_services.tokens.create.return_value = {**_ROW, "token": "salli_pat_secret"}
    r = await client.post(
        "/v1/tokens", json={"name": "laptop", "expires_in_days": 90}, headers=AUTH
    )
    assert r.status_code == 201
    assert r.json()["token"] == "salli_pat_secret"
    mock_services.tokens.create.assert_awaited_once_with("test-user-1", "laptop", 90)


async def test_a_personal_access_token_cannot_make_another(app, client, mock_services):
    _as(app, "pat")
    mock_services.tokens = AsyncMock()
    r = await client.post("/v1/tokens", json={"name": "more"}, headers=AUTH)
    assert r.status_code == 403
    mock_services.tokens.create.assert_not_called()


async def test_the_list_never_includes_the_token(app, client, mock_services):
    mock_services.tokens = AsyncMock()
    mock_services.tokens.list.return_value = [_ROW]
    body = (await client.get("/v1/tokens", headers=AUTH)).json()
    assert body[0]["prefix"] == "salli_pat_AbCd"
    assert "token" not in body[0]


async def test_revoking_an_unknown_token_is_a_404(client, mock_services):
    mock_services.tokens = AsyncMock()
    mock_services.tokens.revoke.return_value = False
    assert (await client.delete("/v1/tokens/nope", headers=AUTH)).status_code == 404


# ── device sign-in over HTTP ──────────────────────────────────────────────────


async def test_device_authorization_returns_the_codes(client, mock_services):
    mock_services.mcp_oauth = AsyncMock()
    mock_services.mcp_oauth.start_device_authorization.return_value = {
        "device_code": "dc",
        "user_code": "BCDF-GHJK",
        "verification_uri": "https://salli.test/mcp/oauth/device",
        "verification_uri_complete": "https://salli.test/mcp/oauth/device?user_code=BCDF-GHJK",
        "expires_in": 600,
        "interval": 5,
    }
    r = await client.post(
        "/mcp/oauth/device_authorization",
        data={"client_id": "c1", "resource": "https://salli.test/v1"},
    )
    assert r.status_code == 200
    assert r.json()["user_code"] == "BCDF-GHJK"


@pytest.mark.parametrize(
    "error", ["authorization_pending", "slow_down", "access_denied", "expired_token"]
)
async def test_the_token_endpoint_reports_device_states_by_name(client, mock_services, error):
    mock_services.mcp_oauth = AsyncMock()
    mock_services.mcp_oauth.exchange_device_code.side_effect = DeviceFlowError(error, "…")
    r = await client.post(
        "/mcp/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": "dc",
            "client_id": "c1",
        },
    )
    assert r.status_code == 400
    assert r.json()["error"] == error


@pytest.mark.parametrize(
    ("kwargs"), [{"data": {"token": "t"}}, {"json": {"token": "t"}}], ids=["form", "json"]
)
async def test_revocation_accepts_rfc_7009_forms_and_json(client, mock_services, kwargs):
    mock_services.mcp_oauth = AsyncMock()
    r = await client.post("/mcp/oauth/revoke", **kwargs)
    assert r.status_code == 200
    mock_services.mcp_oauth.revoke_token_by_value.assert_awaited_once_with("t")


# ── the pages ─────────────────────────────────────────────────────────────────


@pytest.fixture
def cli_consent(mock_services):
    mock_services.mcp_oauth = AsyncMock()
    mock_services.mcp_oauth.get_consent_info.return_value = {
        "client_name": "Salli CLI",
        "scope": "",
        "audience": "api",
    }
    mock_services.mcp_oauth.complete_consent.return_value = "http://127.0.0.1:5000/callback?code=x"
    mock_services.profile.ensure_user.return_value = True
    return mock_services.mcp_oauth


async def test_the_consent_page_asks_the_cli_to_sign_in_not_to_connect(client, cli_consent):
    r = await client.get("/mcp/oauth/consent-page", params={"rt": "t"})
    assert "Sign in to Salli CLI?" in r.text
    assert "act on it for you" not in r.text


async def test_approving_the_cli_does_not_switch_mcp_on(client, cli_consent):
    with (
        patch("salli.interfaces.api.routers.mcp_consent_page._sign_in", return_value="jwt"),
        patch(
            "salli.interfaces.api.routers.mcp_consent_page._decode_jwt",
            return_value=("test-user-1", "a@b.test"),
        ),
    ):
        r = await client.post(
            "/mcp/oauth/consent-page",
            data={"rt": "t", "decision": "allow", "email": "a@b.test", "password": "pw"},
        )
    assert r.status_code == 303
    cli_consent.set_mcp_enabled.assert_not_called()


async def test_the_device_page_signs_a_device_in(client, mock_services):
    mock_services.mcp_oauth = AsyncMock()
    mock_services.mcp_oauth.device_request.return_value = {
        "client_name": "Salli CLI",
        "audience": "api",
    }
    mock_services.profile.ensure_user.return_value = True
    page = await client.get("/mcp/oauth/device", params={"user_code": "BCDF-GHJK"})
    assert "Salli CLI on another device is waiting" in page.text
    with (
        patch("salli.interfaces.api.routers.mcp_consent_page._sign_in", return_value="jwt"),
        patch(
            "salli.interfaces.api.routers.mcp_consent_page._decode_jwt",
            return_value=("test-user-1", "a@b.test"),
        ),
    ):
        r = await client.post(
            "/mcp/oauth/device",
            data={
                "user_code": "BCDF-GHJK",
                "decision": "allow",
                "email": "a@b.test",
                "password": "pw",
            },
        )
    assert r.status_code == 200 and "Signed in" in r.text
    mock_services.mcp_oauth.decide_device.assert_awaited_once_with("BCDF-GHJK", "test-user-1", True)
    mock_services.mcp_oauth.set_mcp_enabled.assert_not_called()


async def test_an_unknown_device_code_is_refused(client, mock_services):
    mock_services.mcp_oauth = AsyncMock()
    mock_services.mcp_oauth.device_request.return_value = None
    r = await client.post("/mcp/oauth/device", data={"user_code": "XXXX-XXXX", "decision": "allow"})
    assert r.status_code == 400 and "not valid" in r.text


async def test_a_refused_decision_is_shown_on_the_page(client, mock_services):
    mock_services.mcp_oauth = AsyncMock()
    mock_services.mcp_oauth.device_request.return_value = {"client_name": "x", "audience": "mcp"}
    mock_services.mcp_oauth.decide_device.side_effect = ConsentError("MCP access isn't available")
    r = await client.post("/mcp/oauth/device", data={"user_code": "B", "decision": "deny"})
    assert r.status_code == 401 and "MCP access" in r.text
