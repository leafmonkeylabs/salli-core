"""
Salli's settings, from the environment (and a `.env` file in the working
directory, when there is one).

A container reads the environment only: the image has no `.env`, and the
compose file passes every setting in. Secrets may also come from files in
SALLI_SECRETS_DIR, one per setting, named after it in lower case
(`database_password`, `byok_encryption_keys`, `mcp_signing_secret`,
`cron_secret`): `salli-server secrets init` writes them there on a first run,
and an environment variable of the same name wins over its file. See
docs/self-host.md for every setting.
"""

from __future__ import annotations

import os
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": a deployment's .env may carry settings for its extensions,
    # which declare their own settings classes over the same file.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database. DATABASE_URL may leave the password out, and DATABASE_PASSWORD
    # (or its file in SALLI_SECRETS_DIR) supply it: the compose file does, so
    # the password it generates is never written into a URL by hand.
    database_url: str = "postgresql+asyncpg://localhost/salli"
    database_password: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # BYOK — encrypts users' own provider keys at rest with AES-GCM.
    # Comma-separated "version:base64key" entries so keys can be rotated: the
    # HIGHEST version encrypts, any listed version can decrypt (each row records
    # the version that sealed it). `salli-server secrets init` generates one.
    # Left blank, BYOK reports unavailable and no user key is accepted — it must
    # never degrade to storing a provider key in plaintext.
    byok_encryption_keys: str = ""

    # LangSmith (optional)
    langsmith_api_key: str = ""
    langsmith_project: str = "salli"

    # Tavily (web search for agents)
    tavily_api_key: str = ""

    # The scheduler routes (/v1/advisor/cron/run-due, /v1/bank-connections/
    # cron/sync-due) want this in X-Cron-Secret; with none, they refuse every
    # call. `salli-server jobs` does the same work from a crontab without them.
    cron_secret: str = ""

    # MCP server — lets external AI clients (Claude, ChatGPT, etc.) connect to a
    # user's Salli account via OAuth 2.1 + Dynamic Client Registration.
    mcp_public_base_url: str = "http://localhost:8000"  # this API, as seen by MCP clients
    # Where a user approves an MCP connection. Empty: Salli's own consent page,
    # served by this API at {mcp_public_base_url}/mcp/oauth/consent-page. A
    # deployment with its own web app points this at that app's consent screen
    # (it receives `?rt=<token>` and calls /mcp/oauth/consent-info and /consent).
    mcp_consent_url: str = ""
    # Signs the short-lived "pending authorization" token handed to the consent
    # page. Without one, each process makes up its own at start, so a pending
    # connection does not survive a restart: set one (`salli-server secrets
    # init` does) to avoid that.
    mcp_signing_secret: str = ""
    # Pending-authorization token TTL — generous because the consent screen
    # usually sits behind a login (or first-time signup) redirect.
    mcp_art_ttl_seconds: int = 1800
    mcp_auth_code_ttl_seconds: int = 120
    mcp_access_token_ttl_seconds: int = 3600
    mcp_refresh_token_ttl_seconds: int = 60 * 60 * 24 * 30

    # Sign-in sessions (`POST /v1/auth/sessions`) last this long from the
    # moment they start, however much they are used.
    salli_session_ttl_days: int = 30

    # CORS: the web origins whose pages may call this API from a browser,
    # comma-separated (`https://app.example.org,https://example.org`). None by
    # default: the salli CLI, scripts and MCP clients need none, and a
    # self-hosted server should trust no one's web pages until told to.
    allowed_origins: Annotated[list[str], NoDecode] = []

    # The user a `salli-server` command that acts on one user acts as (an
    # extension's commands). Empty: the instance's owner, the account
    # `salli-server setup` created. Set it to act as someone else.
    salli_user_id: str = ""

    # Local development only: treat the bearer token itself as the user id.
    # Honoured only when this is set AND ENVIRONMENT=development; never on a
    # server anyone else can reach.
    salli_insecure_dev_auth: bool = False

    # Where uploaded files (statements, receipts) are kept. Empty:
    # ~/.salli/storage. The container keeps them in /var/lib/salli/files.
    salli_storage_dir: str = ""

    # Extensions — comma-separated names of installed `salli.extensions` entry
    # points to activate (see salli/extensions.py). Empty means Salli as
    # shipped: nothing metered, every user sees everything. A name that is not
    # installed stops startup rather than being skipped.
    salli_extensions: str = ""

    # Whether users may power Salli's AI with their ChatGPT plan (Sign in with
    # ChatGPT plan usage). OpenAI offers it to open-source and self-hosted apps
    # such as Salli as shipped, so it is on for self-hosting. A paid or
    # remotely hosted product needs OpenAI's approval first: it turns this off,
    # or decides per user through its extension (ChatGPTPlanPolicy), until then.
    salli_chatgpt_plan_usage: bool = True

    # The base currency a new account is given when nothing else says which —
    # `salli-server setup` asks, and onboarding can change it while the ledger is
    # still empty. Existing users keep theirs; this only applies to new ones.
    salli_default_currency: str = "USD"

    # App
    environment: str = "development"
    log_level: str = "INFO"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _comma_separated(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value


def insecure_dev_auth(settings: Settings) -> bool:
    """Whether "the bearer token is the user id" is switched on. Needs both the
    explicit flag and a development environment, so neither a stray env var on
    a server nor a forgotten ENVIRONMENT alone can switch authentication off.

    While it is, any caller can name any user id, so nothing that holds a
    user's secrets may be switched on: see `auth_can_hold_secrets`."""
    return settings.salli_insecure_dev_auth and settings.environment == "development"


def auth_can_hold_secrets(settings: Settings) -> bool:
    """Whether authentication is real enough to keep a user's secrets (stored
    LLM keys, bank credentials): yes unless any caller can claim to be anyone
    by naming a user id. The one predicate every such feature gates on."""
    return not insecure_dev_auth(settings)


def database_url(settings: Settings) -> str:
    """DATABASE_URL, with DATABASE_PASSWORD in it when the URL has none."""
    from sqlalchemy.engine import make_url

    url = make_url(settings.database_url)
    if settings.database_password and not url.password:
        url = url.set(password=settings.database_password)
    return url.render_as_string(hide_password=False)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        secrets_dir = os.environ.get("SALLI_SECRETS_DIR") or None
        _settings = Settings(_secrets_dir=secrets_dir)  # pyright: ignore[reportCallIssue]
    return _settings
