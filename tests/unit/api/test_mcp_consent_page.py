"""Salli's own MCP consent page — approving a client without a web app."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from salli.application.services.mcp_oauth_service import ConsentError

pytestmark = pytest.mark.asyncio

PAGE = "/mcp/oauth/consent-page"


@pytest.fixture
def consent(mock_services):
    mock_services.mcp_oauth = AsyncMock()
    mock_services.mcp_oauth.get_consent_info.return_value = {
        "client_name": "Claude <script>",
        "scope": "salli",
    }
    mock_services.mcp_oauth.complete_consent.return_value = "https://client.test/cb?code=abc"
    mock_services.profile.ensure_user.return_value = True
    return mock_services.mcp_oauth


async def test_the_page_names_the_client_safely(client, consent):
    r = await client.get(PAGE, params={"rt": "token"})
    assert r.status_code == 200
    assert "Claude &lt;script&gt;" in r.text and "<script>" not in r.text
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


async def test_an_expired_request_says_so(client, consent):
    consent.get_consent_info.side_effect = ConsentError("This authorization request has expired.")
    r = await client.get(PAGE, params={"rt": "old"})
    assert r.status_code == 400
    assert "expired" in r.text


async def test_deny_needs_no_sign_in_and_redirects(client, consent):
    r = await client.post(PAGE, data={"rt": "t", "decision": "deny"})
    assert r.status_code == 303
    consent.complete_consent.assert_awaited_once_with("t", "", False)
    consent.set_mcp_enabled.assert_not_awaited()


async def test_wrong_credentials_show_the_form_again(client, consent):
    with patch("salli.interfaces.api.routers.mcp_consent_page._sign_in", return_value=None):
        r = await client.post(
            PAGE, data={"rt": "t", "decision": "allow", "email": "a@b.c", "password": "x"}
        )
    assert r.status_code == 401
    assert "didn&#x27;t match" in r.text or "didn't match" in r.text
    consent.complete_consent.assert_not_awaited()


async def test_allow_signs_in_enables_mcp_and_redirects_to_the_client(client, consent):
    with (
        patch("salli.interfaces.api.routers.mcp_consent_page._sign_in", return_value="jwt"),
        patch(
            "salli.interfaces.api.routers.mcp_consent_page._decode_jwt",
            return_value=("owner", "a@b.c"),
        ),
    ):
        r = await client.post(
            PAGE, data={"rt": "t", "decision": "allow", "email": "a@b.c", "password": "pw"}
        )
    assert r.status_code == 303
    assert r.headers["location"] == "https://client.test/cb?code=abc"
    consent.set_mcp_enabled.assert_awaited_once_with("owner", True)
    consent.complete_consent.assert_awaited_once_with("t", "owner", True)


async def test_a_non_member_cannot_approve(client, consent, mock_services):
    mock_services.profile.ensure_user.return_value = False
    with (
        patch("salli.interfaces.api.routers.mcp_consent_page._sign_in", return_value="jwt"),
        patch(
            "salli.interfaces.api.routers.mcp_consent_page._decode_jwt",
            return_value=("stranger", None),
        ),
    ):
        r = await client.post(
            PAGE, data={"rt": "t", "decision": "allow", "email": "s@x", "password": "pw"}
        )
    assert r.status_code == 401
    assert "not a member" in r.text
    consent.complete_consent.assert_not_awaited()
