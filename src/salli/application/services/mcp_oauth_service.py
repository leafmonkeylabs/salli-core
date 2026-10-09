"""
McpOAuthService — a minimal OAuth 2.1 authorization server so external AI
clients (Claude, ChatGPT, etc.) can obtain a token scoped to one user's
Salli account — reading and writing, exactly as Scrooge (the in-app agent)
already can — via the MCP server mounted at /mcp.

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

_ART_ISSUER = "salli-mcp-oauth"
_log = logging.getLogger(__name__)


class OAuthError(Exception):
    """A validation failure that must NOT redirect to an unvalidated
    redirect_uri — surfaced as a direct HTTP error instead."""


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
    ) -> None:
        self._uow_factory = uow_factory
        self._signing_secret = signing_secret
        self._resource = mcp_resource_url
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
            "grant_types": ["authorization_code", "refresh_token"],
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

        async with self._uow_factory() as uow:
            client = await uow.oauth_clients.get(client_id)
        if client is None:
            raise OAuthError("unknown client_id")
        if redirect_uri not in client["redirect_uris"]:
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

        if not await self.is_mcp_enabled(user_id):
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
        if not await self.is_mcp_enabled(record["user_id"]):
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
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
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

    async def verify_access_token(self, access_token: str) -> dict[str, Any] | None:
        """Returns {user_id, client_id, scope, resource, expires_at} or None
        if the token is missing/expired/revoked, or MCP has since been
        disabled for that user — checked live, not just at grant time."""
        async with self._uow_factory() as uow:
            record = await uow.oauth_tokens.get_access_token(_hash_token(access_token))
        if record is None:
            return None
        if not await self.is_mcp_enabled(record["user_id"]):
            return None
        return record

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

    async def list_connections(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return await uow.oauth_tokens.list_active_connections(user_id)

    async def revoke_connection(self, user_id: str, token_id: str) -> bool:
        async with self._uow_factory() as uow:
            return await uow.oauth_tokens.revoke_access_token(token_id, user_id)

    # ── Metadata (RFC 8414 / RFC 9728) ──────────────────────────────────────

    def authorization_server_metadata(self, issuer: str) -> dict[str, Any]:
        return {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/mcp/oauth/authorize",
            "token_endpoint": f"{issuer}/mcp/oauth/token",
            "registration_endpoint": f"{issuer}/mcp/oauth/register",
            "revocation_endpoint": f"{issuer}/mcp/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        }

    def protected_resource_metadata(self, issuer: str) -> dict[str, Any]:
        return {
            "resource": self._resource,
            "authorization_servers": [issuer],
        }


def _append_query(url: str, params: dict[str, Any]) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{urlencode(params)}"
