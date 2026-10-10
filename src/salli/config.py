from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": a deployment's .env may carry settings for its extensions,
    # which declare their own settings classes over the same file.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://localhost/salli"

    # Anthropic
    anthropic_api_key: str = ""

    # BYOK — encrypts users' own provider keys at rest with AES-GCM.
    # Comma-separated "version:base64key" entries so keys can be rotated: the
    # HIGHEST version encrypts, any listed version can decrypt (each row records
    # the version that sealed it). Generate one with:
    #   python -c "import base64,os; print('1:'+base64.b64encode(os.urandom(32)).decode())"
    # Left blank, BYOK reports unavailable and no user key is accepted — it must
    # never degrade to storing a provider key in plaintext.
    byok_encryption_keys: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    # JWT secret from Supabase dashboard → Project Settings → API → JWT Secret.
    # When blank, the API accepts any Bearer token and treats it as the user_id
    # (dev-only fallback — never deploy without this set).
    supabase_jwt_secret: str = ""

    # LangSmith (optional)
    langsmith_api_key: str = ""
    langsmith_project: str = "salli"

    # Tavily (web search for agents)
    tavily_api_key: str = ""

    # Daily Wealth Advisor scheduling (Supabase pg_cron calls the API)
    cron_secret: str = ""
    advisor_api_base_url: str = "http://localhost:8000"

    # MCP server — lets external AI clients (Claude, ChatGPT, etc.) connect to a
    # user's Salli account via OAuth 2.1 + Dynamic Client Registration.
    mcp_public_base_url: str = "http://localhost:8000"  # this API, as seen by MCP clients
    # Where a user approves an MCP connection. Empty: Salli's own consent page,
    # served by this API at {mcp_public_base_url}/mcp/oauth/consent-page. A
    # deployment with its own web app points this at that app's consent screen
    # (it receives `?rt=<token>` and calls /mcp/oauth/consent-info and /consent).
    mcp_consent_url: str = ""
    # Signs the short-lived "pending authorization" token handed to the web app's
    # consent screen. Falls back to the Supabase JWT secret in dev so a fresh
    # checkout works without extra config — set a real random value in production.
    mcp_signing_secret: str = ""
    # Pending-authorization token TTL — generous because the consent screen
    # usually sits behind a login (or first-time signup) redirect.
    mcp_art_ttl_seconds: int = 1800
    mcp_auth_code_ttl_seconds: int = 120
    mcp_access_token_ttl_seconds: int = 3600
    mcp_refresh_token_ttl_seconds: int = 60 * 60 * 24 * 30

    # CORS — comma-separated list of allowed origins in production.
    # Defaults cover app + marketing site (both the leafmonkey.org subdomains and
    # the legacy salli.lk domain); override via ALLOWED_ORIGINS env var.
    allowed_origins: list[str] = [
        "https://app.salli.leafmonkey.org",
        "https://salli.leafmonkey.org",
        "https://app.salli.lk",
        "https://salli.lk",
    ]

    # The instance's owner, written to .env by `salli-server setup`. Commands an
    # extension adds to salli-server that act on one user act as this one; set
    # it in the environment to act as someone else (e.g. a household member).
    salli_user_id: str = ""

    # Who may use this instance. "closed" (the default): only accounts that
    # already have a profile — the owner `salli-server setup` creates, and anyone they
    # add — even if the auth provider would vouch for others. "open": anyone
    # who can sign in gets an account on first request, as a hosted service
    # needs.
    salli_registration: Literal["closed", "open"] = "closed"

    # Local development only: with no Supabase configured, treat the bearer
    # token itself as the user id. Honoured only when this is set AND
    # ENVIRONMENT=development; otherwise an API without auth configured refuses
    # every request rather than trusting whoever calls it.
    salli_insecure_dev_auth: bool = False

    # Where uploaded files (statements, receipts) live. "auto": Supabase Storage
    # when SUPABASE_URL and the service-role key are set, else the local disk
    # (~/.salli/storage). "local" keeps them on disk regardless — what a
    # self-hosted instance usually wants.
    salli_storage: Literal["auto", "local", "supabase"] = "auto"

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


def insecure_dev_auth(settings: Settings) -> bool:
    """Whether "the bearer token is the user id" is switched on. Needs both the
    explicit flag and a development environment, so neither a stray env var on
    a server nor a forgotten ENVIRONMENT alone can switch authentication off.

    While it is (and no Supabase is configured), any caller can name any user
    id, so nothing that holds a user's secrets may be switched on: see
    `auth_can_hold_secrets`."""
    return settings.salli_insecure_dev_auth and settings.environment == "development"


def dev_auth_fallback_live(settings: Settings) -> bool:
    """Whether the API takes an unrecognised bearer token as the user id: no
    Supabase at all, and the development fallback switched on. Exactly the
    condition `deps.get_principal` falls back on."""
    return (
        not settings.supabase_url
        and not settings.supabase_jwt_secret
        and insecure_dev_auth(settings)
    )


def auth_can_hold_secrets(settings: Settings) -> bool:
    """Whether authentication is real enough to keep a user's secrets (stored
    LLM keys, bank credentials): yes unless any caller can claim to be anyone
    by naming a user id. The one predicate every such feature gates on."""
    return not dev_auth_fallback_live(settings)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
