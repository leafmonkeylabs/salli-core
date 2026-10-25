"""
Unit of work — wraps a single DB transaction.
Both the CLI and the API use this to ensure all writes in a use-case commit together.

An MCP client's write is audited in the transaction that makes it: while one
runs, `pending_audit` holds its record, and the first unit of work that
commits a change writes the record before committing, so the change and its
audit row are kept together or not at all (mcp_server.py).
"""

from __future__ import annotations

from collections.abc import Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from salli.adapters.db.access_grants import SQLAccessGrantRepository
from salli.adapters.db.decisions import SQLDecisionRepository, SQLPrincipleRepository
from salli.adapters.db.notifications import SQLNotificationRepository
from salli.adapters.db.reconciliations import SQLReconciliationRepository
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
    SQLHoldingPriceRepository,
    SQLHoldingTransactionRepository,
    SQLInstanceSettingsRepository,
    SQLInsuranceTargetRepository,
    SQLLedgerRepository,
    SQLLlmCredentialRepository,
    SQLLoginRepository,
    SQLOAuthClientRepository,
    SQLOAuthTokenRepository,
    SQLPersonalAccessTokenRepository,
    SQLPolicyRepository,
    SQLPortfolioRepository,
    SQLRecurringSubscriptionRepository,
    SQLReminderRepository,
    SQLRuleRepository,
    SQLStatementRepository,
    SQLUserProfileRepository,
)
from salli.adapters.db.tax_computations import SQLTaxComputationRepository
from salli.adapters.db.tax_returns import SQLTaxReturnRepository
from salli.adapters.db.tax_rule_sets import SQLTaxRuleSetRepository
from salli.application.ports import (
    AccessGrantRepository,
    AdvisoryRepository,
    AgentDocumentRepository,
    AgentSessionRepository,
    AiConnectionRepository,
    AuditLogRepository,
    BankConnectionRepository,
    BudgetRepository,
    DataPortabilityRepository,
    DebtRepository,
    DecisionRepository,
    FireStrategyRepository,
    FiScoreRepository,
    GoalRepository,
    HoldingPriceRepository,
    HoldingTransactionRepository,
    InstanceSettingsRepository,
    InsuranceTargetRepository,
    LedgerRepository,
    LlmCredentialRepository,
    LoginRepository,
    NotificationRepository,
    OAuthClientRepository,
    OAuthTokenRepository,
    PersonalAccessTokenRepository,
    PolicyRepository,
    PortfolioRepository,
    PrincipleRepository,
    ReconciliationRepository,
    RecurringSubscriptionRepository,
    ReminderRepository,
    RuleRepository,
    StatementRepository,
    TaxComputationRepository,
    TaxReturnRepository,
    TaxRuleSetRepository,
    UserProfileRepository,
)

if TYPE_CHECKING:
    from salli.extensions import UserDataPurger


@dataclass
class AuditRecord:
    """A write an MCP client asked for: who, through which client, which
    tool, with what. `recorded` once its row is written."""

    user_id: str
    client_id: str | None
    action: str
    params: dict[str, Any]
    recorded: bool = False


#: The MCP write in progress in this context, if any.
pending_audit: ContextVar[AuditRecord | None] = ContextVar("pending_audit", default=None)


class UnitOfWork:
    ledger: LedgerRepository
    tax_computations: TaxComputationRepository
    tax_returns: TaxReturnRepository
    tax_rule_sets: TaxRuleSetRepository
    statements: StatementRepository
    reconciliations: ReconciliationRepository
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
    holding_transactions: HoldingTransactionRepository
    holding_prices: HoldingPriceRepository
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
    access_grants: AccessGrantRepository
    logins: LoginRepository
    rules: RuleRepository
    bank_connections: BankConnectionRepository
    principles: PrincipleRepository
    decisions: DecisionRepository
    notifications: NotificationRepository

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
        self.tax_returns = SQLTaxReturnRepository(self._session)
        self.tax_rule_sets = SQLTaxRuleSetRepository(self._session)
        self.statements = SQLStatementRepository(self._session)
        self.reconciliations = SQLReconciliationRepository(self._session)
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
        self.holding_transactions = SQLHoldingTransactionRepository(self._session)
        self.holding_prices = SQLHoldingPriceRepository(self._session)
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
        self.access_grants = SQLAccessGrantRepository(self._session)
        self.logins = SQLLoginRepository(self._session)
        self.rules = SQLRuleRepository(self._session)
        self.bank_connections = SQLBankConnectionRepository(self._session)
        self.principles = SQLPrincipleRepository(self._session)
        self.decisions = SQLDecisionRepository(self._session)
        self.notifications = SQLNotificationRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        assert self._session is not None
        try:
            if exc_type is None:
                await self._audit_pending()
                await self._session.commit()
            else:
                await self._session.rollback()
        finally:
            # A failed audit row leaves the transaction uncommitted: closing
            # rolls it back.
            await self._session.close()

    async def commit(self) -> None:
        assert self._session is not None
        await self._audit_pending()
        await self._session.commit()

    async def _audit_pending(self) -> None:
        """Writes the pending MCP write's audit row, as succeeded, in this
        transaction if it changes anything; if the row can't be written,
        neither is the change."""
        pending = pending_audit.get()
        if pending is None or pending.recorded:
            return
        assert self._session is not None
        await self._session.flush()
        changed = await self._session.execute(text("select txid_current_if_assigned()"))
        if changed.scalar() is None:
            return
        await self.audit_log.log(
            pending.user_id,
            pending.action,
            pending.params,
            "succeeded",
            client_id=pending.client_id,
        )
        pending.recorded = True
