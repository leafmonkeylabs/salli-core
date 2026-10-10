"""
Composition root — the single place adapters are bound to ports.
Both the CLI (Phase 1) and FastAPI (Phase 2) wire up services here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from salli.adapters.db.session import make_session_factory
from salli.adapters.fx.chain import default_fx_rates
from salli.application.ports import EntitlementPolicy, FxRatePort, StoragePort, UsageMeter
from salli.application.services.advisor_service import AdvisorService
from salli.application.services.agent_service import AgentService
from salli.application.services.budget_service import BudgetService
from salli.application.services.data_portability_service import DataPortabilityService
from salli.application.services.debt_service import DebtService
from salli.application.services.document_service import DocumentService
from salli.application.services.entry_parse_service import EntryParseService
from salli.application.services.fi_service import FiService
from salli.application.services.insurance_service import InsuranceService
from salli.application.services.ledger_service import LedgerService
from salli.application.services.llm_credential_service import LlmCredentialService
from salli.application.services.mcp_oauth_service import McpOAuthService
from salli.application.services.onboarding_service import OnboardingService
from salli.application.services.parsing_service import ParsingService
from salli.application.services.personal_access_token_service import PersonalAccessTokenService
from salli.application.services.portfolio_service import PortfolioService
from salli.application.services.reminder_service import ReminderService
from salli.application.services.report_service import ReportService
from salli.application.services.rules_service import RulesService
from salli.application.services.subscription_service import SubscriptionService
from salli.application.services.tax_service import TaxService
from salli.application.services.user_profile_service import UserProfileService
from salli.application.unit_of_work import UnitOfWork
from salli.config import Settings, auth_can_hold_secrets
from salli.extensions import (
    Contributions,
    ExtensionContext,
    UserDataPurger,
    build_extensions,
    combine,
    enabled_specs,
)


@dataclass
class Services:
    ledger: LedgerService
    tax: TaxService
    agent: AgentService
    parsing: ParsingService
    reminders: ReminderService
    fx: FxRatePort
    storage: StoragePort
    documents: DocumentService
    fi: FiService
    advisor: AdvisorService
    profile: UserProfileService
    onboarding: OnboardingService
    budget: BudgetService
    debt: DebtService
    portfolio: PortfolioService
    subscription: SubscriptionService
    insurance: InsuranceService
    reports: ReportService
    data_portability: DataPortabilityService
    mcp_oauth: McpOAuthService
    llm_credentials: LlmCredentialService
    tokens: PersonalAccessTokenService
    rules: RulesService
    # Not optional any more: availability is per-user, decided at call time.
    entry_parse: EntryParseService
    # The extension seams. Salli's own defaults unless an enabled extension
    # replaced them — see salli/extensions.py.
    usage: UsageMeter
    entitlements: EntitlementPolicy
    # Everything enabled extensions contributed, including their own services
    # (`extensions.services`).
    extensions: Contributions


def build_services(settings: Settings, checkpointer: Any = None, pooled: bool = True) -> Services:
    import os

    # ANTHROPIC_API_KEY is deliberately NOT seeded into os.environ. Every model
    # is now constructed with an explicit key (see domain/agents/model_factory),
    # and while that env var is set ChatAnthropic would silently fall back to it
    # — so any construction site we missed would quietly bill the platform for a
    # user who is supposed to be paying their own way. Leaving it unset turns
    # such a miss into a loud failure instead.
    #
    # Tavily still reads the environment: its LangChain tool has no key
    # parameter, and web search is a platform capability, not a per-user one.
    if settings.tavily_api_key:
        os.environ.setdefault("TAVILY_API_KEY", settings.tavily_api_key)

    # Unpooled for the CLI: a command may run several event loops in turn.
    session_factory = make_session_factory(settings, pooled=pooled)

    # Filled in once extensions are built (they need uow_factory first). Read
    # at call time, so every unit of work — including any opened by an
    # extension — deletes the extensions' rows along with a user's account.
    purgers: list[UserDataPurger] = []

    def uow_factory() -> UnitOfWork:
        return UnitOfWork(session_factory, purgers)

    storage = _build_storage(settings)
    llm_credentials = _build_llm_credentials(settings, uow_factory)

    # Extensions are built before Salli's own services so their meter and policy
    # can be injected into them. Raises if an enabled extension is unavailable.
    extensions = combine(
        build_extensions(
            enabled_specs(settings),
            ExtensionContext(
                settings=settings,
                session_factory=session_factory,
                uow_factory=uow_factory,
                llm_credentials=llm_credentials,
                storage=storage,
                user_data_purgers=purgers,
            ),
        )
    )
    purgers.extend(extensions.user_data_purgers)

    fx = default_fx_rates()
    ledger = LedgerService(uow_factory, fx=fx)
    tax = TaxService(uow_factory)
    documents = DocumentService(uow_factory, storage)
    fi = FiService(uow_factory, llm_credentials)
    budget = BudgetService(uow_factory)
    debt = DebtService(uow_factory)
    portfolio = PortfolioService(uow_factory)
    subscription = SubscriptionService(uow_factory)
    insurance = InsuranceService(uow_factory)
    profile = UserProfileService(
        uow_factory,
        ledger,
        fi,
        documents,
        fx_service=fx,
        default_currency=settings.salli_default_currency,
    )
    advisor = AdvisorService(
        uow_factory,
        fi,
        extensions.usage_meter,
        doc_service=documents,
        credentials=llm_credentials,
    )
    agent = AgentService(
        ledger,
        tax,
        documents,
        profile,
        budget,
        debt,
        portfolio,
        subscription,
        insurance,
        advisor,
        fi,
        checkpointer=checkpointer,
        uow_factory=uow_factory,
    )
    parsing = ParsingService(uow_factory, storage, llm_credentials, fx=fx)

    # Free-text → draft journal entry (voice/text quick-add) and Voice Mode
    # speech-to-text. Both are now always constructed: which key they run on is
    # resolved per request, so a user with their own key gets the feature even
    # where no platform key exists. Previously both were None unless a platform
    # key was configured, which 503'd exactly the users BYOK is for.
    from salli.adapters.llm.anthropic_adapter import AnthropicLLMAdapter

    rules = RulesService(uow_factory)
    entry_parse = EntryParseService(
        ledger,
        lambda key: AnthropicLLMAdapter(key, settings.langsmith_project),
        credentials=llm_credentials,
        rules=rules,
    )

    reminders = ReminderService(uow_factory, budget, subscription, insurance)
    reports = ReportService(ledger, fi)
    public_url = settings.mcp_public_base_url.rstrip("/")
    mcp_oauth = McpOAuthService(
        uow_factory,
        signing_secret=settings.mcp_signing_secret
        or settings.supabase_jwt_secret
        or "dev-insecure-secret",
        mcp_resource_url=f"{public_url}/mcp",
        api_resource_url=f"{public_url}/v1",
        device_verification_url=f"{public_url}/mcp/oauth/device",
        consent_url=settings.mcp_consent_url or f"{public_url}/mcp/oauth/consent-page",
        art_ttl_seconds=settings.mcp_art_ttl_seconds,
        auth_code_ttl_seconds=settings.mcp_auth_code_ttl_seconds,
        access_token_ttl_seconds=settings.mcp_access_token_ttl_seconds,
        refresh_token_ttl_seconds=settings.mcp_refresh_token_ttl_seconds,
    )
    data_portability = DataPortabilityService(
        uow_factory,
        profile,
        ledger,
        tax,
        budget,
        debt,
        portfolio,
        subscription,
        insurance,
        fi,
        advisor,
        documents,
        reminders,
        exporters=extensions.user_data_exporters,
    )

    return Services(
        ledger=ledger,
        tax=tax,
        agent=agent,
        parsing=parsing,
        reminders=reminders,
        fx=fx,
        storage=storage,
        documents=documents,
        fi=fi,
        advisor=advisor,
        profile=profile,
        onboarding=OnboardingService(documents, fi, ledger),
        budget=budget,
        debt=debt,
        portfolio=portfolio,
        subscription=subscription,
        insurance=insurance,
        reports=reports,
        data_portability=data_portability,
        mcp_oauth=mcp_oauth,
        llm_credentials=llm_credentials,
        tokens=PersonalAccessTokenService(uow_factory),
        rules=rules,
        entry_parse=entry_parse,
        usage=extensions.usage_meter,
        entitlements=extensions.entitlements,
        extensions=extensions,
    )


def _build_llm_credentials(settings: Settings, uow_factory) -> LlmCredentialService:
    """Always constructed; `available` decides whether users may supply keys.

    Two gates, both of which must hold, and both of which fail *closed*:

    1. An encryption key is configured. Without one there is nowhere safe to put
       a user's key, and storing plaintext is not an acceptable fallback.
    2. Auth is real (`config.auth_can_hold_secrets`). `deps.get_principal`
       falls back to treating the bearer token *as* the user id when Supabase
       is unconfigured and the development fallback is on — a documented
       local-dev convenience, but with BYOK it would let any caller name an
       arbitrary user id and spend that user's key. So BYOK stays off whenever
       that fallback is live.
    """
    from salli.adapters.crypto.keyring import KeyRing
    from salli.adapters.llm.key_check import validate_provider_key

    auth_is_real = auth_can_hold_secrets(settings)
    if not auth_is_real and settings.byok_encryption_keys:
        logging.getLogger(__name__).warning(
            "BYOK is disabled: an encryption key is configured but authentication "
            "is not, so any bearer token would be accepted as a user id."
        )

    return LlmCredentialService(
        uow_factory,
        KeyRing(settings.byok_encryption_keys),
        platform_anthropic_key=settings.anthropic_api_key,
        validator=validate_provider_key,
        feature_enabled=auth_is_real,
    )


def _build_storage(settings: Settings) -> StoragePort:
    use_supabase = settings.salli_storage == "supabase" or (
        settings.salli_storage == "auto"
        and bool(settings.supabase_url and settings.supabase_service_role_key)
    )
    if use_supabase:
        from salli.adapters.storage.supabase import SupabaseStorageAdapter

        return SupabaseStorageAdapter(settings.supabase_url, settings.supabase_service_role_key)
    from salli.adapters.storage.local import LocalStorageAdapter

    return LocalStorageAdapter()
