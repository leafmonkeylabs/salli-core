"""
FastAPI dependency providers.
Uses the same composition.py the CLI uses — the core never knows which surface it's on.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from salli.application.services.llm_credential_service import ResolvedCredentials
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


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
    services: Annotated[Services, Depends(get_services)],
) -> str:
    """The verified caller, provisioned on first contact if this instance is
    open to sign-ups, and refused if it is not and they are not a member."""
    user_id, email = _decode_jwt(creds.credentials, settings)
    if not await services.profile.ensure_user(
        user_id, email, may_create=settings.salli_registration == "open"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not a member of this Salli instance.",
        )
    return user_id


def get_current_email(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str | None:
    return _decode_jwt(creds.credentials, settings)[1]


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
