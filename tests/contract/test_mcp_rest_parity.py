"""
MCP keeps up with the API: every REST operation is reached by an MCP tool
(PARITY), or is in EXEMPT with the reason an agent has no business with it.
A new route fails here until it is given one or the other, and every tool
PARITY names must exist.

An EXEMPT key ending in `*` covers every route under it, for one reason.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from benchmark.households import Salli

SPEC = Path(__file__).resolve().parents[2] / "openapi" / "openapi.json"

#: Route → the tool that does the same for an agent.
PARITY = {
    "GET /v1/accounts/": "get_accounts",
    "POST /v1/accounts/": "create_account",
    "GET /v1/accounts/{account_id}": "get_accounts",
    "PATCH /v1/accounts/{account_id}": "update_account",
    "GET /v1/accounts/{account_id}/overview": "get_overview",
    "POST /v1/entries/": "post_journal_entry",
    "GET /v1/entries/": "search_entries",
    "GET /v1/entries/search": "search_entries",
    "GET /v1/entries/{entry_id}": "get_entry",
    "GET /v1/entries/{entry_id}/provenance": "get_entry",
    "POST /v1/entries/{entry_id}/reverse": "reverse_entry",
    "POST /v1/entries/{entry_id}/recategorise": "recategorise_entry",
    "GET /v1/ledger/trial-balance": "get_trial_balance",
    "POST /v1/tax/compute": "get_tax_computation",
    "GET /v1/tax/latest": "get_tax_computation",
    "GET /v1/tax/current-year": "get_tax_computation",
    "POST /v1/tax/explain": "explain_tax_line",
    "GET /v1/tax/return-records": "list_tax_returns",
    "GET /v1/tax/return-records/{return_id}": "list_tax_returns",
    "GET /v1/tax/schema": "get_tax_rule_schema",
    "GET /v1/tax/rule-sets": "list_tax_rule_sets",
    "POST /v1/tax/rule-sets": "draft_tax_rule_set",
    "POST /v1/tax/rule-sets/import": "draft_tax_rule_set",
    "GET /v1/tax/rule-sets/{rule_set_id}": "get_tax_rule_set",
    "POST /v1/tax/rule-sets/{rule_set_id}/versions": "draft_tax_rule_set",
    "GET /v1/tax/rule-sets/{rule_set_id}/versions/{version_id}": "get_tax_rule_set",
    "POST /v1/tax/rule-sets/{rule_set_id}/versions/{version_id}/validate": "validate_tax_rule_set",
    "POST /v1/tax/rule-sets/{rule_set_id}/versions/{version_id}/propose": "propose_tax_rule_set",
    "GET /v1/tax/rule-sets/{rule_set_id}/diff": "diff_tax_rule_set_versions",
    "GET /v1/tax/rule-sets/{rule_set_id}/suggested-accounts": "suggested_tax_accounts",
    "POST /v1/tax/rule-sets/{rule_set_id}/suggested-accounts": "apply_suggested_tax_accounts",
    "GET /v1/tax/rule-sets/{rule_set_id}/versions/{version_id}/export": "get_tax_rule_set",
    "POST /v1/tax/rule-sets/{rule_set_id}/versions/{version_id}/evaluate": "evaluate_tax_rule_set",
    "GET /v1/documents/": "list_documents",
    "GET /v1/documents/{doc_id}": "read_document",
    "DELETE /v1/documents/{doc_id}": "delete_document",
    "GET /v1/onboarding/profile": "get_financial_profile",
    "POST /v1/statements/upload": "import_statement",
    "POST /v1/statements/drafts": "import_statement",
    "GET /v1/statements/": "list_pending_transactions",
    "GET /v1/statements/{statement_id}": "list_pending_transactions",
    "POST /v1/statements/{statement_id}/post": "post_transactions",
    "POST /v1/statements/{statement_id}/discard": "discard_transactions",
    "POST /v1/statements/categorize": "categorize_transactions",
    "GET /v1/reminders/": "list_reminders",
    "POST /v1/reminders/": "create_reminder",
    "GET /v1/fi/assumptions": "get_fi_assumptions",
    "PATCH /v1/fi/assumptions": "set_fi_assumption",
    "GET /v1/fi/score": "get_fi_projections",
    "GET /v1/fi/goals": "list_goals",
    "GET /v1/fi/projections": "get_fi_projections",
    "GET /v1/fi/odds": "get_fi_odds",
    "GET /v1/advisor/reports/latest": "get_latest_briefing",
    "POST /v1/advisor/run": "run_briefing",
    "GET /v1/budget/": "list_budgets",
    "PUT /v1/budget/monthly": "set_monthly_budget",
    "GET /v1/budget/monthly": "get_budget_summary",
    "GET /v1/budget/current": "get_budget_summary",
    "GET /v1/budget/{budget_id}/summary": "get_budget_summary",
    "GET /v1/debt/": "list_debts",
    "POST /v1/debt/": "add_debt",
    "GET /v1/debt/payoff-plan": "get_payoff_plan",
    "GET /v1/debt/{debt_id}": "list_debts",
    "PATCH /v1/debt/{debt_id}": "update_debt",
    "GET /v1/portfolio/": "list_holdings",
    "GET /v1/portfolio/summary": "get_portfolio_summary",
    "GET /v1/portfolio/performance": "get_portfolio_performance",
    "GET /v1/portfolio/{holding_id}": "list_holdings",
    "PATCH /v1/portfolio/{holding_id}": "link_holding",
    "GET /v1/portfolio/{holding_id}/performance": "get_portfolio_performance",
    "GET /v1/ips": "get_investment_policy",
    "GET /v1/subscriptions/reports": "get_subscription_report",
    "GET /v1/insurance/report": "get_coverage_report",
    "GET /v1/reports/net-worth": "get_net_worth_history",
    "GET /v1/reconciliation/statements/{statement_id}": "get_reconciliation",
    "GET /v1/rules": "suggest_rules",
    "POST /v1/rules": "create_rule",
    "GET /v1/rules/suggestions": "suggest_rules",
    "GET /v1/insights/cash-flow": "get_cash_flow",
    "GET /v1/insights/spending": "get_spending",
    "GET /v1/insights/net-worth": "get_net_worth_history",
    "GET /v1/insights/recurring": "get_recurring_payments",
    "GET /v1/insights/forecast": "get_cash_forecast",
    "GET /v1/insights/safe-to-spend": "get_safe_to_spend",
    "GET /v1/insights/signals": "get_signals",
    "GET /v1/baseline": "get_baseline",
    "POST /v1/scenarios/run": "run_scenario",
    "POST /v1/scenarios/compare": "compare_options",
    "POST /v1/scenarios/odds": "get_fi_odds",
    "GET /v1/principles": "list_principles",
    "POST /v1/principles": "add_principle",
    "POST /v1/principles/check": "check_principles",
    "GET /v1/decisions/templates": "list_decision_templates",
    "GET /v1/decisions/templates/{template_id}": "list_decision_templates",
    "POST /v1/decisions/start": "start_decision",
    "GET /v1/decisions": "list_decisions",
    "POST /v1/decisions": "record_decision",
    "GET /v1/decisions/reviews": "list_due_reviews",
    "GET /v1/decisions/{decision_id}": "get_decision",
    "POST /v1/decisions/{decision_id}/review": "review_decision",
}

#: Route → why an agent does not get it.
EXEMPT = {
    "GET /.well-known/*": "OAuth discovery, for clients before they connect",
    "* /mcp/oauth/*": "OAuth plumbing that connects an agent",
    "GET /healthz": "the operator's health check",
    "GET /v1/meta": "the server's version and extensions, for clients",
    "* /v1/auth/*": "the person's own sign-ins, password and two-step: first-party only",
    "* /v1/tokens*": "personal access tokens: credentials an agent never mints",
    "* /v1/mcp/connections/*": "the person's AI connections: an agent never widens its own",
    "* /v1/llm-keys*": "the person's AI provider keys: secrets",
    "* /v1/ai/*": "the person's AI settings and connections: first-party",
    "* /v1/access-grants*": "who may read the books: the person's own decision",
    "* /v1/devices/*": "the phone's push registration",
    "* /v1/notifications/*": "digest preferences and the sender's cron",
    "* /v1/agent/*": "Salli's own in-app agent, which an agent does not drive",
    "* /v1/bank-connections*": "bank credentials and their cron: first-party",
    "POST /v1/advisor/cron/run-due": "cron",
    "* /v1/advisor/daily-briefing": "the person's own briefing setting",
    "GET /v1/advisor/reports": "the history behind get_latest_briefing",
    "* /v1/advisor/briefing/*": "the briefing's human review, in the person's own app",
    "GET /v1/onboarding/export": "the person's whole export: behind the step-up",
    "DELETE /v1/onboarding/account": "erasure: behind the step-up",
    "* /v1/onboarding/*": "first-run setup, in the person's own app",
    "* /v1/export/*": "plain-text exports of the whole ledger, for the person",
    "GET /v1/reports/{report_type}/export": "files for the person",
    "* /v1/decisions/export*": "files for the person",
    "GET /v1/decisions/{decision_id}/markdown": "a file for the person",
    "POST /v1/decisions/{decision_id}/notes": "the person's own note on a decision",
    "POST /v1/tax/rule-sets/{rule_set_id}/versions/{version_id}/activate": (
        "only the person activates tax rules (tax:activate)"
    ),
    "* /v1/tax/returns/*": "return preparation's human review, in the person's own app",
    "POST /v1/tax/returns/prepare": "return preparation's human review",
    "* /v1/tax/return-records*": "filing records: the person's own statement of what was filed",
    "* /v1/ledger/*": "closing books, FX revaluation and the hash chain: the person's own acts",
    "PUT /v1/entries/postings/{posting_id}/tags": "tags are set with the entry by the person",
    "GET /v1/tags/": "tags are read with entries",
    "POST /v1/entries/parse": "text to an entry draft, the app's own helper",
    "DELETE /v1/accounts/{account_id}": "closing an account: the person's own act",
    "POST /v1/accounts/{account_id}/reactivate": "the person's own act",
    "POST /v1/statements/check": "the upload screen's preview",
    "* /v1/reminders/*": "seeding, alerts and done: the person's own calendar",
    "POST /v1/reminders/seed": "seeding the filing calendar: the person's own act",
    "POST /v1/reminders/sync-alerts": "the app's alerts",
    "* /v1/fi/score*": "the stored score history, recomputed by the briefing",
    "* /v1/fi/goals*": "goal edits are the person's; list_goals reads them",
    "GET /v1/fi/surplus": "read with get_fi_projections",
    "* /v1/fi/plan": "the person's plan by age: their own statement",
    "* /v1/fi/cma-packs*": "capital-market assumptions are imported by the person",
    "* /v1/budget/*": "budget edits beyond the monthly one: the person's own",
    "POST /v1/budget/": "budget edits beyond the monthly one: the person's own",
    "GET /v1/budget/trend": "read with get_budget_summary",
    "DELETE /v1/debt/{debt_id}": "removing a debt: the person's own act",
    "* /v1/portfolio/*": "trades, prices and lots are the person's records",
    "POST /v1/portfolio/": "holdings are the person's records",
    "* /v1/ips*": "the investment policy is the person's own; get_investment_policy reads it",
    "* /v1/subscriptions/*": "subscription records are the person's; the report is read",
    "POST /v1/subscriptions/": "subscription records are the person's",
    "* /v1/insurance/*": "policies and targets are the person's; the report is read",
    "* /v1/reports/*": "statements read through the insights tools",
    "* /v1/reconciliation/*": "reconciling a statement is the person's own act",
    "* /v1/rules/*": "rule edits and tests are the person's; create_rule adds one",
    "* /v1/principles/*": "editing or archiving a principle is the person's own",
    "* /v1/statements/*": "the statement screens",
}


def _exempt(route: str) -> bool:
    method, path = route.split(" ", 1)
    for key in EXEMPT:
        m, p = key.split(" ", 1)
        if m not in ("*", method):
            continue
        if path == p or (p.endswith("*") and path.startswith(p[:-1])):
            return True
    return False


def _routes() -> list[str]:
    spec = json.loads(SPEC.read_text())
    return [
        f"{method.upper()} {path}"
        for path, item in spec["paths"].items()
        for method, op in item.items()
        if isinstance(op, dict) and "operationId" in op
    ]


def test_every_route_has_a_tool_or_a_reason():
    missing = [r for r in _routes() if r not in PARITY and not _exempt(r)]
    assert missing == [], "give each a tool in PARITY or a reason in EXEMPT"


def test_every_tool_named_exists():
    tools = {t["name"] for t in asyncio.run(Salli("household").tools())}
    assert set(PARITY.values()) - tools == set()
    assert set(PARITY) <= set(_routes())
