"""
The HTTP API's contract: its version prefix, operation ids, and shared shapes.

Clients are generated from the OpenAPI document (the TypeScript SDK, the hosted
apps), so the document is the contract. Two things about it have to be stable
and deliberate rather than whatever the framework derives:

- **The version.** Every REST route lives under `/v1`. Routes are also served at
  their old unversioned paths, outside the schema and marked deprecated, until
  every client has moved.
- **Operation ids.** They become function names in every generated client
  (`accounts.list` → `accountsList`). FastAPI's default is the function name
  plus the path plus the method (`list_accounts_accounts__get`), which changes
  whenever a route is renamed or moved. Here each route is named once, in the
  table below; tests/contract fails when a route is missing from it.

The OAuth and MCP protocol endpoints keep their fixed paths outside `/v1`:
their URLs are dictated by the protocols and by clients configured long ago.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import UploadFile
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

API_PREFIX = "/v1"
API_VERSION = "1"

Route = tuple[str, str]

#: (method, path without the version prefix) → operation id.
OPERATION_IDS: dict[Route, str] = {
    # meta
    ("GET", "/healthz"): "meta.health",
    ("GET", "/meta"): "meta.get",
    ("GET", "/auth/me"): "auth.me",
    # accounts
    ("GET", "/accounts/"): "accounts.list",
    ("POST", "/accounts/"): "accounts.create",
    ("GET", "/accounts/{account_id}"): "accounts.get",
    ("PATCH", "/accounts/{account_id}"): "accounts.update",
    ("DELETE", "/accounts/{account_id}"): "accounts.deactivate",
    ("GET", "/accounts/{account_id}/overview"): "accounts.overview",
    ("POST", "/accounts/{account_id}/reactivate"): "accounts.reactivate",
    # entries, ledger, tags
    ("GET", "/entries/"): "entries.list",
    ("POST", "/entries/"): "entries.create",
    ("POST", "/entries/parse"): "entries.parse",
    ("GET", "/entries/{entry_id}"): "entries.get",
    ("GET", "/entries/{entry_id}/provenance"): "entries.provenance",
    ("POST", "/entries/{entry_id}/reverse"): "entries.reverse",
    ("PUT", "/entries/postings/{posting_id}/tags"): "entries.postings.setTags",
    ("GET", "/tags/"): "tags.list",
    ("GET", "/ledger/trial-balance"): "ledger.trialBalance",
    ("GET", "/ledger/income-statement"): "ledger.incomeStatement",
    # tax
    ("GET", "/tax/packs"): "tax.packs",
    ("POST", "/tax/compute"): "tax.compute",
    ("GET", "/tax/latest"): "tax.latest",
    # statements
    ("GET", "/statements/"): "statements.list",
    ("POST", "/statements/upload"): "statements.upload",
    ("GET", "/statements/{statement_id}"): "statements.pending",
    ("POST", "/statements/{statement_id}/post"): "statements.post",
    # agent
    ("POST", "/agent/chat"): "agent.chat",
    ("POST", "/agent/resume"): "agent.resume",
    ("POST", "/agent/files"): "agent.files.upload",
    ("GET", "/agent/sessions"): "agent.sessions.list",
    ("DELETE", "/agent/sessions/{thread_id}"): "agent.sessions.delete",
    ("GET", "/agent/history/{thread_id}"): "agent.history",
    ("GET", "/agent/audit-log"): "agent.auditLog",
    # documents
    ("GET", "/documents/"): "documents.list",
    ("GET", "/documents/{doc_id}"): "documents.get",
    ("DELETE", "/documents/{doc_id}"): "documents.delete",
    # reminders
    ("GET", "/reminders/"): "reminders.list",
    ("POST", "/reminders/"): "reminders.create",
    ("POST", "/reminders/seed"): "reminders.seedFilingCalendar",
    ("POST", "/reminders/sync-alerts"): "reminders.syncAlerts",
    ("DELETE", "/reminders/{reminder_id}"): "reminders.delete",
    ("PATCH", "/reminders/{reminder_id}/done"): "reminders.markDone",
    # financial independence
    ("GET", "/fi/score"): "fi.score.get",
    ("GET", "/fi/score/history"): "fi.score.history",
    ("POST", "/fi/score/recompute"): "fi.score.recompute",
    ("GET", "/fi/projections"): "fi.projections",
    ("POST", "/fi/simulate-purchase"): "fi.simulatePurchase",
    ("GET", "/fi/surplus"): "fi.surplus",
    ("GET", "/fi/strategy"): "fi.strategy.get",
    ("POST", "/fi/strategy/generate"): "fi.strategy.generate",
    ("GET", "/fi/strategy/history"): "fi.strategy.history",
    ("GET", "/fi/goals"): "goals.list",
    ("POST", "/fi/goals"): "goals.create",
    ("PATCH", "/fi/goals/{goal_id}"): "goals.update",
    ("DELETE", "/fi/goals/{goal_id}"): "goals.delete",
    ("GET", "/fi/goals/{goal_id}/allocations"): "goals.allocations.list",
    ("PUT", "/fi/goals/{goal_id}/allocations"): "goals.allocations.set",
    # advisor
    ("POST", "/advisor/run"): "advisor.run",
    ("GET", "/advisor/reports"): "advisor.reports.list",
    ("GET", "/advisor/reports/latest"): "advisor.reports.latest",
    (
        "POST",
        "/advisor/reports/{report_id}/recommendations/{rec_id}/apply",
    ): "advisor.recommendations.apply",
    (
        "POST",
        "/advisor/reports/{report_id}/recommendations/{rec_id}/dismiss",
    ): "advisor.recommendations.dismiss",
    ("GET", "/advisor/daily-briefing"): "advisor.dailyBriefing.get",
    ("PUT", "/advisor/daily-briefing"): "advisor.dailyBriefing.set",
    ("POST", "/advisor/briefing/prepare"): "advisor.briefing.prepare",
    ("POST", "/advisor/briefing/resume"): "advisor.briefing.resume",
    ("POST", "/advisor/cron/run-due"): "advisor.cron.runDue",
    # budgets
    ("GET", "/budget/"): "budgets.list",
    ("POST", "/budget/"): "budgets.create",
    ("GET", "/budget/{budget_id}"): "budgets.get",
    ("PATCH", "/budget/{budget_id}"): "budgets.update",
    ("DELETE", "/budget/{budget_id}"): "budgets.delete",
    ("GET", "/budget/{budget_id}/summary"): "budgets.summary",
    # debts
    ("GET", "/debt/"): "debts.list",
    ("POST", "/debt/"): "debts.create",
    ("GET", "/debt/payoff-plan"): "debts.payoffPlan",
    ("GET", "/debt/{debt_id}"): "debts.get",
    ("PATCH", "/debt/{debt_id}"): "debts.update",
    ("DELETE", "/debt/{debt_id}"): "debts.delete",
    # portfolio
    ("GET", "/portfolio/"): "holdings.list",
    ("POST", "/portfolio/"): "holdings.create",
    ("GET", "/portfolio/summary"): "portfolio.summary",
    ("GET", "/portfolio/{holding_id}"): "holdings.get",
    ("PATCH", "/portfolio/{holding_id}"): "holdings.update",
    ("DELETE", "/portfolio/{holding_id}"): "holdings.delete",
    # subscriptions
    ("GET", "/subscriptions/"): "subscriptions.list",
    ("POST", "/subscriptions/"): "subscriptions.create",
    ("GET", "/subscriptions/reports"): "subscriptions.reports",
    ("GET", "/subscriptions/{subscription_id}"): "subscriptions.get",
    ("PATCH", "/subscriptions/{subscription_id}"): "subscriptions.update",
    ("DELETE", "/subscriptions/{subscription_id}"): "subscriptions.delete",
    ("GET", "/subscriptions/{subscription_id}/report"): "subscriptions.report",
    # insurance
    ("GET", "/insurance/policies"): "insurance.policies.list",
    ("POST", "/insurance/policies"): "insurance.policies.create",
    ("GET", "/insurance/policies/{policy_id}"): "insurance.policies.get",
    ("PATCH", "/insurance/policies/{policy_id}"): "insurance.policies.update",
    ("DELETE", "/insurance/policies/{policy_id}"): "insurance.policies.delete",
    ("GET", "/insurance/targets"): "insurance.targets.list",
    ("PUT", "/insurance/targets"): "insurance.targets.set",
    ("DELETE", "/insurance/targets/{policy_type}"): "insurance.targets.delete",
    ("GET", "/insurance/report"): "insurance.report",
    # reports
    ("GET", "/reports/balance-sheet"): "reports.balanceSheet",
    ("GET", "/reports/net-worth"): "reports.netWorth",
    ("GET", "/reports/goal-progress"): "reports.goalProgress",
    ("GET", "/reports/{report_type}/export"): "reports.exportCsv",
    # profile, onboarding, the account itself
    ("GET", "/onboarding/status"): "onboarding.status",
    ("POST", "/onboarding/complete"): "onboarding.complete",
    ("POST", "/onboarding/balance-sheet"): "onboarding.balanceSheet",
    ("POST", "/onboarding/income"): "onboarding.income",
    ("POST", "/onboarding/goals"): "onboarding.goals",
    ("POST", "/onboarding/risk-questionnaire"): "onboarding.riskQuestionnaire",
    ("GET", "/onboarding/profile"): "profile.get",
    ("PATCH", "/onboarding/profile"): "profile.update",
    ("GET", "/onboarding/export"): "account.export",
    ("DELETE", "/onboarding/account"): "account.delete",
    # LLM keys and MCP connections
    ("GET", "/llm-keys"): "llmKeys.list",
    ("PUT", "/llm-keys/{provider}"): "llmKeys.set",
    ("DELETE", "/llm-keys/{provider}"): "llmKeys.delete",
    ("GET", "/mcp/connections/"): "mcp.connections.list",
    ("DELETE", "/mcp/connections/{token_id}"): "mcp.connections.revoke",
    ("GET", "/mcp/connections/enabled"): "mcp.enabled.get",
    ("PUT", "/mcp/connections/enabled"): "mcp.enabled.set",
    # personal access tokens
    ("GET", "/tokens"): "tokens.list",
    ("POST", "/tokens"): "tokens.create",
    ("DELETE", "/tokens/{token_id}"): "tokens.revoke",
    # OAuth (protocol paths, outside /v1)
    ("GET", "/.well-known/oauth-authorization-server"): "oauth.authorizationServerMetadata",
    ("GET", "/.well-known/oauth-protected-resource"): "oauth.protectedResourceMetadata",
    ("POST", "/mcp/oauth/register"): "oauth.register",
    ("POST", "/mcp/oauth/device_authorization"): "oauth.deviceAuthorization",
    ("GET", "/mcp/oauth/authorize"): "oauth.authorize",
    ("GET", "/mcp/oauth/consent-info"): "oauth.consentInfo",
    ("POST", "/mcp/oauth/consent"): "oauth.consent",
    ("POST", "/mcp/oauth/token"): "oauth.token",
    ("POST", "/mcp/oauth/revoke"): "oauth.revoke",
}


def unversioned(path: str) -> str:
    return path.removeprefix(API_PREFIX) if path.startswith(API_PREFIX + "/") else path


def operation_id(route: APIRoute) -> str:
    """FastAPI's `generate_unique_id_function`: the route's name in the table.

    A route an extension adds is not in Salli's table, so it is named after its
    tag and function (`widgets.list_widgets`); Salli's own routes must be
    listed, which tests/contract enforces.
    """
    method = sorted(route.methods)[0]
    known = OPERATION_IDS.get((method, unversioned(route.path)))
    if known:
        return known
    tag = str(route.tags[0]) if route.tags else "ext"
    return f"{tag}.{route.name}"


# ── Shared shapes ──────────────────────────────────────────────────────────────

#: An amount of money: a decimal string with exactly its currency's decimals
#: ("1234.50", "1200", "1.234"). Never a JSON number — a client would read it as
#: a binary float — and always alongside a `currency` that says what it is in.
Amount = Annotated[
    str,
    Field(
        pattern=r"^-?\d+(\.\d+)?$",
        examples=["1234.50"],
        description="Decimal string in the currency's own precision; never a float.",
    ),
]

#: An ISO 4217 currency code.
CurrencyCode = Annotated[
    str, Field(pattern=r"^[A-Z]{3}$", examples=["USD"], description="ISO 4217 currency code")
]


class Problem(BaseModel):
    """An error, as RFC 9457 problem details (`application/problem+json`).

    `type` names the kind of problem as a path under `/problems/`, or is
    `about:blank` for a plain HTTP error. `detail` is what clients written
    before this shape existed already read: a sentence for most errors, the
    field-by-field list for a request that failed validation.
    """

    type: str = Field(examples=["/problems/fx-rate-unavailable"])
    title: str
    status: int
    detail: Any = None


class Ref(BaseModel):
    """What a create or update returns: the id of the thing it touched."""

    id: str


class Updated(BaseModel):
    """What the updates that predate `Ref` return instead of an id."""

    updated: bool


class FileUpload(BaseModel):
    """A multipart/form-data body carrying one file, as `file`."""

    file: UploadFile
