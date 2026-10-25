"""
McpOAuthService — Salli's OAuth 2.1 authorization server. It issues tokens
scoped to one user's account for two kinds of client:

- AI clients (Claude, ChatGPT, …) using the MCP server mounted at /mcp.
  These tokens are for the MCP resource and stop working the moment the user
  switches MCP off. They read (`mcp:read`); they change anything only with
  `mcp:write`, which the person ticks on the consent page ("Allow changes",
  unticked to begin with). The Salli app's own AI always holds it: the app
  asks the person before every change. The scope a client asks for is not
  what it gets: a grant records only what Salli granted, and a grant from
  before the scopes (no `mcp:write`) only reads.
- Salli's own clients, the `salli` CLI first, using the REST API under /v1.
  These tokens are for the API resource (RFC 8707 `resource={base}/v1`), and
  the MCP switch has nothing to do with them.

A token is only accepted by the resource it was issued for, so a token an AI
client holds cannot be replayed against the REST API, or the reverse.

This app is both the Authorization Server (this file + mcp_oauth router) and
the Resource Server (mcp_server.py's TokenVerifier) — a deliberate choice over
the MCP SDK's less-documented OAuthAuthorizationServerProvider protocol, which
gives full control over schema, consent, and validation.

Flow:
  1. Client calls POST /mcp/oauth/register (Dynamic Client Registration).
  2. Client redirects the user's browser to GET /mcp/oauth/authorize.
  3. We validate the request (client, redirect_uri, PKCE) and redirect the
     browser to the consent page with a short-lived signed token (an "ART" —
     authorization request token) carrying the pending request — nothing is
     persisted to the DB until the user actually decides.
  4. Salli's own consent page (mcp_consent_page.py) takes the user's email
     and password with their Allow/Deny decision. A deployment's web app,
     holding the user's session, can instead call GET .../consent-info to
     show what's being requested, then POST .../consent with the decision.
  5. On Allow, we mint a one-time authorization code and redirect back to the
     client's redirect_uri. The client exchanges it at POST /mcp/oauth/token.

A native app's loopback redirect (http://127.0.0.1/callback) matches on any
port (RFC 8252 §7.3), since the app listens wherever the OS gives it a port.
A client registers https redirects, or loopback ones; nothing else. Salli's
own CLI, on a machine without a browser, uses the device grant (RFC 8628)
instead: it gets a short code the person approves on the device page. No
other client may: a code to approve is too easy to phish with.

Salli's console (`salli-console`, docs/design/console.md) is the other first
party client. Its one redirect is `{SALLI_PUBLIC_URL}/console/callback`,
computed from the setting rather than stored and matched exactly (no loopback
rule); it signs in to the API only, only where the public URL is HTTPS or
localhost, and not at all while SALLI_CONSOLE is off.

**Grants.** Each approval starts a grant: one sign-in, which every token
issued from it belongs to, through every refresh. A grant records when the
person's password was checked (`authenticated_at`), which the console's
step-up reads (application/permissions.py). The console's grants end
SALLI_CONSOLE_SIGN_IN_HOURS after it, and an AI client's (any but Salli's
own) MCP_GRANT_LIFETIME_DAYS after it, however often they refresh; the CLI's
and the app's have no such end. Refresh
tokens rotate, and a rotated one presented again revokes its whole grant, for
every client: a thief and the person can't both keep going, and the person
finds out by being signed out. Revoking any token of a grant (RFC 7009)
revokes the grant.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urlparse

import jwt

from salli.application.ports import McpConnectionRow, SignInGrantRow

_ART_ISSUER = "salli-mcp-oauth"
_log = logging.getLogger(__name__)

DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
_DEVICE_CODE_TTL_SECONDS = 600
_DEVICE_POLL_INTERVAL_SECONDS = 5
# No vowels (no words), no lookalikes (0/O, 1/I/L): easy to read off a screen
# and type on a phone. 20^8 codes, each valid for ten minutes.
_USER_CODE_ALPHABET = "BCDFGHJKMNPQRSTVWXZ"
_LOOPBACK_HOSTS = ("127.0.0.1", "[::1]", "localhost")

MCP = "mcp"
API = "api"

#: An MCP connection's scopes. Reading needs no scope (grants from before
#: there were scopes still read); every tool that changes anything needs
#: `mcp:write` (mcp_server.py checks it in one place).
MCP_READ = "mcp:read"
MCP_WRITE = "mcp:write"

#: The `salli` CLI's client: first party, seeded by core_0011, never
#: registered. Advertised in /v1/meta so the CLI signs in as it.
CLI_CLIENT_ID = "salli-cli"
#: The console's client: first party, seeded by core_0021. Its redirect is
#: computed from SALLI_PUBLIC_URL (`console_redirect_uri`).
CONSOLE_CLIENT_ID = "salli-console"
#: Where the console receives its code, under SALLI_PUBLIC_URL.
CONSOLE_CALLBACK_PATH = "/console/callback"
#: The phone app's client: first party, seeded by core_0022. A native app's
#: private-use URI scheme (RFC 8252, section 7.1), the reverse of salli.money,
#: is its one redirect, stored and matched exactly. It signs in to the API as
#: the person, and to MCP for the AI the person set up in the app.
MOBILE_CLIENT_ID = "salli-mobile"
MOBILE_REDIRECT_URI = "money.salli.app:/oauth/callback"
#: How often a grant's `last_used_at` is written, at most.
_TOUCH_EVERY = timedelta(minutes=1)

# Recognisable prefixes, like personal access tokens' `salli_pat_`: secret
# scanners can spot a leaked one, and the API's development fallback can tell
# a Salli token from a user id without a lookup. Tokens issued before the
# prefixes have none, and are still verified by lookup.
ACCESS_TOKEN_PREFIX = "salli_at_"
REFRESH_TOKEN_PREFIX = "salli_rt_"
SALLI_TOKEN_PREFIX = "salli_"


def has_salli_prefix(token: str) -> bool:
    """Whether `token` is shaped like one of Salli's own (OAuth or PAT)."""
    return token.startswith(SALLI_TOKEN_PREFIX)


