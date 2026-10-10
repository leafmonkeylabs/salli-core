"""
`GET /v1/meta` — what this server is and how to talk to it.

Public, because a client needs it before it can sign in: the CLI reads it to
find the sign-in endpoints, to check it is speaking a compatible API version,
and to learn which commands an enabled extension adds.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter
from pydantic import BaseModel

from salli.application.services.mcp_oauth_service import CLI_CLIENT_ID
from salli.config import get_settings
from salli.extensions import enabled_specs
from salli.interfaces.api.contract import API_VERSION, CurrencyCode

router = APIRouter(prefix="/meta", tags=["meta"])


def server_version() -> str:
    try:
        return version("salli-core")
    except PackageNotFoundError:  # running from a source tree without metadata
        return "0.0.0"


class OAuthInfo(BaseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str
    revocation_endpoint: str
    device_authorization_endpoint: str
    #: The resource indicator (RFC 8707) to request a token for this REST API.
    #: Tokens issued for MCP are not accepted here, nor these by MCP.
    api_resource: str
    #: Where a person approves a device sign-in.
    device_verification_uri: str
    #: The client id the `salli` CLI signs in as. Salli's own client, known to
    #: the server rather than registered, so its sessions may do what only the
    #: user's own sign-ins may (activate a tax rule set).
    cli_client_id: str


class Meta(BaseModel):
    api_version: str
    server_version: str
    #: Names of the extensions this deployment runs (empty for Salli as shipped).
    extensions: list[str]
    oauth: OAuthInfo
    #: The base currency a new account starts in unless it names another.
    default_currency: CurrencyCode


@router.get("")
async def get_meta() -> Meta:
    settings = get_settings()
    base = settings.mcp_public_base_url.rstrip("/")
    return Meta(
        api_version=API_VERSION,
        server_version=server_version(),
        extensions=[spec.name for spec in enabled_specs(settings)],
        oauth=OAuthInfo(
            issuer=base,
            authorization_endpoint=f"{base}/mcp/oauth/authorize",
            token_endpoint=f"{base}/mcp/oauth/token",
            registration_endpoint=f"{base}/mcp/oauth/register",
            revocation_endpoint=f"{base}/mcp/oauth/revoke",
            device_authorization_endpoint=f"{base}/mcp/oauth/device_authorization",
            api_resource=f"{base}/v1",
            device_verification_uri=f"{base}/mcp/oauth/device",
            cli_client_id=CLI_CLIENT_ID,
        ),
        default_currency=settings.salli_default_currency.upper(),
    )
