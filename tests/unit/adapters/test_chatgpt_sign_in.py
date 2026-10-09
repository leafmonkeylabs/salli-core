"""
Sign in with ChatGPT, OpenAI's side, piece by piece: PKCE, a fresh state and
nonce per attempt, the authorization request for a first registration and
for signing in again, the callback, the code exchange, and the ID token,
verified against a JWKS made for this run.
"""

from __future__ import annotations

import base64
import hashlib
import re
import time
from urllib.parse import parse_qs, urlsplit

import pytest

from salli.adapters.llm.chatgpt_oauth import (
    AUTHORIZE_URL,
    SignInDeclined,
    SignInError,
    authorization_url,
    begin_sign_in,
    pkce_challenge,
    read_callback,
)
from tests.openai_fakes import FakeAuthServer, Signer

HOST = "urn:uuid:7f2c1e9a-3b4d-4c5e-8f60-0a1b2c3d4e5f"
REDIRECT = "http://127.0.0.1:1455/auth/callback"


def _params(url: str) -> dict[str, str]:
    assert url.startswith(AUTHORIZE_URL + "?")
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


# ── PKCE, state and nonce ─────────────────────────────────────────────────────


def test_the_challenge_is_the_unpadded_base64url_sha256_of_the_verifier():
    verifier = "a-verifier-of-at-least-forty-three-characters-long"
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    assert pkce_challenge(verifier) == expected.rstrip(b"=").decode()
    assert "=" not in pkce_challenge(verifier)


def test_every_attempt_has_a_fresh_state_nonce_and_verifier():
    first = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT)
    second = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT)

    assert first.state != second.state
    assert first.nonce != second.nonce
    assert first.code_verifier != second.code_verifier
    # RFC 7636: 43 to 128 characters of the unreserved set.
    assert re.fullmatch(r"[A-Za-z0-9\-._~]{43,128}", first.code_verifier)


@pytest.mark.parametrize(
    "redirect",
    [
        "http://localhost:1455/auth/callback",  # "Do not substitute with localhost"
        "http://127.0.0.1:1455/callback",  # "/callback does not match /auth/callback"
        "https://127.0.0.1:1455/auth/callback",
        "http://127.0.0.1/auth/callback",
    ],
)
def test_only_the_port_of_the_loopback_callback_may_vary(redirect):
    with pytest.raises(ValueError):
        begin_sign_in(host_id=HOST, redirect_uri=redirect)


def test_another_port_is_fine():
    assert begin_sign_in(host_id=HOST, redirect_uri="http://127.0.0.1:54321/auth/callback")


# ── The authorization request ─────────────────────────────────────────────────


def test_a_first_registration_asks_as_dynamic_agent_client_with_salli_s_name():
    pending = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT)

    params = _params(authorization_url(pending, login_hint="me@example.com", id_token_hint="x"))

    assert params == {
        "client_id": "dynamic_agent_client",
        "agent_name_hint": "Salli",
        "ext_agent_host_id": HOST,
        "response_type": "code",
        "redirect_uri": REDIRECT,
        "scope": "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct",
        "resource": "https://api.openai.com/v1",
        "state": pending.state,
        "nonce": pending.nonce,
        "code_challenge": pkce_challenge(pending.code_verifier),
        "code_challenge_method": "S256",
    }


def test_signing_in_again_uses_the_issued_client_id_and_the_hints_but_no_name():
    pending = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT, client_id="oaiapp_test")

    params = _params(
        authorization_url(pending, login_hint="me@example.com", id_token_hint="id-token-1")
    )

    assert params["client_id"] == "oaiapp_test"
    assert "agent_name_hint" not in params
    assert params["ext_agent_host_id"] == HOST  # the same host, every time
    assert params["id_token_hint"] == "id-token-1"
    assert params["login_hint"] == "me@example.com"
    assert "prompt" not in params  # consent is not forced on an ordinary sign-in


def test_turning_plan_use_back_on_asks_for_consent():
    pending = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT, client_id="oaiapp_test")
    assert _params(authorization_url(pending, ask_consent=True))["prompt"] == "consent"


def test_a_saved_dynamic_agent_client_is_never_reused():
    assert begin_sign_in(
        host_id=HOST, redirect_uri=REDIRECT, client_id="dynamic_agent_client"
    ).registering


# ── The callback ──────────────────────────────────────────────────────────────


def test_a_registration_callback_returns_the_code_and_the_issued_client_id():
    pending = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT)
    callback = read_callback(
        pending, {"code": "c", "state": pending.state, "client_id": "oaiapp_new"}
    )
    assert (callback.code, callback.client_id) == ("c", "oaiapp_new")


def test_state_is_checked_before_anything_else():
    pending = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT)
    with pytest.raises(SignInError, match="did not come from this attempt"):
        read_callback(pending, {"error": "access_denied", "state": "forged"})
    with pytest.raises(SignInError):
        read_callback(pending, {"code": "c", "state": "forged", "client_id": "oaiapp_new"})


