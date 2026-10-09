"""
Sign in with ChatGPT, for using a person's ChatGPT plan: OpenAI's side of it.

The contract is OpenAI's guide for open-source and self-hosted apps
(https://developers.openai.com/siwc/token-sharing-open-source). This module is
only the wire: the endpoints, the token requests and what their answers mean.
What Salli keeps, and when it renews, lives in ChatGPTConnectionService.

Open-source and locally hosted apps may offer plan use this way; a paid or
remotely hosted product needs OpenAI's approval first (see
Settings.salli_chatgpt_plan_usage and the extension seam for switching it off).

Never logged: a token, an authorization code, a PKCE verifier, or an
authorization URL that carries an `id_token_hint`.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlencode

import httpx

_log = logging.getLogger(__name__)

#: OpenAI's published values (its discovery document, auth.openai.com's
#: /.well-known/openid-configuration, and the sign-in guide).
ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = "https://auth.openai.com/api/accounts/authorize"
TOKEN_URL = "https://auth.openai.com/api/accounts/oauth/token"
REVOKE_URL = "https://auth.openai.com/api/accounts/oauth/revoke"
JWKS_URL = "https://auth.openai.com/.well-known/jwks.json"
#: The resource every token is for, sent with each authorization and token request.
RESOURCE = "https://api.openai.com/v1"
MODELS_URL = "https://api.openai.com/v1/models"

#: First-time registration's client id. Never saved, never used for a token
#: exchange: the callback returns the issued one (sign-in, step 3).
DYNAMIC_CLIENT_ID = "dynamic_agent_client"
#: Without this granted scope there is no plan use, whatever else was granted.
PLAN_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = ("openid", "profile", "email", "offline_access", "resource.invoke", PLAN_SCOPE)

#: Refresh errors that mean the refresh token can never be used again
#: (errors-and-recovery, "Refresh errors").
_UNUSABLE_REFRESH = frozenset(
    {
        "invalid_grant",
        "invalid_refresh_token",
        "token_expired",
        "refresh_token_expired",
        "refresh_token_invalidated",
        "refresh_token_reused",
    }
)

#: `agent_name_hint`: "your app's actual name", the same on every installation.
#: Sent only when registering; the user may rename it before approving.
AGENT_NAME = "Salli"
#: The loopback callback's path. Only the port may vary ("Keep the scheme, host,
#: and path unchanged"), and the host is 127.0.0.1, never `localhost`.
CALLBACK_PATH = "/auth/callback"
_LOOPBACK = re.compile(r"^http://127\.0\.0\.1:(\d{1,5})/auth/callback$")

#: How long a fetched JWKS is trusted before it is fetched again.
_JWKS_TTL = 3600.0
#: Clock skew allowed when checking an ID token's times: "only a small
#: clock-skew tolerance".
_LEEWAY = 30

HttpFactory = Callable[[], httpx.AsyncClient]
Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class TokenSet:
    """What the token endpoint returned (token-reference, "Token response")."""

    access_token: str
    refresh_token: str | None
    id_token: str | None
    scopes: tuple[str, ...]
    #: Seconds the access token lasts from when the response was received.
    expires_in: int | None
    earliest_refresh_at: dt.datetime | None
    token_type: str = "Bearer"

    @property
    def plan_granted(self) -> bool:
        return PLAN_SCOPE in self.scopes

    def expires_at(self, received_at: dt.datetime) -> dt.datetime | None:
        if self.expires_in is None:
            return None
        return received_at + dt.timedelta(seconds=self.expires_in)


def _instant(value: Any) -> dt.datetime | None:
    """A moment given as Unix seconds or as ISO 8601; None when it is neither."""
    if isinstance(value, bool) or value in (None, ""):
        return None
    if isinstance(value, int | float):
        return dt.datetime.fromtimestamp(int(value), dt.UTC)
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


def token_set(body: dict[str, Any]) -> TokenSet:
    """A token response as a TokenSet. Its `expires_in` counts from when the
    response was received ("saved_at" in OpenAI's example record)."""
    raw_expiry = body.get("expires_in")
    expires_in = (
        int(str(raw_expiry).strip())
        if isinstance(raw_expiry, int | str) and str(raw_expiry).strip().isdigit()
        else None
    )
    scope = body.get("scope")
    scopes: tuple[str, ...]
    if isinstance(scope, str):
        scopes = tuple(sorted(set(scope.split())))
    elif isinstance(scope, list):
        scopes = tuple(sorted({str(s) for s in cast(list[Any], scope)}))
    else:
        scopes = ()
    access = body.get("access_token")
    if not isinstance(access, str) or not access:
        raise ValueError("The token response has no access token")
    refresh = body.get("refresh_token")
    id_token = body.get("id_token")
    return TokenSet(
        access_token=access,
        refresh_token=refresh if isinstance(refresh, str) and refresh else None,
        id_token=id_token if isinstance(id_token, str) and id_token else None,
        scopes=scopes,
        expires_in=expires_in,
        earliest_refresh_at=_instant(body.get("earliest_refresh_at")),
        token_type=str(body.get("token_type") or "Bearer"),
    )


class OAuthUnavailable(Exception):
    """OpenAI could not be reached, or failed on its side. Nothing about the
    credential is known: keep it and try again later."""


class RefreshRefused(Exception):
    """OpenAI refused a refresh for good: the refresh token is unusable, or
    the client is (`invalid_client`). Sign in again."""

    def __init__(self, code: str, *, invalid_client: bool = False) -> None:
        self.code = code
        self.invalid_client = invalid_client
        super().__init__(code)


class SignInError(Exception):
    """A sign-in that cannot be used, said in our own words for the user."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class SignInDeclined(SignInError):
    """The user did not allow it (`error=access_denied`)."""


# ── Signing in: the authorization request and its callback ───────────────────


def pkce_challenge(verifier: str) -> str:
    """S256: the base64url SHA-256 digest of the verifier, without padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def loopback_redirect_uri(port: int) -> str:
    return f"http://127.0.0.1:{port}{CALLBACK_PATH}"


@dataclass(frozen=True)
class PendingSignIn:
    """One authorization attempt: fresh `state`, `nonce` and PKCE verifier,
    and the exact callback URI, kept until its callback is handled."""

    host_id: str
    redirect_uri: str
    state: str
    nonce: str
    code_verifier: str
    #: The account's issued client id when it registered before; None to
    #: register (`client_id=dynamic_agent_client`).
    client_id: str | None = None

    @property
    def registering(self) -> bool:
        return self.client_id is None

    @property
    def code_challenge(self) -> str:
        return pkce_challenge(self.code_verifier)


def begin_sign_in(
    *, host_id: str, redirect_uri: str, client_id: str | None = None
) -> PendingSignIn:
    """A new attempt, with its own random state, nonce and verifier."""
    if not _LOOPBACK.match(redirect_uri):
        raise ValueError(
            f"The callback must be http://127.0.0.1:<port>{CALLBACK_PATH}, not {redirect_uri!r}"
        )
    if not host_id:
        raise ValueError("A sign-in needs this host's ext_agent_host_id")
    return PendingSignIn(
        host_id=host_id,
        redirect_uri=redirect_uri,
        state=secrets.token_urlsafe(32),
        nonce=secrets.token_urlsafe(32),
        # 64 random bytes: 86 characters from the unreserved set, within
        # PKCE's 43-128.
        code_verifier=secrets.token_urlsafe(64),
        client_id=client_id if client_id and client_id != DYNAMIC_CLIENT_ID else None,
    )


def authorization_url(
    pending: PendingSignIn,
    *,
    login_hint: str | None = None,
    id_token_hint: str | None = None,
    ask_consent: bool = False,
) -> str:
    """The URL to open in the system browser (sign-in, step 2).

    Registering sends `client_id=dynamic_agent_client` with `agent_name_hint`;
    signing in again sends the issued client id, no name, and the hints for
    the account. Every attempt sends this host's `ext_agent_host_id`, the plan
    scopes, the resource, and PKCE S256. `ask_consent` (`prompt=consent`) is
    for turning plan use on after it was declined, never an ordinary sign-in.

    A URL with an `id_token_hint` must not be logged.
    """
    params: dict[str, str] = {"client_id": pending.client_id or DYNAMIC_CLIENT_ID}
    if pending.registering:
        params["agent_name_hint"] = AGENT_NAME
    else:
        if id_token_hint:
            params["id_token_hint"] = id_token_hint
        if login_hint:
            params["login_hint"] = login_hint
    params.update(
        {
            "ext_agent_host_id": pending.host_id,
            "response_type": "code",
            "redirect_uri": pending.redirect_uri,
            "scope": " ".join(SCOPES),
            "resource": RESOURCE,
            "state": pending.state,
            "nonce": pending.nonce,
            "code_challenge": pending.code_challenge,
            "code_challenge_method": "S256",
        }
    )
    if ask_consent and not pending.registering:
        params["prompt"] = "consent"
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


@dataclass(frozen=True)
class Callback:
    code: str
    #: The issued client id the code belongs to.
    client_id: str


def read_callback(pending: PendingSignIn, query: Mapping[str, str]) -> Callback:
    """The authorization code and client id from the loopback callback, once
    `state` matches (sign-in, step 3). A registration must return its issued
    client id; a sign-in again may omit it, but never return another."""
    if not hmac.compare_digest(str(query.get("state", "")), pending.state):
        raise SignInError(
            "The sign-in could not be verified: it did not come from this attempt. "
            "Please start again."
        )
    error = str(query.get("error", ""))
    if error == "access_denied":
        raise SignInDeclined(
            "Salli was not allowed to use your ChatGPT plan, so nothing was connected. "
            "You can try again, or add your own API key instead."
        )
    if error:
        shown = error if re.fullmatch(r"[a-z_]{1,64}", error) else "unknown error"
        raise SignInError(f"ChatGPT could not complete the sign-in ({shown}). Please try again.")
    code = str(query.get("code", ""))
    if not code:
        raise SignInError("ChatGPT's answer had no sign-in code. Please try again.")
    returned = str(query.get("client_id", ""))
    if pending.registering:
        if not returned or returned == DYNAMIC_CLIENT_ID:
            raise SignInError("ChatGPT did not finish registering Salli. Please try again.")
        return Callback(code=code, client_id=returned)
    assert pending.client_id is not None
    if returned and returned != pending.client_id:
        raise SignInError(
            "ChatGPT answered for a different registration of Salli, so it was not used. "
            "Please try again."
        )
    return Callback(code=code, client_id=pending.client_id)


def unverified_claims(token: str) -> dict[str, Any]:
    """A JWT's claims without checking its signature, for consistency checks
    only (never for trust). Empty when it is not a JWT."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded: Any = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, TypeError):
        return {}
    return cast(dict[str, Any], decoded) if isinstance(decoded, dict) else {}


def _error_code(response: httpx.Response) -> str:
    """The machine-readable code of an OAuth error: `{"error": "code"}`, or
    OpenAI's `{"error": {"code": ...}}`. Never its description, which is not
    for parsing and may quote what was sent."""
    try:
        body: Any = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    error: Any = cast(dict[str, Any], body).get("error")
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        return str(cast(dict[str, Any], error).get("code") or "")
    return ""


def default_http() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0))


class ChatGPTOAuth:
    """OpenAI's auth server and the model list, over httpx. `http_factory`
    makes the client (tests pass one on httpx.MockTransport)."""

    def __init__(self, http_factory: HttpFactory | None = None, sleep: Sleep = asyncio.sleep):
        self._http_factory = http_factory or default_http
        self._sleep = sleep
        self._jwks_cache: tuple[float, list[dict[str, Any]]] | None = None

    @asynccontextmanager
    async def _http(self) -> AsyncGenerator[httpx.AsyncClient, None]:
        async with self._http_factory() as client:
            yield client

    async def _post_form(self, url: str, form: dict[str, str]) -> httpx.Response:
        try:
            async with self._http() as http:
                return await http.post(url, data=form, headers={"Accept": "application/json"})
        except httpx.HTTPError:
            raise OAuthUnavailable("OpenAI's sign-in service could not be reached") from None

    async def refresh(self, *, client_id: str, refresh_token: str) -> TokenSet:
        """Renew with the rotating refresh token. The issued client id, never
        `dynamic_agent_client`; no `scope`, which keeps the grant as it is
        (accounts-and-sessions, "Refreshing tokens"). The answer carries a
        replacement refresh token: the one sent is spent either way."""
        response = await self._post_form(
            TOKEN_URL,
            {
                "grant_type": "refresh_token",
                "client_id": client_id,
                "refresh_token": refresh_token,
                "resource": RESOURCE,
            },
        )
        if response.status_code == 200:
            try:
                return token_set(response.json())
            except ValueError:
                # The old refresh token is spent either way; say so plainly
                # rather than as a bad request of the user's.
                raise OAuthUnavailable("OpenAI's renewal answer could not be read") from None
        code = _error_code(response)
        if code == "invalid_client":
            raise RefreshRefused(code, invalid_client=True)
        if code in _UNUSABLE_REFRESH:
            raise RefreshRefused(code)
        # Anything else says nothing certain about the token, and credentials
        # are never cleared on a guess: errors-and-recovery keeps them through
        # a temporary network or infrastructure failure.
        _log.warning(
            "ChatGPT token renewal failed with HTTP %s (%s)", response.status_code, code or "-"
        )
        raise OAuthUnavailable(f"OpenAI answered {response.status_code}")

    async def revoke(self, *, client_id: str, refresh_token: str, attempts: int = 3) -> bool:
        """End the renewable session (accounts-and-sessions, "End the
        renewable session"). An empty 200 is success, even for a token that is
        already invalid; a network failure or a 5xx is retried with backoff.
        False when it could not be confirmed."""
        for attempt in range(attempts):
            try:
                response = await self._post_form(
                    REVOKE_URL,
                    {
                        "token": refresh_token,
                        "token_type_hint": "refresh_token",
                        "client_id": client_id,
                    },
                )
            except OAuthUnavailable:
                response = None
            if response is not None and response.status_code == 200:
                return True
            if response is not None and response.status_code < 500:
                _log.warning(
                    "ChatGPT session revocation refused with HTTP %s", response.status_code
                )
                return False
            if attempt + 1 < attempts:
                await self._sleep(0.5 * 2**attempt)
        return False

    async def list_models(self, access_token: str) -> list[dict[str, Any]]:
        """The account's model catalogue (`GET /v1/models` with the plan's own
        token, models-and-inference step 1), in the server's order. Raises
        the typed error for a refusal (see responses.error_for)."""
        from salli.adapters.llm.responses import error_for
        from salli.domain.llm import LLMProviderUnavailable

        try:
            async with self._http() as http:
                response = await http.get(
                    MODELS_URL, headers={"Authorization": f"Bearer {access_token}"}
                )
        except httpx.HTTPError:
            raise LLMProviderUnavailable(
                "Couldn't reach OpenAI to list your models. Please try again in a moment.",
                provider="chatgpt",
            ) from None
        if response.status_code != 200:
            raise error_for(
                "chatgpt", status=response.status_code, code=_error_code(response) or None
            )
        body: Any = response.json()
        models: Any = cast(dict[str, Any], body).get("models") if isinstance(body, dict) else None
        if not isinstance(models, list):
            return []
        return [cast(dict[str, Any], m) for m in cast(list[Any], models) if isinstance(m, dict)]

    # ── Signing in ────────────────────────────────────────────────────────────

    async def exchange_code(self, pending: PendingSignIn, callback: Callback) -> TokenSet:
        """Redeem the code (sign-in, step 3): the issued client id, the code,
        the PKCE verifier, and the same redirect URI and resource as the
        authorization request. No client secret: this is a public client."""
        response = await self._post_form(
            TOKEN_URL,
            {
                "grant_type": "authorization_code",
                "client_id": callback.client_id,
                "code": callback.code,
                "code_verifier": pending.code_verifier,
                "redirect_uri": pending.redirect_uri,
                "resource": RESOURCE,
            },
        )
        if response.status_code == 200:
            return token_set(response.json())
        code = _error_code(response)
        if code == "invalid_grant":
            # "discard that code and start a fresh authorization"
            raise SignInError(
                "That sign-in code was already used or has expired. Please sign in again."
            )
        if response.status_code >= 500:
            raise OAuthUnavailable(f"OpenAI answered {response.status_code}")
        raise SignInError("ChatGPT refused the sign-in. Please try again.")

    async def _jwks(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        cached = self._jwks_cache
        if cached is not None and not refresh and time.monotonic() - cached[0] < _JWKS_TTL:
            return cached[1]
        try:
            async with self._http() as http:
                response = await http.get(JWKS_URL)
        except httpx.HTTPError:
            raise OAuthUnavailable("OpenAI's signing keys could not be fetched") from None
        if response.status_code != 200:
            raise OAuthUnavailable(f"OpenAI's signing keys: HTTP {response.status_code}")
        body: Any = response.json()
        keys: Any = cast(dict[str, Any], body).get("keys") if isinstance(body, dict) else None
        found = [
            cast(dict[str, Any], k) for k in cast(list[Any], keys or []) if isinstance(k, dict)
        ]
        self._jwks_cache = (time.monotonic(), found)
        return found

    async def _signing_key(self, kid: str) -> dict[str, Any]:
        for refresh in (False, True):
            # An unfamiliar `kid` fetches the keys again, once: OpenAI rotates them.
            for key in await self._jwks(refresh=refresh):
                if key.get("kid") == kid:
                    return key
        raise SignInError("The ChatGPT sign-in was signed with a key OpenAI does not publish.")

    async def verify_id_token(
        self,
        id_token: str,
        *,
        client_id: str,
        nonce: str | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        """The ID token's claims, once verified (sign-in, step 4): its RS256
        signature against OpenAI's published JWKS, the issuer, the audience
        (the issued client id), its expiry, and the nonce this attempt sent.
        With the access token, its `at_hash` binding too, when there is one.

        A valid ID token says who signed in. It does not, alone, allow plan
        use: that is the granted `chatgpt.tokens.use.direct` scope.
        """
        from jose import jwt as jose_jwt  # pyright: ignore[reportMissingTypeStubs]
        from jose.exceptions import (  # pyright: ignore[reportMissingTypeStubs]
            ExpiredSignatureError,
            JWTError,
        )

        jwt: Any = jose_jwt
        try:
            header: dict[str, Any] = jwt.get_unverified_header(id_token)
        except JWTError:
            raise SignInError("The ChatGPT sign-in could not be read.") from None
        if header.get("alg") != "RS256":
            raise SignInError("The ChatGPT sign-in was not signed the way OpenAI signs.")
        key = await self._signing_key(str(header.get("kid", "")))
        try:
            claims: dict[str, Any] = jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                audience=client_id,
                issuer=ISSUER,
                access_token=access_token,
                options={
                    "leeway": _LEEWAY,
                    "require_exp": True,
                    "require_iat": True,
                    "require_sub": True,
                },
            )
        except ExpiredSignatureError:
            raise SignInError("This ChatGPT sign-in has expired. Please sign in again.") from None
        except JWTError:
            raise SignInError("The ChatGPT sign-in could not be verified.") from None
        if nonce is not None and not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
            raise SignInError("The ChatGPT sign-in was not the one this attempt asked for.")
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise SignInError("The ChatGPT sign-in did not say which account it is.")
        return claims
