"""
McpOAuthService — Salli's OAuth 2.1 authorization server. It issues tokens
scoped to one user's account for two kinds of client:

- AI clients (Claude, ChatGPT, …) using the MCP server mounted at /mcp —
  reading and writing, exactly as Scrooge (the in-app agent) already can.
  These tokens are for the MCP resource and stop working the moment the user
  switches MCP off.
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
     browser to the web app's consent screen with a short-lived signed token
     (an "ART" — authorization request token) carrying the pending request —
     nothing is persisted to the DB until the user actually decides.
  4. The web app (already holding the user's Supabase session) calls
     GET .../consent-info to show what's being requested, then
     POST .../consent with the user's Allow/Deny decision.
  5. On Allow, we mint a one-time authorization code and redirect back to the
     client's redirect_uri. The client exchanges it at POST /mcp/oauth/token.

A native app's loopback redirect (http://127.0.0.1/callback) matches on any
port (RFC 8252 §7.3), since the app listens wherever the OS gives it a port.
A client on a machine without a browser uses the device grant (RFC 8628)
instead: it gets a short code the person approves on the device page.
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

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from salli.application.ports import McpConnectionRow

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

#: The `salli` CLI's client: first party, seeded by core_0011, never
#: registered. Advertised in /v1/meta so the CLI signs in as it.
CLI_CLIENT_ID = "salli-cli"

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


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
        """The user's own toggle, and nothing else.

        No longer plan-gated: tiers differ only in AI usage allowance now, so
        every feature — MCP included — is available on Free. Still checked live
        everywhere a token is minted or verified, so switching the toggle off
        kills already-issued tokens on the next request rather than needing a
        separate revocation step.
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
            parsed = urlparse(uri)
            if parsed.scheme not in ("https", "http") or not parsed.netloc:
                raise OAuthError(f"invalid redirect_uri: {uri}")
        async with self._uow_factory() as uow:
            client = await uow.oauth_clients.register(client_name, redirect_uris)
        return {
            "client_id": client["client_id"],
            "client_name": client["client_name"],
            "redirect_uris": client["redirect_uris"],
            "token_endpoint_auth_method": "none",  # public client, PKCE-only
            # Every client may use any grant this server supports.
            "grant_types": ["authorization_code", "refresh_token", DEVICE_GRANT_TYPE],
            "response_types": ["code"],
        }

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
    ) -> str:
        """Validates the request and returns the URL to redirect the user's
        browser to (the web app's consent screen). Raises OAuthError on any
        validation failure — those must NOT redirect anywhere, since the
        redirect_uri isn't trusted yet at that point."""
        if code_challenge_method != "S256":
            raise OAuthError("code_challenge_method must be S256")
        if not code_challenge:
            raise OAuthError("code_challenge is required")

        self.audience(resource)  # refuse an unknown resource before any redirect

        async with self._uow_factory() as uow:
            client = await uow.oauth_clients.get(client_id)
        if client is None:
            raise OAuthError("unknown client_id")
        if not any(_redirect_matches(redirect_uri, r) for r in client["redirect_uris"]):
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
        except ExpiredSignatureError as exc:
            raise ConsentError(
                "This authorization request has expired. Please try connecting again."
            ) from exc
        except JWTError as exc:
            # Logged distinctly from genuine expiry — a signature/issuer
            # mismatch here means signing_secret changed between mint and
            # verify (e.g. an env var rotation), not that time ran out.
            _log.warning("MCP consent: ART failed to decode (%s: %s)", type(exc).__name__, exc)
            raise ConsentError(
                "This connection link is no longer valid. Please try connecting again."
            ) from exc
        return payload

    async def get_consent_info(self, art: str, user_id: str) -> dict[str, Any]:
        payload = self._decode_art(art)
        async with self._uow_factory() as uow:
            client: dict[str, Any] | None = await uow.oauth_clients.get(payload["client_id"])
        return {
            "client_name": (client or {}).get("client_name") or "An application",
            "scope": payload.get("scope") or "",
            "resource": payload.get("resource"),
            "audience": self.audience(payload.get("resource")),
        }

    async def complete_consent(self, art: str, user_id: str, approve: bool) -> str:
        """Returns the final redirect_uri (with ?code=... or ?error=...) to
        send the user's browser to."""
        payload = self._decode_art(art)
        redirect_uri = payload["redirect_uri"]
        state = payload.get("state")

        if not approve:
            return _append_query(
                redirect_uri, {"error": "access_denied", **({"state": state} if state else {})}
            )

        if not await self._may_use(user_id, self.audience(payload.get("resource"))):
            raise ConsentError("MCP access isn't available for this account. Check Settings.")

        code = secrets.token_urlsafe(32)
        async with self._uow_factory() as uow:
            await uow.oauth_tokens.save_authorization_code(
                code=code,
                client_id=payload["client_id"],
                user_id=user_id,
                redirect_uri=redirect_uri,
                code_challenge=payload["code_challenge"],
                scope=payload.get("scope") or "",
                resource=payload.get("resource"),
                expires_at=datetime.now(UTC) + timedelta(seconds=self._auth_code_ttl),
            )
        return _append_query(redirect_uri, {"code": code, **({"state": state} if state else {})})

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

        async with self._uow_factory() as uow:
            await uow.oauth_tokens.delete_authorization_code(code)

        return await self._issue_token_pair(
            client_id=client_id,
            user_id=record["user_id"],
            scope=record["scope"],
            resource=record["resource"],
        )

    async def exchange_refresh_token(self, refresh_token: str, client_id: str) -> dict[str, Any]:
        token_hash = _hash_token(refresh_token)
        async with self._uow_factory() as uow:
            record = await uow.oauth_tokens.get_refresh_token(token_hash)
        if record is None or record["client_id"] != client_id:
            raise OAuthError("invalid or expired refresh token")
        if not await self._may_use(record["user_id"], self._token_audience(record)):
            raise OAuthError("MCP access has been disabled for this account")

        # Rotate: revoke the used refresh token, issue a fresh pair.
        async with self._uow_factory() as uow:
            await uow.oauth_tokens.revoke_refresh_token(token_hash)
        return await self._issue_token_pair(
            client_id=client_id,
            user_id=record["user_id"],
            scope=record["scope"],
            resource=record["resource"],
        )

    async def _issue_token_pair(
        self, client_id: str, user_id: str, scope: str, resource: str | None
    ) -> dict[str, Any]:
        access_token = ACCESS_TOKEN_PREFIX + secrets.token_urlsafe(32)
        refresh_token = REFRESH_TOKEN_PREFIX + secrets.token_urlsafe(32)
        access_expires_at = datetime.now(UTC) + timedelta(seconds=self._access_ttl)
        refresh_expires_at = datetime.now(UTC) + timedelta(seconds=self._refresh_ttl)

        async with self._uow_factory() as uow:
            token_id = await uow.oauth_tokens.save_access_token(
                token_hash=_hash_token(access_token),
                client_id=client_id,
                user_id=user_id,
                scope=scope,
                resource=resource,
                expires_at=access_expires_at,
            )
            await uow.oauth_tokens.save_refresh_token(
                token_hash=_hash_token(refresh_token),
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
            "expires_in": self._access_ttl,
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
        """Returns {user_id, client_id, scope, resource, expires_at} or None
        if the token is missing/expired/revoked, was issued for a different
        resource than `audience`, or — for MCP — MCP has since been disabled
        for that user (checked live, not just at grant time)."""
        async with self._uow_factory() as uow:
            record = await uow.oauth_tokens.get_access_token(_hash_token(access_token))
        if record is None or self._token_audience(record) != audience:
            return None
        if not await self._may_use(record["user_id"], audience):
            return None
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
        """RFC 7009 — a client presenting a token it holds (access or refresh)
        to revoke it. Best-effort: tries both token kinds."""
        token_hash = _hash_token(token)
        async with self._uow_factory() as uow:
            access = await uow.oauth_tokens.get_access_token(token_hash)
            if access is not None:
                await uow.oauth_tokens.revoke_access_token(access["id"], access["user_id"])
                return
            await uow.oauth_tokens.revoke_refresh_token(token_hash)

    # ── Settings UI: connection management ──────────────────────────────────

    async def list_connections(self, user_id: str) -> list[McpConnectionRow]:
        """The AI clients connected over MCP (not the user's own CLI sessions)."""
        async with self._uow_factory() as uow:
            rows = await uow.oauth_tokens.list_active_connections(user_id)
        return [r for r in rows if self._token_audience(r) == MCP]

    async def revoke_connection(self, user_id: str, token_id: str) -> bool:
        """Disconnect an AI client: every token of its grant, the refresh
        tokens and any earlier rotated access tokens too, so it cannot come
        back with a refresh. `token_id` is any of the grant's access tokens,
        expired ones included (the refresh token may outlive it). Only AI
        clients: a CLI session's token is not a connection, and is signed out
        with `salli logout`."""
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
        async with self._uow_factory() as uow:
            if await uow.oauth_clients.get(client_id) is None:
                raise OAuthError("unknown client_id")
            device_code = secrets.token_urlsafe(32)
            user_code = "".join(secrets.choice(_USER_CODE_ALPHABET) for _ in range(8))
            await uow.oauth_tokens.save_device_code(
                device_code_hash=_hash_token(device_code),
                user_code=user_code,
                client_id=client_id,
                scope=scope,
                resource=resource,
                interval_seconds=_DEVICE_POLL_INTERVAL_SECONDS,
                expires_at=datetime.now(UTC) + timedelta(seconds=_DEVICE_CODE_TTL_SECONDS),
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
            client = await uow.oauth_clients.get(record["client_id"])
        return {
            "client_name": (client or {}).get("client_name") or "An application",
            "audience": self._token_audience(record),
        }

    async def decide_device(self, user_code: str, user_id: str, approve: bool) -> None:
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
            )

    async def exchange_device_code(self, device_code: str, client_id: str) -> dict[str, Any]:
        now = datetime.now(UTC)
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
        return await self._issue_token_pair(
            client_id=client_id,
            user_id=record["user_id"],
            scope=record["scope"],
            resource=record["resource"],
        )

    def protected_resource_metadata(self, issuer: str) -> dict[str, Any]:
        return {
            "resource": self._resource,
            "authorization_servers": [issuer],
        }


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
