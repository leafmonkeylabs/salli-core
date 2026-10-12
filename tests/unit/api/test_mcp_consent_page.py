"""Salli's own MCP consent page — approving a client without a web app."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from salli.application.services.login_service import SignedIn, SignInRefused, SignInThrottled
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
    mock_services.logins = AsyncMock()
    mock_services.logins.authenticate.return_value = SignedIn("owner", "a@b.c")
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
    consent.complete_consent.assert_awaited_once_with("t", "", False, password_checked=False)
    consent.set_mcp_enabled.assert_not_awaited()


async def test_wrong_credentials_show_the_form_again(client, consent, mock_services):
    mock_services.logins.authenticate.side_effect = SignInRefused()
    r = await client.post(
        PAGE,
        data={"rt": "t", "decision": "allow", "email": "a@b.c", "password": "a-guess-1234"},
    )
    assert r.status_code == 401
    assert "didn&#x27;t match" in r.text or "didn't match" in r.text
    # The password is never written back into the page.
    assert "a-guess-1234" not in r.text
    consent.complete_consent.assert_not_awaited()


async def test_too_many_failures_are_refused_with_429(client, consent, mock_services):
    mock_services.logins.authenticate.side_effect = SignInThrottled(600)
    r = await client.post(
        PAGE, data={"rt": "t", "decision": "allow", "email": "a@b.c", "password": "pw"}
    )
    assert r.status_code == 429
    assert "Too many failed sign-ins" in r.text
    consent.complete_consent.assert_not_awaited()


async def test_allow_signs_in_enables_mcp_and_redirects_to_the_client(
    client, consent, mock_services
):
    r = await client.post(
        PAGE, data={"rt": "t", "decision": "allow", "email": "a@b.c", "password": "pw"}
    )
    assert r.status_code == 303
    assert r.headers["location"] == "https://client.test/cb?code=abc"
    # Checked against Salli's own accounts, throttled by where it came from.
    mock_services.logins.authenticate.assert_awaited_once_with("a@b.c", "pw", address="127.0.0.1")
    consent.set_mcp_enabled.assert_awaited_once_with("owner", True)
    consent.complete_consent.assert_awaited_once_with("t", "owner", True, password_checked=True)


async def test_a_non_member_cannot_approve(client, consent, mock_services):
    mock_services.profile.ensure_user.return_value = False
    r = await client.post(
        PAGE, data={"rt": "t", "decision": "allow", "email": "s@x", "password": "pw"}
    )
    assert r.status_code == 403
    assert "not a member" in r.text
    mock_services.profile.ensure_user.assert_awaited_once_with("owner", None, may_create=False)
    consent.complete_consent.assert_not_awaited()