class OAuthError(Exception):
    """A validation failure that must NOT redirect to an unvalidated
    redirect_uri — surfaced as a direct HTTP error instead."""

    #: The RFC 6749 / 8628 error code a token-endpoint failure reports.
    error = "invalid_grant"


class DeviceFlowError(OAuthError):
    """A device-grant poll that has to tell the client something specific:
    keep waiting, slow down, the person said no, or the code expired."""

    def __init__(self, error: str, description: str) -> None:
        super().__init__(description)
        self.error = error


class ConsentError(Exception):
    """A failure during/after consent — the redirect_uri is already known
    good by this point, so callers may redirect back with an error code."""


class RefreshTokenReused(OAuthError):
    """A rotated refresh token was presented again: its grant is now revoked."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def may_change(scope: str) -> bool:
    """Whether a connection with this scope may change the person's data."""
    return MCP_WRITE in scope.split()


def _verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    computed = _b64url(hashlib.sha256(code_verifier.encode("utf-8")).digest())
    return secrets.compare_digest(computed, code_challenge)


class McpOAuthService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        signing_secret: str,
        mcp_resource_url: str,
        consent_url: str,
        auth_code_ttl_seconds: int,
        access_token_ttl_seconds: int,
        refresh_token_ttl_seconds: int,
        art_ttl_seconds: int = 1800,
        api_resource_url: str | None = None,
        device_verification_url: str | None = None,
        console_redirect_uri: str | None = None,
        console_sign_in_hours: int = 12,
        mcp_grant_lifetime_days: int = 90,
        console_secure: bool = True,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._signing_secret = signing_secret
        self._resource = mcp_resource_url
        # The REST API's resource indicator, `{base}/v1`. None: only MCP.
        self._api_resource = api_resource_url
        # Where a person approves a device code (the device page).
        self._device_url = device_verification_url
        # Where the user approves a connection: Salli's own consent page, or a
        # deployment's web app.
        self._consent_url = consent_url
        self._auth_code_ttl = auth_code_ttl_seconds
        self._access_ttl = access_token_ttl_seconds
        self._refresh_ttl = refresh_token_ttl_seconds
        # Generous by design: the consent screen usually sits behind a login
        # redirect (or a first-time signup), which can easily eat several
        # minutes on its own before the user ever gets back here.
        self._art_ttl = art_ttl_seconds
        # The console's one redirect, or None while SALLI_CONSOLE is off.
        self._console_redirect = console_redirect_uri
        self._console_lifetime = timedelta(hours=console_sign_in_hours)
        self._third_party_lifetime = timedelta(days=mcp_grant_lifetime_days)
        # Whether SALLI_PUBLIC_URL is HTTPS or localhost: the console signs
        # in only where a browser treats it as a secure context.
        self._console_secure = console_secure
        self._clock = clock or (lambda: datetime.now(UTC))

    # ── Which resource a token is for ───────────────────────────────────────

    def audience(self, resource: str | None) -> str:
        """MCP or API, from a request's `resource` (RFC 8707). Clients that
        predate resource indicators send none, and they are all MCP clients."""
        if not resource:
            return MCP
        wanted = resource.rstrip("/")
        if wanted == self._resource.rstrip("/"):
            return MCP
        if self._api_resource and wanted == self._api_resource.rstrip("/"):
            return API
        raise OAuthError(f"unknown resource: {resource}")

    async def _may_use(self, user_id: str, audience: str) -> bool:
        # The MCP switch governs AI clients only; the API is the user's own.
        return audience != MCP or await self.is_mcp_enabled(user_id)

    # ── Per-user enable/disable ─────────────────────────────────────────────

    async def is_mcp_enabled(self, user_id: str) -> bool:
        """The user's own toggle, and nothing else: nothing about who they
        are is consulted. Checked live everywhere a token is minted or
        verified, so switching the toggle off kills already-issued tokens on
        the next request rather than needing a separate revocation step.
        """
        async with self._uow_factory() as uow:
            profile: dict[str, Any] | None = await uow.user_profiles.get(user_id)
        return bool(profile and profile.get("mcp_enabled"))

    async def set_mcp_enabled(self, user_id: str, enabled: bool) -> None:
        async with self._uow_factory() as uow:
            await uow.user_profiles.upsert(user_id, {"mcp_enabled": enabled})

    # ── Dynamic Client Registration (RFC 7591) ──────────────────────────────

    async def register_client(
        self, client_name: str | None, redirect_uris: list[str]
    ) -> dict[str, Any]:
        if not redirect_uris:
            raise OAuthError("redirect_uris must be a non-empty list")
        for uri in redirect_uris:
            if not _may_register(uri):
                raise OAuthError(
                    f"invalid redirect_uri: {uri} (https, or http to 127.0.0.1 or localhost)"
                )
        async with self._uow_factory() as uow:
            client = await uow.oauth_clients.register(client_name, redirect_uris)
        return {
            "client_id": client["client_id"],
            "client_name": client["client_name"],
            "redirect_uris": client["redirect_uris"],
            "token_endpoint_auth_method": "none",  # public client, PKCE-only
            # The device grant is the CLI's alone (start_device_authorization).
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        }

    # ── The console's client ─────────────────────────────────────────────────

    @property
    def console_enabled(self) -> bool:
        return self._console_redirect is not None

    def _check_console(self, client_id: str) -> None:
        """The console's client works only while the console is on."""
        if client_id == CONSOLE_CLIENT_ID and not self.console_enabled:
            raise OAuthError("The console is switched off on this server (SALLI_CONSOLE=false).")

    def _redirects_for(self, client: dict[str, Any]) -> list[str]:
        if client["client_id"] == CONSOLE_CLIENT_ID:
            return [self._console_redirect] if self._console_redirect else []
        return list(client["redirect_uris"])

    def _matches(self, client: dict[str, Any], redirect_uri: str) -> bool:
        if client["client_id"] == CONSOLE_CLIENT_ID:
            # Exactly its one redirect: no loopback rule for a web page.
            return redirect_uri in self._redirects_for(client)
        return any(_redirect_matches(redirect_uri, r) for r in client["redirect_uris"])

    def _lifetime_of(self, client_id: str) -> timedelta | None:
        """How long a sign-in of this client lasts at most, refresh or not:
        the console's SALLI_CONSOLE_SIGN_IN_HOURS; none for the CLI's and the
        app's; MCP_GRANT_LIFETIME_DAYS for any other (an AI client)."""
        if client_id == CONSOLE_CLIENT_ID:
            return self._console_lifetime
        if client_id in (CLI_CLIENT_ID, MOBILE_CLIENT_ID):
            return None
        return self._third_party_lifetime

    # ── Authorize → consent handoff ──────────────────────────────────────────

    async def build_consent_redirect(
        self,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        scope: str,
        resource: str | None,
        state: str | None,
        *,
        reauthenticate: bool = False,
    ) -> str:
        """Validates the request and returns the URL to redirect the user's
        browser to (the web app's consent screen). Raises OAuthError on any
        validation failure — those must NOT redirect anywhere, since the
        redirect_uri isn't trusted yet at that point.

        `reauthenticate` (`prompt=login`, or a `max_age`, from the client) is
        a client asking the person to confirm it's them again, as the console
        does before activating tax rules: the page says so. Every approval
        checks the password anyway."""
        if code_challenge_method != "S256":
            raise OAuthError("code_challenge_method must be S256")
        if not code_challenge:
            raise OAuthError("code_challenge is required")

        audience = self.audience(resource)  # refuse an unknown resource before any redirect

        async with self._uow_factory() as uow:
            client = await uow.oauth_clients.get(client_id)
        if client is None:
            raise OAuthError("unknown client_id")
        if client_id == CONSOLE_CLIENT_ID:
            self._check_console(client_id)
            if audience != API:
                raise OAuthError("The console signs in to the API only (resource {base}/v1).")
            if not self._console_secure:
                raise OAuthError(
                    "The console signs in only over HTTPS, or on this machine at localhost: "
                    "set SALLI_PUBLIC_URL to an https:// address (docs/self-host.md)."
                )
        if client_id == MOBILE_CLIENT_ID:
            # The API, as the person; or MCP, for the AI the person set up in
            # the app on their own key: a sign-in of its own, an AI connection
            # like any other (under the MCP switch, listed and ended with the
            # rest), whose every change the person confirms in the app.
            # The same test as the console's: a password crosses a network
            # only encrypted, and a simulator reaches this machine at localhost.
            if not self._console_secure:
                raise OAuthError(
                    "The app signs in only over HTTPS, or on this machine at localhost: "
                    "set SALLI_PUBLIC_URL to an https:// address (docs/self-host.md)."
                )
        if not self._matches(client, redirect_uri) or not (
            client.get("first_party") or _may_register(redirect_uri)
        ):
            raise OAuthError("redirect_uri does not match a registered value for this client")

        art = jwt.encode(
            {
                "iss": _ART_ISSUER,
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "scope": scope,
                "resource": resource,
                "state": state,
                "reauth": reauthenticate,
                # The JWT library checks this against the real time.
                "exp": datetime.now(UTC) + timedelta(seconds=self._art_ttl),
            },
            self._signing_secret,
            algorithm="HS256",
        )
        return f"{self._consent_url}?rt={art}"

    def _decode_art(self, art: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                art, self._signing_secret, algorithms=["HS256"], issuer=_ART_ISSUER
            )
        except jwt.ExpiredSignatureError as exc:
            raise ConsentError(
                "This sign-in link has expired. Go back to the app and start again."
            ) from exc
        except jwt.PyJWTError as exc:
            # Logged apart from expiry: a signature or issuer mismatch means the
            # signing secret changed between mint and verify, not that time ran out.
            _log.warning("MCP consent: ART failed to decode (%s: %s)", type(exc).__name__, exc)
            raise ConsentError(
                "This sign-in link is no longer valid. Go back to the app and start again."
            ) from exc
        return payload

    async def get_consent_info(self, art: str, user_id: str) -> dict[str, Any]:
        payload = self._decode_art(art)
        async with self._uow_factory() as uow:
            client: dict[str, Any] | None = await uow.oauth_clients.get(payload["client_id"])
        return {
            "client_id": payload["client_id"],
            "client_name": (client or {}).get("client_name") or "An application",
            "first_party": bool((client or {}).get("first_party")),
            "scope": payload.get("scope") or "",
            "resource": payload.get("resource"),
            "audience": self.audience(payload.get("resource")),
            "reauthenticate": bool(payload.get("reauth")),
        }

    async def complete_consent(
        self,
        art: str,
        user_id: str,
        approve: bool,
        *,
        password_checked: bool,
        authenticated_at: datetime | None = None,
        allow_changes: bool = False,
    ) -> str:
        """Returns the final redirect_uri (with ?code=... or ?error=...) to
        send the user's browser to.

        `password_checked` says whether this approval came with the person's
        password, checked just now on Salli's own sign-in page. Salli's own
        clients (first party: the CLI, the console) are signed in only that
        way: their tokens hold `tax:activate`, so approving one on the
        strength of any other sign-in (a personal access token without it, or
        a web app's own consent screen) would hand out a permission the caller
        doesn't have. A client this server doesn't know is refused likewise.
        `authenticated_at` is when that password was checked (now, unless
        said otherwise): the sign-in records it, and the console's step-up
        reads it. `allow_changes` is the person ticking "Allow changes": an
        MCP connection gets `mcp:write` only with it (or as the Salli app)."""
        payload = self._decode_art(art)
        redirect_uri = payload["redirect_uri"]
        state = payload.get("state")

        if not approve:
            return _append_query(
                redirect_uri, {"error": "access_denied", **({"state": state} if state else {})}
            )

        self._check_console_consent(payload["client_id"])
        if not password_checked:
            async with self._uow_factory() as uow:
                client: dict[str, Any] | None = await uow.oauth_clients.get(payload["client_id"])
            if client is None or client.get("first_party"):
                raise ConsentError(
                    "Salli's own apps are signed in with your password, on Salli's sign-in page."
                )

        if not await self._may_use(user_id, self.audience(payload.get("resource"))):
            raise ConsentError("MCP access isn't available for this account. Check Settings.")

        code = secrets.token_urlsafe(32)
        now = self._clock()
        async with self._uow_factory() as uow:
            await uow.oauth_tokens.save_authorization_code(
                code=code,
                client_id=payload["client_id"],
                user_id=user_id,
                redirect_uri=redirect_uri,
                code_challenge=payload["code_challenge"],
                scope=self._granted(
                    payload["client_id"],
                    payload.get("scope") or "",
                    payload.get("resource"),
                    allow_changes,
                ),
                resource=payload.get("resource"),
                expires_at=now + timedelta(seconds=self._auth_code_ttl),
                authenticated_at=authenticated_at or now,
            )
        return _append_query(redirect_uri, {"code": code, **({"state": state} if state else {})})

    def _granted(
        self, client_id: str, scope: str, resource: str | None, allow_changes: bool
    ) -> str:
        """The scope an approval grants. An MCP connection reads, and changes
        only if the person allowed it, whatever it asked for; the Salli app's
        AI may change, since the app asks the person before each change."""
        if self.audience(resource) != MCP:
            return scope
        if allow_changes or client_id == MOBILE_CLIENT_ID:
            return f"{MCP_READ} {MCP_WRITE}"
        return MCP_READ

    def _check_console_consent(self, client_id: str) -> None:
        try:
            self._check_console(client_id)
        except OAuthError as exc:
            raise ConsentError(str(exc)) from exc

    # ── Token endpoint ────────────────────────────────────────────────────

    async def exchange_authorization_code(
        self, code: str, redirect_uri: str, client_id: str, code_verifier: str
    ) -> dict[str, Any]:
        # Validate everything before deleting the code — a wrong code_verifier
        # or client_id must not burn a code a legitimate retry still needs.
        async with self._uow_factory() as uow:
            record = await uow.oauth_tokens.get_authorization_code(code)
        if record is None:
            raise OAuthError("invalid or expired authorization code")
        if record["client_id"] != client_id or record["redirect_uri"] != redirect_uri:
            raise OAuthError("client_id/redirect_uri mismatch")
        if not _verify_pkce(code_verifier, record["code_challenge"]):
            raise OAuthError("PKCE verification failed")
        self._check_console(client_id)

        async with self._uow_factory() as uow:
            if not await uow.oauth_tokens.delete_authorization_code(code):
                # Another exchange took it first.
                raise OAuthError("invalid or expired authorization code")
            return await self._start_grant(
                uow,
                client_id=client_id,
                user_id=record["user_id"],
                scope=record["scope"],
                resource=record["resource"],
                authenticated_at=record.get("authenticated_at") or self._clock(),
            )

    async def exchange_refresh_token(self, refresh_token: str, client_id: str) -> dict[str, Any]:
        """Rotate: a new pair in the same grant, the used refresh token
        revoked. A refresh token used a second time revokes its whole grant."""
        token_hash = _hash_token(refresh_token)
        async with self._uow_factory() as uow:
            record = await uow.oauth_tokens.find_refresh_token(token_hash)
        if record is None or record["client_id"] != client_id:
            raise OAuthError("invalid or expired refresh token")
        self._check_console(client_id)
        if record["grant_revoked_at"] is not None:
            raise OAuthError("invalid or expired refresh token")
        if record["revoked_at"] is not None:
            raise await self._reused(record)
        now = self._clock()
        grant_ends = record["grant_expires_at"]
        if (
            record["expires_at"] <= now
            or record["access_revoked_at"] is not None
            or (grant_ends is not None and grant_ends <= now)
        ):
            raise OAuthError("invalid or expired refresh token")
        if not await self._may_use(record["user_id"], self._token_audience(record)):
            raise OAuthError("MCP access has been disabled for this account")

        async with self._uow_factory() as uow:
            claimed = await uow.oauth_tokens.rotate_refresh_token(token_hash)
            if claimed:
                return await self._issue_token_pair(
                    uow,
                    grant_id=record["grant_id"],
                    grant_expires_at=grant_ends,
                    client_id=client_id,
                    user_id=record["user_id"],
                    scope=record["scope"],
                    resource=record["resource"],
                )
        # Another request rotated it between our read and our claim.
        raise await self._reused(record)

    async def _reused(self, record: dict[str, Any]) -> RefreshTokenReused:
        """Revokes the grant of a refresh token used a second time, and
        returns the error to raise."""
        async with self._uow_factory() as uow:
            await uow.oauth_tokens.revoke_grant(record["grant_id"])
        # Which grant, never the token: the log must not hold one.
        _log.warning(
            "OAuth: a rotated refresh token was used again; revoked grant %s (client %s)",
            record["grant_id"],
            record["client_id"],
        )
        return RefreshTokenReused(
            "This refresh token was already used, so the sign-in it belongs to has been "
            "ended. Sign in again."
        )

    async def _start_grant(
        self,
        uow: Any,
        *,
        client_id: str,
        user_id: str,
        scope: str,
        resource: str | None,
        authenticated_at: datetime,
    ) -> dict[str, Any]:
        """A new sign-in, and its first token pair."""
        lifetime = self._lifetime_of(client_id)
        expires_at = authenticated_at + lifetime if lifetime is not None else None
        grant_id = await uow.oauth_tokens.create_grant(
            user_id=user_id,
            client_id=client_id,
            scope=scope,
            resource=resource,
            authenticated_at=authenticated_at,
            expires_at=expires_at,
        )
        return await self._issue_token_pair(
            uow,
            grant_id=grant_id,
            grant_expires_at=expires_at,
            client_id=client_id,
            user_id=user_id,
            scope=scope,
            resource=resource,
        )

    async def _issue_token_pair(
        self,
        uow: Any,
        *,
        grant_id: str,
        grant_expires_at: datetime | None,
        client_id: str,
        user_id: str,
        scope: str,
        resource: str | None,
    ) -> dict[str, Any]:
        access_token = ACCESS_TOKEN_PREFIX + secrets.token_urlsafe(32)
        refresh_token = REFRESH_TOKEN_PREFIX + secrets.token_urlsafe(32)
        now = self._clock()
        access_expires_at = now + timedelta(seconds=self._access_ttl)
        refresh_expires_at = now + timedelta(seconds=self._refresh_ttl)
        # Neither outlives the sign-in's absolute end.
        if grant_expires_at is not None:
            access_expires_at = min(access_expires_at, grant_expires_at)
            refresh_expires_at = min(refresh_expires_at, grant_expires_at)

        token_id = await uow.oauth_tokens.save_access_token(
            token_hash=_hash_token(access_token),
            grant_id=grant_id,
            client_id=client_id,
            user_id=user_id,
            scope=scope,
            resource=resource,
            expires_at=access_expires_at,
        )
        await uow.oauth_tokens.save_refresh_token(
            token_hash=_hash_token(refresh_token),
            grant_id=grant_id,
            access_token_id=token_id,
            client_id=client_id,
            user_id=user_id,
            scope=scope,
            resource=resource,
            expires_at=refresh_expires_at,
        )

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": max(0, int((access_expires_at - now).total_seconds())),
            "refresh_token": refresh_token,
            "scope": scope,
        }

    # ── Verification (used by mcp_server.py's TokenVerifier) ────────────────

    def _token_audience(self, record: dict[str, Any]) -> str:
        try:
            return self.audience(record.get("resource"))
        except OAuthError:
            return "unknown"

    async def verify_access_token(
        self, access_token: str, audience: str = MCP
    ) -> dict[str, Any] | None:
        """Returns the token's record (user_id, client_id, scope, resource,
        expires_at, grant_id, authenticated_at, and its client's name,
        first-party flag and step_up_seconds) or None if the token is
        missing/expired/revoked, its sign-in has ended, it was issued for a
        different resource than `audience`, or — for MCP — MCP has since been
        disabled for that user (checked live, not just at grant time)."""
        async with self._uow_factory() as uow:
            record = await uow.oauth_tokens.get_access_token(_hash_token(access_token))
        if record is None or self._token_audience(record) != audience:
            return None
        if record["client_id"] == CONSOLE_CLIENT_ID and not self.console_enabled:
            return None
        now = self._clock()
        if record["expires_at"] <= now:
            return None
        if not await self._may_use(record["user_id"], audience):
            return None
        last = record.get("last_used_at")
        if record.get("grant_id") and (last is None or now - last > _TOUCH_EVERY):
            async with self._uow_factory() as uow:
                await uow.oauth_tokens.touch_grant(record["grant_id"], now)
        return record

    async def client_name(self, client_id: str) -> str | None:
        """The name a client registered with: recorded as the author of
        what an AI connector writes."""
        async with self._uow_factory() as uow:
            client: dict[str, Any] | None = await uow.oauth_clients.get(client_id)
        return (client or {}).get("client_name") or None

    async def is_salli_token(self, token: str) -> bool:
        """Whether this server ever issued `token`, as an access or a refresh
        token, whatever its state now."""
        async with self._uow_factory() as uow:
            return await uow.oauth_tokens.token_exists(_hash_token(token))

    # ── Revocation ───────────────────────────────────────────────────────

    async def revoke_token_by_value(self, token: str) -> None:
        """RFC 7009 — a client presenting a token it holds (access or
        refresh) to revoke it. Revokes the token's whole grant: signing out
        ends the sign-in, not one token of it."""
        async with self._uow_factory() as uow:
            grant = await uow.oauth_tokens.grant_of_token(_hash_token(token))
            if grant is not None:
                await uow.oauth_tokens.revoke_grant(grant["id"])

    # ── The user's own sign-ins (the API's grants) ──────────────────────────

    async def list_sign_ins(self, user_id: str) -> list[SignInGrantRow]:
        """The user's live OAuth sign-ins to the REST API: the CLI on each
        machine, the console in each tab, any other API client. AI
        connections (MCP) are listed with `list_connections`."""
        if self._api_resource is None:
            return []
        async with self._uow_factory() as uow:
            return await uow.oauth_tokens.list_sign_in_grants(
                user_id, self._api_resource, self._clock()
            )

    async def revoke_sign_in(self, user_id: str, grant_id: str) -> bool:
        """End one of the user's API sign-ins. False if it is not one: not
        theirs, already ended, or an AI connection (revoked with
        `revoke_connection`)."""
        async with self._uow_factory() as uow:
            grant = await uow.oauth_tokens.get_grant(grant_id)
            if (
                grant is None
                or grant["user_id"] != user_id
                or grant["revoked_at"] is not None
                or self._token_audience(grant) != API
            ):
                return False
            return await uow.oauth_tokens.revoke_grant(grant_id, user_id) > 0

    # ── Settings UI: connection management ──────────────────────────────────

    async def list_connections(self, user_id: str) -> list[McpConnectionRow]:
        """The AI clients connected over MCP (not the user's own CLI sessions)."""
        async with self._uow_factory() as uow:
            rows = await uow.oauth_tokens.list_active_connections(user_id)
        return [r for r in rows if self._token_audience(r) == MCP]

    async def revoke_connection(self, user_id: str, token_id: str) -> bool:
        """Disconnect an AI client: every grant it holds for the user over
        MCP, and every token in them, so it cannot come back with a refresh.
        `token_id` is any of its access tokens, expired ones included (the
        refresh token may outlive it). Only AI clients: the user's own
        sign-ins are ended with `revoke_sign_in`."""
        async with self._uow_factory() as uow:
            token = await uow.oauth_tokens.get_access_token_by_id(token_id, user_id)
            if token is None or self._token_audience(token) != MCP:
                return False
            revoked = await uow.oauth_tokens.revoke_client_grant(
                user_id, token["client_id"], token["resource"]
            )
        return revoked > 0

    # ── Metadata (RFC 8414 / RFC 9728) ──────────────────────────────────────

    def authorization_server_metadata(self, issuer: str) -> dict[str, Any]:
        return {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/mcp/oauth/authorize",
            "token_endpoint": f"{issuer}/mcp/oauth/token",
            "registration_endpoint": f"{issuer}/mcp/oauth/register",
            "revocation_endpoint": f"{issuer}/mcp/oauth/revoke",
            "device_authorization_endpoint": f"{issuer}/mcp/oauth/device_authorization",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token", DEVICE_GRANT_TYPE],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        }

    # ── Device authorization grant (RFC 8628) ───────────────────────────────

    async def start_device_authorization(
        self, client_id: str, scope: str, resource: str | None
    ) -> dict[str, Any]:
        """A device code to poll with and a user code for the person to approve."""
        self.audience(resource)
        if client_id in (CONSOLE_CLIENT_ID, MOBILE_CLIENT_ID):
            # The console and the app sign in through their redirect.
            raise OAuthError(
                "The console and the app sign in with the authorization code grant only."
            )
        async with self._uow_factory() as uow:
            client = await uow.oauth_clients.get(client_id)
            if client is None:
                raise OAuthError("unknown client_id")
            if not client.get("first_party"):
                # A code approved on another device is easy to phish: only
                # Salli's own CLI may ask for one.
                raise OAuthError("Only Salli's own CLI signs in with a device code.")
            device_code = secrets.token_urlsafe(32)
            user_code = "".join(secrets.choice(_USER_CODE_ALPHABET) for _ in range(8))
            await uow.oauth_tokens.save_device_code(
                device_code_hash=_hash_token(device_code),
                user_code=user_code,
                client_id=client_id,
                scope=scope,
                resource=resource,
                interval_seconds=_DEVICE_POLL_INTERVAL_SECONDS,
                expires_at=self._clock() + timedelta(seconds=_DEVICE_CODE_TTL_SECONDS),
            )
        shown = f"{user_code[:4]}-{user_code[4:]}"
        verification_uri = self._device_url or ""
        return {
            "device_code": device_code,
            "user_code": shown,
            "verification_uri": verification_uri,
            "verification_uri_complete": f"{verification_uri}?user_code={shown}",
            "expires_in": _DEVICE_CODE_TTL_SECONDS,
            "interval": _DEVICE_POLL_INTERVAL_SECONDS,
        }

    @staticmethod
    def normalize_user_code(user_code: str) -> str:
        return "".join(ch for ch in user_code.upper() if ch.isalnum())

    async def device_request(self, user_code: str) -> dict[str, Any] | None:
        """What the device page shows: which client, for what — or None."""
        async with self._uow_factory() as uow:
            record = await uow.oauth_tokens.get_device_code_by_user_code(
                self.normalize_user_code(user_code)
            )
            if record is None:
                return None
            client: dict[str, Any] | None = await uow.oauth_clients.get(record["client_id"])
        return {
            "client_name": (client or {}).get("client_name") or "An application",
            "audience": self._token_audience(record),
        }

    async def decide_device(
        self, user_code: str, user_id: str, approve: bool, *, allow_changes: bool = False
    ) -> None:
        async with self._uow_factory() as uow:
            record = await uow.oauth_tokens.get_device_code_by_user_code(
                self.normalize_user_code(user_code)
            )
            if record is None:
                raise ConsentError("That code is not valid, or it has expired.")
            if approve and not await self._may_use(user_id, self._token_audience(record)):
                raise ConsentError("MCP access isn't available for this account. Check Settings.")
            await uow.oauth_tokens.update_device_code(
                record["id"],
                status="approved" if approve else "denied",
                user_id=user_id if approve else None,
                authenticated_at=self._clock() if approve else None,
                scope=self._granted(
                    record["client_id"], record["scope"], record["resource"], allow_changes
                ),
            )

    async def exchange_device_code(self, device_code: str, client_id: str) -> dict[str, Any]:
        now = self._clock()
        async with self._uow_factory() as uow:
            record = await uow.oauth_tokens.get_device_code(_hash_token(device_code))
            if record is None or record["client_id"] != client_id:
                raise DeviceFlowError("invalid_grant", "invalid device code")
            if record["expires_at"] < now:
                raise DeviceFlowError("expired_token", "the code expired; start again")
            last = record["last_polled_at"]
            await uow.oauth_tokens.update_device_code(record["id"], last_polled_at=now)
            # A second of grace: a client polling on its interval can arrive a
            # hair early, and slow_down makes it back off for good.
            if last is not None and (now - last).total_seconds() < record["interval_seconds"] - 1:
                raise DeviceFlowError("slow_down", "polling too fast")
            if record["status"] == "pending":
                raise DeviceFlowError("authorization_pending", "waiting for approval")
            if record["status"] == "denied":
                raise DeviceFlowError("access_denied", "the request was declined")
            if record["status"] != "approved" or not record["user_id"]:
                raise DeviceFlowError("invalid_grant", "this code has already been used")
            await uow.oauth_tokens.update_device_code(record["id"], status="consumed")
            return await self._start_grant(
                uow,
                client_id=client_id,
                user_id=record["user_id"],
                scope=record["scope"],
                resource=record["resource"],
                authenticated_at=record.get("authenticated_at") or now,
            )

    def protected_resource_metadata(self, issuer: str) -> dict[str, Any]:
        return {
            "resource": self._resource,
            "authorization_servers": [issuer],
        }


def _may_register(uri: str) -> bool:
    """A redirect a client may register for itself: https, or http to this
    machine (a native app's loopback redirect, RFC 8252 section 7.3)."""
    parsed = urlparse(uri)
    if not parsed.netloc:
        return False
    loopback = {h.strip("[]") for h in _LOOPBACK_HOSTS}
    return parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname in loopback)


def _redirect_matches(requested: str, registered: str) -> bool:
    """Exact match, or — for a native app's loopback redirect — the same URI on
    any port (RFC 8252 §7.3): the app listens wherever the OS lets it."""
    if requested == registered:
        return True
    want, have = urlparse(requested), urlparse(registered)
    if want.scheme != "http" or have.scheme != "http":
        return False
    if want.hostname is None or have.hostname is None:
        return False
    loopback = {h.strip("[]") for h in _LOOPBACK_HOSTS}
    return (
        want.hostname in loopback
        and want.hostname == have.hostname
        and want.path == have.path
        and want.query == have.query
    )


def _append_query(url: str, params: dict[str, Any]) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{urlencode(params)}"
