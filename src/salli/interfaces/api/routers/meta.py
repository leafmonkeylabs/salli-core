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

from salli.config import get_settings
from salli.domain.tax.packs import registry
from salli.extensions import enabled_specs
from salli.interfaces.api.contract import API_VERSION, CurrencyCode
from salli.interfaces.api.routers.tax import WithholdingKind, withholding_kinds

router = APIRouter(prefix="/meta", tags=["meta"])


def server_version() -> str:
    try:
        return version("salli-core")
    except PackageNotFoundError:  # running from a source tree without metadata
        return "0.0.0"


class TaxPackInfo(BaseModel):
    country: str
    year: str
    version: str
    currency: CurrencyCode
    period_start: str
    period_end: str
    #: The tax withheld or paid ahead that the pack credits; an account's
    #: `tax_role` names one by its code.
    withholding_kinds: list[WithholdingKind]


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


class Meta(BaseModel):
    api_version: str
    server_version: str
    #: Names of the extensions this deployment runs (empty for Salli as shipped).
    extensions: list[str]
    tax_packs: list[TaxPackInfo]
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
        tax_packs=[
            TaxPackInfo(
                country=p.country,
                year=p.year,
                version=p.version,
                currency=p.currency,
                period_start=p.period_start,
                period_end=p.period_end,
                withholding_kinds=withholding_kinds(p),
            )
            for p in registry.list_packs()
        ],
        oauth=OAuthInfo(
            issuer=base,
            authorization_endpoint=f"{base}/mcp/oauth/authorize",
            token_endpoint=f"{base}/mcp/oauth/token",
            registration_endpoint=f"{base}/mcp/oauth/register",
            revocation_endpoint=f"{base}/mcp/oauth/revoke",
            device_authorization_endpoint=f"{base}/mcp/oauth/device_authorization",
            api_resource=f"{base}/v1",
            device_verification_uri=f"{base}/mcp/oauth/device",
        ),
        default_currency=settings.salli_default_currency.upper(),
    )
