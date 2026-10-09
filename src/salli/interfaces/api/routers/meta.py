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


class OAuthInfo(BaseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str
    revocation_endpoint: str


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
            )
            for p in registry.list_packs()
        ],
        oauth=OAuthInfo(
            issuer=base,
            authorization_endpoint=f"{base}/mcp/oauth/authorize",
            token_endpoint=f"{base}/mcp/oauth/token",
            registration_endpoint=f"{base}/mcp/oauth/register",
            revocation_endpoint=f"{base}/mcp/oauth/revoke",
        ),
        default_currency=settings.salli_default_currency.upper(),
    )