def test_declining_stops_the_attempt():
    pending = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT)
    with pytest.raises(SignInDeclined):
        read_callback(pending, {"error": "access_denied", "state": pending.state})


@pytest.mark.parametrize("client_id", [None, "dynamic_agent_client"])
def test_a_registration_without_an_issued_client_id_is_incomplete(client_id):
    pending = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT)
    query = {"code": "c", "state": pending.state}
    if client_id:
        query["client_id"] = client_id
    with pytest.raises(SignInError, match="did not finish registering"):
        read_callback(pending, query)


def test_signing_in_again_keeps_the_saved_client_id_and_refuses_another():
    pending = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT, client_id="oaiapp_test")

    assert read_callback(pending, {"code": "c", "state": pending.state}).client_id == "oaiapp_test"
    with pytest.raises(SignInError, match="different registration"):
        read_callback(pending, {"code": "c", "state": pending.state, "client_id": "oaiapp_other"})


# ── The code exchange ─────────────────────────────────────────────────────────


async def test_the_code_is_exchanged_with_the_verifier_redirect_and_resource():
    auth = FakeAuthServer()
    pending = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT)
    callback = read_callback(pending, auth.authorize(authorization_url(pending)))

    tokens = await auth.oauth().exchange_code(pending, callback)

    (form,) = auth.exchanges
    assert form == {
        "grant_type": "authorization_code",
        "client_id": "oaiapp_test",
        "code": "code-1",
        "code_verifier": pending.code_verifier,
        "redirect_uri": REDIRECT,
        "resource": "https://api.openai.com/v1",
    }
    assert "client_secret" not in form
    assert tokens.plan_granted
    assert tokens.refresh_token == "refresh-1"


async def test_a_spent_code_means_starting_again():
    auth = FakeAuthServer()
    pending = begin_sign_in(host_id=HOST, redirect_uri=REDIRECT)
    callback = read_callback(pending, auth.authorize(authorization_url(pending)))
    await auth.oauth().exchange_code(pending, callback)

    with pytest.raises(SignInError, match="already used"):
        await auth.oauth().exchange_code(pending, callback)


# ── The ID token ──────────────────────────────────────────────────────────────


@pytest.fixture
def auth():
    return FakeAuthServer()


async def test_a_valid_id_token_says_who_signed_in(auth):
    token = auth.signer.id_token(nonce="n-1")
    claims = await auth.oauth().verify_id_token(token, client_id="oaiapp_test", nonce="n-1")
    assert (claims["sub"], claims["email"]) == ("user-sub-1", "me@example.com")


@pytest.mark.parametrize(
    ("claims", "message"),
    [
        ({"iss": "https://evil.example"}, "could not be verified"),
        ({"aud": "oaiapp_someone_else"}, "could not be verified"),
        ({"exp": int(time.time()) - 600, "iat": int(time.time()) - 4200}, "expired"),
        ({"nonce": "another-attempt"}, "not the one this attempt asked for"),
        ({"sub": None}, "could not be verified"),
    ],
)
async def test_an_id_token_that_fails_a_check_is_refused(auth, claims, message):
    token = auth.signer.id_token(**{"nonce": "n-1", **claims})
    with pytest.raises(SignInError, match=message):
        await auth.oauth().verify_id_token(token, client_id="oaiapp_test", nonce="n-1")


async def test_an_id_token_signed_by_another_key_is_refused(auth):
    impostor = Signer(kid=auth.signer.kid)  # same key id, different key
    with pytest.raises(SignInError, match="could not be verified"):
        await auth.oauth().verify_id_token(impostor.id_token(), client_id="oaiapp_test")


async def test_an_unknown_key_id_fetches_the_keys_again_once(auth):
    oauth = auth.oauth()
    await oauth.verify_id_token(auth.signer.id_token(), client_id="oaiapp_test")
    assert auth.jwks_fetches == 1

    with pytest.raises(SignInError, match="does not publish"):
        await oauth.verify_id_token(Signer(kid="rotated").id_token(), client_id="oaiapp_test")
    assert auth.jwks_fetches == 2  # the cached set was checked, then fetched afresh once


async def test_an_unsigned_token_is_refused(auth):
    from jose import jwt

    unsigned = jwt.encode({"sub": "x"}, "secret", algorithm="HS256")
    with pytest.raises(SignInError, match="not signed the way OpenAI signs"):
        await auth.oauth().verify_id_token(unsigned, client_id="oaiapp_test")


async def test_the_id_token_is_bound_to_its_access_token_when_it_says_so(auth):
    from jose.utils import calculate_at_hash

    token = auth.signer.id_token(at_hash=calculate_at_hash("access-1", hashlib.sha256))
    oauth = auth.oauth()
    assert await oauth.verify_id_token(token, client_id="oaiapp_test", access_token="access-1")
    with pytest.raises(SignInError):
        await oauth.verify_id_token(token, client_id="oaiapp_test", access_token="access-2")
