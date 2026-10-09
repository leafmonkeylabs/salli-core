"""
Every HTTP route and the `salli` command that does the same thing.

Salli is CLI-first: anything the API can do, the CLI can do. This table is how
that stays true. tests/contract/test_cli_api_parity.py fails when a route is in
neither table, when a command named here no longer exists, or when an entry
here no longer matches a route — so adding a route means adding its command, or
writing down why it has none.

Several routes may share one command (`entry show` prints an entry and its
provenance; `accounts show` is the account and its overview).
"""

from __future__ import annotations

Route = tuple[str, str]

CLI_FOR_ROUTE: dict[Route, str] = {
    # accounts
    ("GET", "/accounts/"): "accounts list",
    ("POST", "/accounts/"): "accounts add",
    ("GET", "/accounts/{account_id}"): "accounts show",
    ("GET", "/accounts/{account_id}/overview"): "accounts show",
    ("PATCH", "/accounts/{account_id}"): "accounts update",
    ("DELETE", "/accounts/{account_id}"): "accounts deactivate",
    ("POST", "/accounts/{account_id}/reactivate"): "accounts reactivate",
    # entries, ledger, tags
    ("GET", "/entries/"): "entry list",
    ("POST", "/entries/"): "entry add",
    ("POST", "/entries/parse"): "entry parse",
    ("GET", "/entries/{entry_id}"): "entry show",
    ("GET", "/entries/{entry_id}/provenance"): "entry show",
    ("POST", "/entries/{entry_id}/reverse"): "entry reverse",
    ("PUT", "/entries/postings/{posting_id}/tags"): "entry tag",
    ("GET", "/tags/"): "ledger tags",
    ("GET", "/ledger/trial-balance"): "ledger trial-balance",
    ("GET", "/ledger/income-statement"): "ledger income-statement",
    # tax
    ("GET", "/tax/packs"): "tax packs",
    ("POST", "/tax/compute"): "tax compute",
    ("GET", "/tax/latest"): "tax latest",
    # statements
    ("POST", "/statements/upload"): "parse upload",
    ("GET", "/statements/"): "parse list",
    ("GET", "/statements/{statement_id}"): "parse pending",
    ("POST", "/statements/{statement_id}/post"): "parse post",
    ("POST", "/statements/{statement_id}/discard"): "parse discard",
    # agent
    ("POST", "/agent/chat"): "agent chat",
    ("POST", "/agent/resume"): "agent resume",
    ("POST", "/agent/files"): "documents upload",
    ("GET", "/agent/sessions"): "agent sessions",
    ("DELETE", "/agent/sessions/{thread_id}"): "agent delete-session",
    ("GET", "/agent/history/{thread_id}"): "agent history",
    ("GET", "/agent/audit-log"): "agent audit-log",
    # documents
    ("GET", "/documents/"): "documents list",
    ("GET", "/documents/{doc_id}"): "documents show",
    ("DELETE", "/documents/{doc_id}"): "documents delete",
    # reminders
    ("GET", "/reminders/"): "reminders list",
    ("POST", "/reminders/"): "reminders add",
    ("POST", "/reminders/seed"): "reminders seed",
    ("POST", "/reminders/sync-alerts"): "reminders sync-alerts",
    ("PATCH", "/reminders/{reminder_id}/done"): "reminders done",
    ("DELETE", "/reminders/{reminder_id}"): "reminders delete",
    # financial independence
    ("GET", "/fi/score"): "fi score",
    ("POST", "/fi/score/recompute"): "fi score",
    ("GET", "/fi/score/history"): "fi history",
    ("GET", "/fi/projections"): "fi projections",
    ("GET", "/fi/surplus"): "fi surplus",
    ("POST", "/fi/simulate-purchase"): "fi simulate-purchase",
    ("GET", "/fi/goals"): "fi goals list",
    ("POST", "/fi/goals"): "fi goals add",
    ("PATCH", "/fi/goals/{goal_id}"): "fi goals update",
    ("DELETE", "/fi/goals/{goal_id}"): "fi goals delete",
    ("GET", "/fi/goals/{goal_id}/allocations"): "fi goals allocations",
    ("PUT", "/fi/goals/{goal_id}/allocations"): "fi goals allocate",
    ("GET", "/fi/strategy"): "fi strategy show",
    ("GET", "/fi/strategy/history"): "fi strategy history",
    ("POST", "/fi/strategy/generate"): "fi strategy generate",
    # advisor
    ("POST", "/advisor/run"): "advisor run",
    ("GET", "/advisor/reports"): "advisor reports list",
    ("GET", "/advisor/reports/latest"): "advisor reports latest",
    ("POST", "/advisor/reports/{report_id}/recommendations/{rec_id}/apply"): "advisor apply",
    ("POST", "/advisor/reports/{report_id}/recommendations/{rec_id}/dismiss"): "advisor dismiss",
    ("POST", "/advisor/briefing/prepare"): "advisor briefing",
    ("POST", "/advisor/briefing/resume"): "advisor briefing",
    ("GET", "/advisor/daily-briefing"): "advisor daily-briefing",
    ("PUT", "/advisor/daily-briefing"): "advisor daily-briefing",
    ("POST", "/advisor/cron/run-due"): "advisor run-due",
    # profile and onboarding
    ("GET", "/onboarding/status"): "onboarding status",
    ("POST", "/onboarding/complete"): "onboarding complete",
    ("GET", "/onboarding/profile"): "profile show",
    ("PATCH", "/onboarding/profile"): "profile update",
    ("POST", "/onboarding/balance-sheet"): "profile balance-sheet",
    ("POST", "/onboarding/income"): "profile income",
    ("POST", "/onboarding/risk-questionnaire"): "profile risk-questionnaire",
    ("POST", "/onboarding/goals"): "fi goals add",
    ("GET", "/onboarding/export"): "profile export",
    ("DELETE", "/onboarding/account"): "profile delete-account",
    # budget
    ("GET", "/budget/"): "budget list",
    ("POST", "/budget/"): "budget add",
    ("GET", "/budget/{budget_id}"): "budget show",
    ("PATCH", "/budget/{budget_id}"): "budget update",
    ("DELETE", "/budget/{budget_id}"): "budget delete",
    ("GET", "/budget/{budget_id}/summary"): "budget summary",
    # debt
    ("GET", "/debt/"): "debt list",
    ("POST", "/debt/"): "debt add",
    ("GET", "/debt/payoff-plan"): "debt payoff-plan",
    ("GET", "/debt/{debt_id}"): "debt show",
    ("PATCH", "/debt/{debt_id}"): "debt update",
    ("DELETE", "/debt/{debt_id}"): "debt delete",
    # portfolio
    ("GET", "/portfolio/"): "portfolio list",
    ("POST", "/portfolio/"): "portfolio add",
    ("GET", "/portfolio/summary"): "portfolio summary",
    ("GET", "/portfolio/{holding_id}"): "portfolio show",
    ("PATCH", "/portfolio/{holding_id}"): "portfolio update",
    ("DELETE", "/portfolio/{holding_id}"): "portfolio delete",
    # recurring subscriptions (the user's own)
    ("GET", "/subscriptions/"): "subscription list",
    ("POST", "/subscriptions/"): "subscription add",
    ("GET", "/subscriptions/reports"): "subscription report",
    ("GET", "/subscriptions/{subscription_id}"): "subscription show",
    ("PATCH", "/subscriptions/{subscription_id}"): "subscription update",
    ("DELETE", "/subscriptions/{subscription_id}"): "subscription delete",
    ("GET", "/subscriptions/{subscription_id}/report"): "subscription report",
    # insurance
    ("GET", "/insurance/policies"): "insurance policy list",
    ("POST", "/insurance/policies"): "insurance policy add",
    ("GET", "/insurance/policies/{policy_id}"): "insurance policy show",
    ("PATCH", "/insurance/policies/{policy_id}"): "insurance policy update",
    ("DELETE", "/insurance/policies/{policy_id}"): "insurance policy delete",
    ("GET", "/insurance/targets"): "insurance target list",
    ("PUT", "/insurance/targets"): "insurance target set",
    ("DELETE", "/insurance/targets/{policy_type}"): "insurance target delete",
    ("GET", "/insurance/report"): "insurance report",
    # reports
    ("GET", "/reports/balance-sheet"): "reports balance-sheet",
    ("GET", "/reports/net-worth"): "reports net-worth",
    ("GET", "/reports/goal-progress"): "reports goal-progress",
    ("GET", "/reports/{report_type}/export"): "reports export",
    # your own LLM keys
    ("GET", "/llm-keys"): "llm-keys list",
    ("PUT", "/llm-keys/{provider}"): "llm-keys set",
    ("DELETE", "/llm-keys/{provider}"): "llm-keys delete",
    ("GET", "/export/beancount"): "export beancount",
    ("GET", "/export/hledger"): "export hledger",
    ("GET", "/rules"): "rules list",
    ("POST", "/rules"): "rules add",
    ("POST", "/rules/test"): "rules test",
    ("GET", "/rules/suggestions"): "rules suggest",
    ("GET", "/rules/{rule_id}"): "rules show",
    ("PATCH", "/rules/{rule_id}"): "rules update",
    ("DELETE", "/rules/{rule_id}"): "rules delete",
    ("GET", "/insights/cash-flow"): "insights cash-flow",
    ("GET", "/insights/spending"): "insights spending",
    ("GET", "/insights/net-worth"): "insights net-worth",
    ("GET", "/insights/recurring"): "insights recurring",
    ("GET", "/tokens"): "tokens list",
    ("POST", "/tokens"): "tokens create",
    ("DELETE", "/tokens/{token_id}"): "tokens revoke",
    # MCP connections
    ("GET", "/mcp/connections/"): "mcp connections",
    ("DELETE", "/mcp/connections/{token_id}"): "mcp revoke",
    ("GET", "/mcp/connections/enabled"): "mcp status",
    ("PUT", "/mcp/connections/enabled"): "mcp enable",
    # identity
    ("GET", "/auth/me"): "whoami",
}

#: Routes with no command, and why. Each one is a protocol endpoint a browser
#: or an OAuth client calls, not something a person does.
NO_CLI: dict[Route, str] = {
    ("GET", "/healthz"): "liveness probe for the host",
    ("GET", "/meta"): "describes the HTTP server to remote clients; the in-process CLI has none",
    ("GET", "/.well-known/oauth-authorization-server"): "OAuth discovery (RFC 8414)",
    ("GET", "/.well-known/oauth-protected-resource"): "OAuth discovery (RFC 9728)",
    ("POST", "/mcp/oauth/register"): "dynamic client registration by an MCP client",
    ("POST", "/mcp/oauth/device_authorization"): "device sign-in, started by a remote client",
    ("GET", "/mcp/oauth/authorize"): "browser redirect step of the OAuth flow",
    ("POST", "/mcp/oauth/token"): "token exchange by an MCP client",
    ("POST", "/mcp/oauth/revoke"): "token revocation by an MCP client (RFC 7009)",
    ("GET", "/mcp/oauth/consent-info"): "read by a web app's consent screen",
    ("POST", "/mcp/oauth/consent"): "submitted by a web app's consent screen",
}
