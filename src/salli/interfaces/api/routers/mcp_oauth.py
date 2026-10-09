"""
MCP OAuth router — the authorization-server half of MCP support.

- /.well-known/*                    — RFC 8414 / RFC 9728 discovery metadata
- POST /mcp/oauth/register          — Dynamic Client Registration (RFC 7591)
- GET  /mcp/oauth/authorize         — validates the request, redirects the
                                       browser to the web app's consent screen
- GET  /mcp/oauth/consent-info      — (authenticated) what's being requested
- POST /mcp/oauth/consent           — (authenticated) Allow/Deny
- POST /mcp/oauth/device_authorization — RFC 8628, sign-in for a device
                                       without a browser (the CLI over SSH)
- POST /mcp/oauth/token             — authorization_code / refresh_token /
                                       device_code grants
- POST /mcp/oauth/revoke            — RFC 7009, client-presented token revocation
- GET/DELETE /mcp/connections       — (authenticated) Settings UI surface

The actual MCP protocol endpoint (/mcp) lives in mcp_server.py.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from salli.application.services.mcp_oauth_service import (
    DEVICE_GRANT_TYPE,
    ConsentError,
    OAuthError,
)
from salli.config import get_settings
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(tags=["mcp-oauth"])


def _issuer() -> str:
    return get_settings().mcp_public_base_url.rstrip("/")


# ── Discovery metadata ───────────────────────────────────────────────────────


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata(svc: AppServices):
    return svc.mcp_oauth.authorization_server_metadata(_issuer())


@router.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata(svc: AppServices):
    return svc.mcp_oauth.protected_resource_metadata(_issuer())


# ── Dynamic Client Registration ──────────────────────────────────────────────

# Best-effort in-memory rate limit for the (intentionally unauthenticated,
# per RFC 7591) registration endpoint — a per-process sliding window, good
# enough to stop unbounded junk registration from a single dev/test client.
# Production deployments should also rate-limit at the reverse proxy.
_register_hits: dict[str, list[float]] = {}
_REGISTER_WINDOW_SECONDS = 60.0
_REGISTER_MAX_PER_WINDOW = 10


def _check_register_rate_limit(client_ip: str) -> None:
    now = time.time()
    hits = [t for t in _register_hits.get(client_ip, []) if now - t < _REGISTER_WINDOW_SECONDS]
    if len(hits) >= _REGISTER_MAX_PER_WINDOW:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many registration attempts"
        )
    hits.append(now)
    _register_hits[client_ip] = hits


class RegisterClientRequest(BaseModel):
    client_name: str | None = None
    redirect_uris: list[str]


@router.post("/mcp/oauth/register", status_code=201)
async def register_client(body: RegisterClientRequest, request: Request, svc: AppServices):
    _check_register_rate_limit(request.client.host if request.client else "unknown")
    try:
        return await svc.mcp_oauth.register_client(body.client_name, body.redirect_uris)
    except OAuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ── Authorize → consent handoff ──────────────────────────────────────────────


@router.get("/mcp/oauth/authorize")
async def authorize(
    svc: AppServices,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
    scope: str = "",
    resource: str | None = None,
    state: str | None = None,
):
    if response_type != "code":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="only response_type=code is supported"
        )
    try:
        consent_url = await svc.mcp_oauth.build_consent_redirect(
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=scope,
            resource=resource,
            state=state,
        )
    except OAuthError as exc:
        # Never redirect on a validation failure — the redirect_uri isn't
        # trusted yet at this point.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(consent_url, status_code=status.HTTP_302_FOUND)


@router.get("/mcp/oauth/consent-info")
async def consent_info(rt: str, user_id: CurrentUser, svc: AppServices):
    try:
        return await svc.mcp_oauth.get_consent_info(rt, user_id)
    except ConsentError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


class ConsentDecisionRequest(BaseModel):
    rt: str
    approve: bool


@router.post("/mcp/oauth/consent")
async def consent(body: ConsentDecisionRequest, user_id: CurrentUser, svc: AppServices):
    try:
        redirect_url = await svc.mcp_oauth.complete_consent(body.rt, user_id, body.approve)
    except ConsentError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"redirect_url": redirect_url}


# ── Token endpoint ────────────────────────────────────────────────────────


def _oauth_error_response(error: str, description: str, http_status: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=http_status, content={"error": error, "error_description": description}
    )


class DeviceAuthorization(BaseModel):
    """RFC 8628 §3.2."""

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


@router.post(
    "/mcp/oauth/device_authorization",
    response_model=DeviceAuthorization,
    responses={400: {"description": "OAuth error (`invalid_client`)"}},
)
async def device_authorization(
    svc: AppServices,
    client_id: str = Form(...),
    scope: str = Form(""),
    resource: str | None = Form(None),
) -> DeviceAuthorization | JSONResponse:
    """Start a device sign-in (RFC 8628 §3.1): a code the person approves on
    the device page, and the device code the client polls the token endpoint with."""
    try:
        started = await svc.mcp_oauth.start_device_authorization(client_id, scope, resource)
    except OAuthError as exc:
        return _oauth_error_response("invalid_client", str(exc))
    return DeviceAuthorization.model_validate(started)


@router.post("/mcp/oauth/token")
async def token(
    svc: AppServices,
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str = Form(...),
    code_verifier: str | None = Form(None),
    refresh_token: str | None = Form(None),
    device_code: str | None = Form(None),
):
    try:
        if grant_type == DEVICE_GRANT_TYPE:
            if not device_code:
                return _oauth_error_response("invalid_request", "device_code is required")
            result = await svc.mcp_oauth.exchange_device_code(device_code, client_id)
        elif grant_type == "authorization_code":
            if not (code and redirect_uri and code_verifier):
                return _oauth_error_response(
                    "invalid_request", "code, redirect_uri, and code_verifier are required"
                )
            result = await svc.mcp_oauth.exchange_authorization_code(
                code=code,
                redirect_uri=redirect_uri,
                client_id=client_id,
                code_verifier=code_verifier,
            )
        elif grant_type == "refresh_token":
            if not refresh_token:
                return _oauth_error_response("invalid_request", "refresh_token is required")
            result = await svc.mcp_oauth.exchange_refresh_token(refresh_token, client_id)
        else:
            return _oauth_error_response("unsupported_grant_type", grant_type)
    except OAuthError as exc:
        return _oauth_error_response(exc.error, str(exc))
    return result


@router.post("/mcp/oauth/revoke")
async def revoke(request: Request, svc: AppServices) -> dict[str, Any]:
    """RFC 7009 says form-encoded; older clients of this endpoint sent JSON.
    Both are accepted."""
    if request.headers.get("content-type", "").startswith("application/json"):
        body: Any = await request.json()
    else:
        body = await request.form()
    token = body.get("token") if hasattr(body, "get") else None
    if isinstance(token, str) and token:
        await svc.mcp_oauth.revoke_token_by_value(token)
    return {}  # RFC 7009: always 200, whether or not the token existed


# ── Settings UI: connection management ──────────────────────────────────────

connections_router = APIRouter(prefix="/mcp/connections", tags=["mcp-oauth"])


@connections_router.get("/")
async def list_connections(user_id: CurrentUser, svc: AppServices):
    return {"connections": await svc.mcp_oauth.list_connections(user_id)}


@connections_router.delete("/{token_id}", status_code=204)
async def revoke_connection(token_id: str, user_id: CurrentUser, svc: AppServices):
    revoked = await svc.mcp_oauth.revoke_connection(user_id, token_id)
    if not revoked:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="connection not found")


class McpEnabledRequest(BaseModel):
    enabled: bool


@connections_router.put("/enabled", status_code=204)
async def set_mcp_enabled(body: McpEnabledRequest, user_id: CurrentUser, svc: AppServices):
    """No plan gate: MCP is available on every tier, Free included."""
    await svc.mcp_oauth.set_mcp_enabled(user_id, body.enabled)


@connections_router.get("/enabled")
async def get_mcp_enabled(user_id: CurrentUser, svc: AppServices):
    return {"enabled": await svc.mcp_oauth.is_mcp_enabled(user_id)}
