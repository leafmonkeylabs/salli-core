"""
Unit of work — wraps a single DB transaction.
Both the CLI and the API use this to ensure all writes in a use-case commit together.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from salli.adapters.db.repositories import (
    SQLAdvisoryRepository,
    SQLAgentDocumentRepository,
    SQLAgentSessionRepository,
    SQLAiConnectionRepository,
    SQLAuditLogRepository,
    SQLBankConnectionRepository,
    SQLBudgetRepository,
    SQLDataPortabilityRepository,
    SQLDebtRepository,
    SQLFireStrategyRepository,
    SQLFiScoreRepository,
    SQLGoalRepository,
    SQLInstanceSettingsRepository,
    SQLInsuranceTargetRepository,
    SQLLedgerRepository,
    SQLLlmCredentialRepository,
    SQLOAuthClientRepository,
    SQLOAuthTokenRepository,
    SQLPersonalAccessTokenRepository,
    SQLPolicyRepository,
    SQLPortfolioRepository,
    SQLRecurringSubscriptionRepository,
    SQLReminderRepository,
    SQLRuleRepository,
    SQLStatementRepository,
    SQLTaxComputationRepository,
    SQLUserProfileRepository,
)
from salli.application.ports import (
    AdvisoryRepository,
    AgentDocumentRepository,
    AgentSessionRepository,
    AiConnectionRepository,
    AuditLogRepository,
    BankConnectionRepository,
    BudgetRepository,
    DataPortabilityRepository,
    DebtRepository,
    FireStrategyRepository,
    FiScoreRepository,
    GoalRepository,
    InstanceSettingsRepository,
    InsuranceTargetRepository,
    LedgerRepository,
    LlmCredentialRepository,
    OAuthClientRepository,
    OAuthTokenRepository,
    PersonalAccessTokenRepository,
    PolicyRepository,
    PortfolioRepository,
    RecurringSubscriptionRepository,
    ReminderRepository,
    RuleRepository,
    StatementRepository,
    TaxComputationRepository,
    UserProfileRepository,
)

if TYPE_CHECKING:
    from salli.extensions import UserDataPurger


class UnitOfWork:
    ledger: LedgerRepository
    tax_computations: TaxComputationRepository
    statements: StatementRepository
    reminders: ReminderRepository
    agent_documents: AgentDocumentRepository
    agent_sessions: AgentSessionRepository
    user_profiles: UserProfileRepository
    goals: GoalRepository
    fi_scores: FiScoreRepository
    advisories: AdvisoryRepository
    fire_strategies: FireStrategyRepository
    budgets: BudgetRepository
    debts: DebtRepository
    holdings: PortfolioRepository
    recurring_subscriptions: RecurringSubscriptionRepository
    policies: PolicyRepository
    insurance_targets: InsuranceTargetRepository
    audit_log: AuditLogRepository
    data_portability: DataPortabilityRepository
    oauth_clients: OAuthClientRepository
    oauth_tokens: OAuthTokenRepository
    llm_credentials: LlmCredentialRepository
    ai_connections: AiConnectionRepository
    instance_settings: InstanceSettingsRepository
    personal_access_tokens: PersonalAccessTokenRepository
    rules: RuleRepository
    bank_connections: BankConnectionRepository

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        purgers: Sequence[UserDataPurger] = (),
    ) -> None:
        self._factory = session_factory
        self._purgers = purgers
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> UnitOfWork:
        self._session = self._factory()
        self.ledger = SQLLedgerRepository(self._session)
        self.tax_computations = SQLTaxComputationRepository(self._session)
        self.statements = SQLStatementRepository(self._session)
        self.reminders = SQLReminderRepository(self._session)
        self.agent_documents = SQLAgentDocumentRepository(self._session)
        self.agent_sessions = SQLAgentSessionRepository(self._session)
        self.user_profiles = SQLUserProfileRepository(self._session)
        self.goals = SQLGoalRepository(self._session)
        self.fi_scores = SQLFiScoreRepository(self._session)
        self.advisories = SQLAdvisoryRepository(self._session)
        self.fire_strategies = SQLFireStrategyRepository(self._session)
        self.budgets = SQLBudgetRepository(self._session)
        self.debts = SQLDebtRepository(self._session)
        self.holdings = SQLPortfolioRepository(self._session)
        self.recurring_subscriptions = SQLRecurringSubscriptionRepository(self._session)
        self.policies = SQLPolicyRepository(self._session)
        self.insurance_targets = SQLInsuranceTargetRepository(self._session)
        self.audit_log = SQLAuditLogRepository(self._session)
        self.data_portability = SQLDataPortabilityRepository(self._session, self._purgers)
        self.oauth_clients = SQLOAuthClientRepository(self._session)
        self.oauth_tokens = SQLOAuthTokenRepository(self._session)
        self.llm_credentials = SQLLlmCredentialRepository(self._session)
        self.ai_connections = SQLAiConnectionRepository(self._session)
        self.instance_settings = SQLInstanceSettingsRepository(self._session)
        self.personal_access_tokens = SQLPersonalAccessTokenRepository(self._session)
        self.rules = SQLRuleRepository(self._session)
        self.bank_connections = SQLBankConnectionRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        assert self._session is not None
        if exc_type is None:
            await self._session.commit()
        else:
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        assert self._session is not None
        await self._session.commit()
