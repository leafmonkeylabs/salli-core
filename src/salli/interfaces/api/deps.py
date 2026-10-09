"""
FastAPI dependency providers.
Uses the same composition.py the CLI uses — the core never knows which surface it's on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from salli.application.services.llm_credential_service import ResolvedCredentials
from salli.application.services.mcp_oauth_service import API
from salli.application.services.personal_access_token_service import is_personal_access_token
from salli.composition import Services, build_services
from salli.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=True)


_services_singleton: Services | None = None
_checkpointer = None


def set_checkpointer(cp) -> None:
    """Called from the app lifespan before the first request."""
    global _checkpointer
    _checkpointer = cp


def get_services() -> Services:
    global _services_singleton
    if _services_singleton is None:
        _services_singleton = build_services(get_settings(), checkpointer=_checkpointer)
    return _services_singleton


# ── Auth ───────────────────────────────────────────────────────────────────────

# JWKS cache for Supabase's asymmetric signing keys (ES256/RS256).
_jwks_cache: dict[str, object] = {"keys": [], "ts": 0.0}
_JWKS_TTL = 3600.0


def _get_jwks(settings: Settings) -> list[dict]:
    import time

    import httpx

    now = time.time()
    if _jwks_cache["keys"] and now - float(_jwks_cache["ts"]) < _JWKS_TTL:  # type: ignore[arg-type]
        return _jwks_cache["keys"]  # type: ignore[return-value]
    url = settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    resp = httpx.get(url, timeout=5)
    resp.raise_for_status()
    keys = resp.json().get("keys", [])
    _jwks_cache["keys"] = keys
    _jwks_cache["ts"] = now
    return keys


def insecure_dev_auth(settings: Settings) -> bool:
    """Whether "the bearer token is the user id" is in force. Needs both the
    explicit flag and a development environment, so neither a stray env var on
    a server nor a forgotten ENVIRONMENT alone can switch authentication off."""
    return settings.salli_insecure_dev_auth and settings.environment == "development"


def _decode_jwt(token: str, settings: Settings) -> tuple[str, str | None]:
    """
    Verify a Supabase-issued JWT and return (user_id, email).

    Supports both modern asymmetric tokens (ES256/RS256, verified via the project's
    JWKS) and legacy HS256 tokens (verified with the shared JWT secret).

    With no Supabase configured, refuses — unless the local-dev fallback is
    explicitly switched on (see `insecure_dev_auth`), in which case the token
    itself is taken as the user id.
    """
    if not settings.supabase_url and not settings.supabase_jwt_secret:
        if insecure_dev_auth(settings):
            return token, None
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server.",
        )

    try:
        from jose import jwt

        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "")

        if alg == "HS256":
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            kid = header.get("kid")
            jwks = _get_jwks(settings)
            jwk = next((k for k in jwks if k.get("kid") == kid), None)
            if jwk is None:
                # Key may have rotated — refresh once
                _jwks_cache["ts"] = 0.0
                jwks = _get_jwks(settings)
                jwk = next((k for k in jwks if k.get("kid") == kid), None)
            if jwk is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown signing key"
                )
            payload = jwt.decode(token, jwk, algorithms=[alg], audience="authenticated")

        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return str(sub), payload.get("email")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate token"
        ) from exc


@dataclass(frozen=True)
class Principal:
    """Who is calling, and how they signed in.

    `session`: a Supabase access token (the web and mobile apps).
    `oauth`: a Salli OAuth token issued for the REST API (the `salli` CLI).
    `pat`: a personal access token (scripts, CI).
    `dev`: the local-development fallback where the token is the user id.
    """

    user_id: str
    email: str | None
    method: Literal["session", "oauth", "pat", "dev"]


def _looks_like_jwt(token: str) -> bool:
    # Three dot-separated segments. Salli's own tokens never contain a dot.
    return token.count(".") == 2


async def get_principal(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
    services: Annotated[Services, Depends(get_services)],
) -> Principal:
    """Verify the bearer token, whichever kind it is.

    Personal access tokens and Salli's own OAuth tokens are checked against
    this database, so they work with or without Supabase. An OAuth token is
    only accepted if it was issued for the REST API: one an AI client holds
    for MCP is refused here, as an API token would be refused by MCP.
    """
    token = creds.credentials
    if is_personal_access_token(token):
        user_id = await services.tokens.verify(token)
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This token is invalid, expired, or has been revoked.",
            )
        return Principal(user_id, None, "pat")
    # Salli's own tokens before the development fallback: under it, a CLI
    # signed in with the device flow was taken to be the user whose id is
    # its access token.
    if not _looks_like_jwt(token):
        record = await services.mcp_oauth.verify_access_token(token, audience=API)
        if record is not None:
            return Principal(str(record["user_id"]), None, "oauth")
    if (
        not settings.supabase_url
        and not settings.supabase_jwt_secret
        and insecure_dev_auth(settings)
    ):
        return Principal(token, None, "dev")
    if _looks_like_jwt(token):
        user_id, email = _decode_jwt(token, settings)
        return Principal(user_id, email, "session")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate token")


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


async def get_current_user(
    principal: CurrentPrincipal,
    settings: Annotated[Settings, Depends(get_settings)],
    services: Annotated[Services, Depends(get_services)],
) -> str:
    """The verified caller, provisioned on first contact if this instance is
    open to sign-ups, and refused if it is not and they are not a member.

    Only a sign-in (or the local-dev fallback) can create an account: a token
    is only ever issued to someone who already has one."""
    if not await services.profile.ensure_user(
        principal.user_id,
        principal.email,
        may_create=settings.salli_registration == "open" and principal.method in ("session", "dev"),
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not a member of this Salli instance.",
        )
    return principal.user_id


async def get_current_email(
    principal: CurrentPrincipal,
    services: Annotated[Services, Depends(get_services)],
) -> str | None:
    if principal.email or principal.method in ("session", "dev"):
        return principal.email
    # A token carries no email; the profile has the one they signed up with.
    profile = await services.profile.get_profile(principal.user_id)
    return profile.get("email")


async def get_credentials(
    user_id: Annotated[str, Depends(get_current_user)],
    services: Annotated[Services, Depends(get_services)],
) -> ResolvedCredentials:
    """Resolve this request's LLM credentials once, at the boundary.

    Deliberately not resolved lazily inside each service: the usage meter runs
    *before* the stream opens, so it has to already know whether this user is on
    their own key. Resolving in two places would let the metering decision and
    the key that actually ran disagree.
    """
    return await services.llm_credentials.resolve(user_id)


# Convenient type aliases for route parameters
CurrentUser = Annotated[str, Depends(get_current_user)]
CurrentEmail = Annotated["str | None", Depends(get_current_email)]
AppServices = Annotated[Services, Depends(get_services)]
Credentials = Annotated[ResolvedCredentials, Depends(get_credentials)]
