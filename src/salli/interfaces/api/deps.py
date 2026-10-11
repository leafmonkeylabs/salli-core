"""
FastAPI dependency providers.
Uses the same composition.py the CLI uses — the core never knows which surface it's on.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from salli.application.permissions import Actor, permissions_for
from salli.application.ports import IdentityProvider
from salli.application.services.llm_credential_service import ResolvedCredentials
from salli.application.services.login_service import is_session_token
from salli.application.services.mcp_oauth_service import API, has_salli_prefix
from salli.application.services.personal_access_token_service import is_personal_access_token
from salli.composition import Services, build_services
from salli.config import Settings, get_settings, insecure_dev_auth

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


@dataclass(frozen=True)
class Principal:
    """Who is calling, and how they signed in.

    `session`: a session from signing in with an email and password
    (`POST /v1/auth/sessions`; `session_id` says which), or a token an
    extension's identity provider vouches for (application/ports.py,
    `IdentityProvider`).
    `oauth`: a Salli OAuth token issued for the REST API (the `salli` CLI, or
    another client: `first_party_client` says which).
    `pat`: a personal access token (scripts, CI).
    `dev`: the local-development fallback where the token is the user id.

    What the caller may do beyond reading and writing the user's data follows
    from how they signed in (application/permissions.py), and is derived
    there and nowhere else: for a personal access token, from the permissions
    it stores (`granted`); for any other sign-in, from the method and client.
    There is no way to build a Principal whose permissions disagree with its
    sign-in.
    """

    user_id: str
    email: str | None
    method: Literal["session", "oauth", "pat", "dev"]
    #: For `oauth`: whether the token's client is one of Salli's own.
    first_party_client: bool = False
    #: For `oauth`: the client's name; for `pat`, the token's. Recorded as the
    #: author of what it writes.
    client_name: str | None = None
    #: For `pat`: the permissions the token was made with. Ignored otherwise.
    granted: frozenset[str] = frozenset()
    #: For a Salli `session`: which one (so it can sign itself out).
    session_id: str | None = None

    @property
    def permissions(self) -> frozenset[str]:
        return permissions_for(
            self.method, first_party_client=self.first_party_client, granted=self.granted
        )

    def actor(self) -> Actor:
        return Actor.signed_in(
            self.user_id,
            self.method,
            first_party_client=self.first_party_client,
            name=self.client_name,
            granted=self.granted,
        )


def _refused(detail: str = "This token is invalid, expired, or has been revoked.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _identity_provider(services: Any) -> IdentityProvider | None:
    extensions = getattr(services, "extensions", None)
    return getattr(extensions, "identity_provider", None)


async def get_principal(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
    services: Annotated[Services, Depends(get_services)],
) -> Principal:
    """Verify the bearer token, whichever kind it is.

    Salli's own tokens are checked against this database: sessions, personal
    access tokens and OAuth tokens. An OAuth token is only accepted if it was
    issued for the REST API: one an AI client holds for MCP is refused here,
    as an API token would be refused by MCP. A token that is none of these
    goes to an extension's identity provider, if there is one, and then to
    the local-development fallback, if that is on; never one Salli issued.
    """
    token = creds.credentials
    if is_personal_access_token(token):
        verified = await services.tokens.verify(token)
        if verified is None:
            raise _refused()
        return Principal(
            verified.user_id,
            None,
            "pat",
            client_name=verified.name,
            granted=verified.permissions,
        )
    if is_session_token(token):
        session = await services.logins.verify_session(token)
        if session is None:
            raise _refused("This session has ended or expired. Sign in again.")
        return Principal(session.user_id, None, "session", session_id=session.id)
    record = await services.mcp_oauth.verify_access_token(token, audience=API)
    if record is not None:
        return Principal(
            str(record["user_id"]),
            None,
            "oauth",
            first_party_client=bool(record.get("client_first_party")),
            client_name=record.get("client_name"),
        )

    provider = _identity_provider(services)
    dev = insecure_dev_auth(settings)
    if provider is None and not dev:
        raise _refused()
    # A Salli token that did not verify (expired, revoked, issued for MCP, or
    # a refresh token) is refused, never taken to be anything else. Prefixed
    # tokens need no lookup; older unprefixed ones do.
    if has_salli_prefix(token) or await services.mcp_oauth.is_salli_token(token):
        raise _refused()
    if provider is not None:
        identity = await provider.verify(token)
        if identity is not None:
            return Principal(identity.user_id, identity.email, "session")
    if dev:
        return Principal(token, None, "dev")
    raise _refused()


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


async def get_current_user(
    principal: CurrentPrincipal,
    services: Annotated[Services, Depends(get_services)],
) -> str:
    """The verified caller, refused unless they have an account here.

    No request creates an account: the owner's comes from `salli-server
    setup`, and everyone else's from the owner. A token an identity provider
    vouches for, or a user id under the development fallback, is no
    exception."""
    if not await services.profile.ensure_user(principal.user_id, principal.email, may_create=False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not a member of this Salli instance.",
        )
    return principal.user_id


async def get_current_email(
    principal: CurrentPrincipal,
    services: Annotated[Services, Depends(get_services)],
) -> str | None:
    if principal.email or principal.method == "dev":
        return principal.email
    # A token carries no email; the profile has the one they sign in with.
    profile = await services.profile.get_profile(principal.user_id)
    return profile.get("email")


async def get_actor(
    principal: CurrentPrincipal,
    user_id: Annotated[str, Depends(get_current_user)],
) -> Actor:
    """The caller as the services see them: whose data, which author to
    record, and what they may do (application/permissions.py). Depends on
    get_current_user, so the caller is a member before anything is written."""
    return principal.actor()


def require_permission(permission: str) -> Any:
    """A dependency refusing (403) a caller whose sign-in doesn't carry
    `permission`. The service checks it again: this only refuses earlier, and
    says why in a way a client can show."""

    async def check(principal: CurrentPrincipal) -> None:
        if permission in principal.permissions:
            return
        if principal.method == "pat":
            why = (
                f"This personal access token wasn't made with {permission}. Make one that "
                f"is (`salli tokens create <name> --allow {permission}`), or sign in "
                "yourself (`salli login`, or the app)."
            )
        else:
            why = (
                f"This sign-in doesn't hold {permission}. Only your own sign-in to Salli "
                "(with your password, or the salli CLI) can do this, or a personal access "
                "token you made with it; AI connectors and other applications never can."
            )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=why)

    return Depends(check)


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


def require_cron_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    x_cron_secret: Annotated[str | None, Header()] = None,
) -> None:
    """The scheduler's own endpoints (a cron job, not users): the X-Cron-Secret
    header must match CRON_SECRET, and with none configured nothing does.
    Compared as bytes: a non-ASCII header is a wrong secret, not a 500."""
    secret = settings.cron_secret
    if (
        not secret
        or not x_cron_secret
        or not hmac.compare_digest(x_cron_secret.encode(), secret.encode())
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cron secret")


# Convenient type aliases for route parameters
CurrentUser = Annotated[str, Depends(get_current_user)]
CurrentActor = Annotated[Actor, Depends(get_actor)]
CurrentEmail = Annotated["str | None", Depends(get_current_email)]
AppServices = Annotated[Services, Depends(get_services)]
Credentials = Annotated[ResolvedCredentials, Depends(get_credentials)]
CronSecret = Depends(require_cron_secret)
