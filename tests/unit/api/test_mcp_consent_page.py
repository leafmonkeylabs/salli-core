"""Salli's own MCP consent page — approving a client without a web app."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from salli.application.services.login_service import (
    CodeNeeded,
    SignedIn,
    SignInRefused,
    SignInThrottled,
)
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
    consent.get_consent_info.side_effect = ConsentError(
        "This sign-in link has expired. Go back to the app and start again."
    )
    r = await client.get(PAGE, params={"rt": "old"})
    assert r.status_code == 400
    assert "expired" in r.text


async def test_deny_needs_no_sign_in_and_redirects(client, consent):
    r = await client.post(PAGE, data={"rt": "t", "decision": "deny"})
    assert r.status_code == 303
    consent.complete_consent.assert_awaited_once_with(
        "t", "", False, password_checked=False, allow_changes=False
    )
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
    mock_services.logins.authenticate.assert_awaited_once_with(
        "a@b.c", "pw", address="127.0.0.1", code=None
    )
    consent.set_mcp_enabled.assert_awaited_once_with("owner", True)
    consent.complete_consent.assert_awaited_once_with(
        "t", "owner", True, password_checked=True, allow_changes=False
    )


async def test_an_authenticator_code_goes_with_the_password(client, consent, mock_services):
    page = await client.get(PAGE, params={"rt": "t"})
    assert "<label for=code>Authenticator code" in page.text
    r = await client.post(
        PAGE,
        data={"rt": "t", "decision": "allow", "email": "a@b.c", "password": "pw", "code": "123456"},
    )
    assert r.status_code == 303
    mock_services.logins.authenticate.assert_awaited_once_with(
        "a@b.c", "pw", address="127.0.0.1", code="123456"
    )


async def test_a_missing_code_shows_the_form_again_and_says_so(client, consent, mock_services):
    mock_services.logins.authenticate.side_effect = CodeNeeded()
    r = await client.post(
        PAGE, data={"rt": "t", "decision": "allow", "email": "a@b.c", "password": "pw-1234"}
    )
    assert r.status_code == 401
    assert "Enter the code from your authenticator app" in r.text
    assert "pw-1234" not in r.text
    consent.complete_consent.assert_not_awaited()


async def test_a_non_member_cannot_approve(client, consent, mock_services):
    mock_services.profile.ensure_user.return_value = False
    r = await client.post(
        PAGE, data={"rt": "t", "decision": "allow", "email": "s@x", "password": "pw"}
    )
    assert r.status_code == 403
    assert "not a member" in r.text
    mock_services.profile.ensure_user.assert_awaited_once_with("owner", None, may_create=False)
    consent.complete_consent.assert_not_awaited()


# ── The brand, the console and the CSP (docs/design/console.md, section 2) ──


def _style_of(page: str) -> str:
    return page.split("<style>", 1)[1].split("</style>", 1)[0]


async def test_the_page_s_only_style_is_allowed_by_its_hash_and_no_script_runs(client, consent):
    import base64
    import hashlib

    r = await client.get(PAGE, params={"rt": "token"})
    csp = r.headers["content-security-policy"]
    digest = base64.b64encode(hashlib.sha256(_style_of(r.text).encode()).digest()).decode()
    assert f"style-src 'sha256-{digest}'" in csp
    assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp
    assert "require-trusted-types-for 'script'; trusted-types 'none'" in csp
    assert "unsafe-inline" not in csp and "script-src" not in csp
    assert "<script" not in r.text and " style=" not in r.text
    for name, value in (
        ("x-content-type-options", "nosniff"),
        ("referrer-policy", "no-referrer"),
        ("cross-origin-opener-policy", "same-origin"),
    ):
        assert r.headers[name] == value


async def test_the_page_is_in_the_brand(client, consent):
    style = _style_of((await client.get(PAGE, params={"rt": "token"})).text)
    for token in ("#F6F3EC", "#1C1B19", "#173B33", "#D8CBAE", "#0E1513", "#F2ECDF"):
        assert token in style
    # Not the colours it had before the brand, and no brass focus ring (2.4:1).
    for old in ("#2E7D6B", "#fafaf7", "#B39A6B"):
        assert old.lower() not in style.lower()
    assert "@import" not in style and "url(" not in style  # no font request
    # A field's edge is stone (muted on dark), at least 3:1; inputs and buttons 44 px.
    assert "--field:#8A8378" in style and "--field:#9AAAA2" in style
    assert "border:1px solid var(--field)" in style
    assert "height:44px" in style and "height:40px" not in style


async def test_the_logo_is_the_outlined_file_not_retyped(client, consent):
    page = (await client.get(PAGE, params={"rt": "token"})).text
    assert '<svg viewBox="0 0 472.214 137.829" role="img" aria-label="Salli">' in page
    assert "<span>Salli</span>" not in page and "text-transform:uppercase" not in page
    assert "SALLI" not in page


async def test_the_page_says_who_resets_a_forgotten_password(client, consent):
    page = (await client.get(PAGE, params={"rt": "token"})).text
    assert "Forgotten your password? The person who runs this Salli server can reset it." in page


async def test_the_console_reads_as_signing_in_to_salli_with_one_button(client, consent):
    consent.get_consent_info.return_value = {
        "client_id": "salli-console",
        "client_name": "Salli console",
        "first_party": True,
        "scope": "",
        "audience": "api",
        "reauthenticate": False,
    }
    r = await client.get(PAGE, params={"rt": "token"})
    assert "<title>Sign in to Salli</title>" in r.text and "<h1>Sign in to Salli</h1>" in r.text
    assert r.text.count("<button") == 1 and ">Sign in</button>" in r.text
    assert "is asking" not in r.text


_ALLOW = "<input type=checkbox id=allow_changes name=allow_changes value=yes>"
_SIGNED_IN = {"rt": "t", "decision": "allow", "email": "a@b.c", "password": "pw"}


async def test_an_ai_client_reads_unless_the_person_ticks_allow_changes(client, consent):
    r = await client.get(PAGE, params={"rt": "token"})
    assert "is asking to read your Salli data." in r.text
    assert _ALLOW in r.text and "checked" not in r.text
    assert "<label for=allow_changes>Allow changes" in r.text

    await client.post(PAGE, data=_SIGNED_IN)
    assert consent.complete_consent.await_args.kwargs["allow_changes"] is False
    await client.post(PAGE, data={**_SIGNED_IN, "allow_changes": "yes"})
    assert consent.complete_consent.await_args.kwargs["allow_changes"] is True


@pytest.mark.parametrize(
    ("client_id", "audience"),
    [("salli-mobile", "mcp"), ("salli-mobile", "api"), ("salli-console", "api")],
)
async def test_salli_s_own_sign_ins_are_not_asked_about_changes(
    client, consent, client_id, audience
):
    """The app's AI asks the person in the app before each change: its grant
    may change, and the page has no tick box for it, nor for a sign-in."""
    consent.get_consent_info.return_value = {
        "client_id": client_id,
        "client_name": "Salli",
        "first_party": True,
        "scope": "",
        "audience": audience,
        "reauthenticate": False,
    }
    r = await client.get(PAGE, params={"rt": "token"})
    assert "allow_changes" not in r.text
    await client.post(PAGE, data={**_SIGNED_IN, "allow_changes": "yes"})
    assert consent.complete_consent.await_args.kwargs["allow_changes"] is False


async def test_a_client_asking_for_the_password_again_says_so(client, consent):
    consent.get_consent_info.return_value = {
        "client_id": "salli-console",
        "client_name": "Salli console",
        "scope": "",
        "audience": "api",
        "reauthenticate": True,
    }
    r = await client.get(PAGE, params={"rt": "token"})
    assert "Confirm it&#x27;s you" in r.text or "Confirm it's you" in r.text
    assert "Enter your password again to continue." in r.text
    assert ">Continue</button>" in r.text


async def test_a_refused_consent_is_shown_on_the_page(client, consent, mock_services):
    consent.complete_consent.side_effect = ConsentError("The console is switched off.")
    r = await client.post(
        PAGE, data={"rt": "t", "decision": "allow", "email": "a@b.c", "password": "pw"}
    )
    assert r.status_code == 403
    assert "The console is switched off." in r.text
    assert r.headers["content-security-policy"].startswith("default-src 'none'")
