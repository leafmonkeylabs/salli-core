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
import datetime as dt
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, cast

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


class OAuthRefused(Exception):
    """OpenAI refused a request with an OAuth error (`code`)."""

    def __init__(self, code: str, status: int) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


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
            return token_set(response.json())
        code = _error_code(response)
        if code == "invalid_client":
            raise RefreshRefused(code, invalid_client=True)
        if code in _UNUSABLE_REFRESH:
            raise RefreshRefused(code)
        # Anything else says nothing certain about the token, and credentials
        # are never cleared on a guess ("Do not erase credentials solely
        # because of a temporary network or infrastructure failure").
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
