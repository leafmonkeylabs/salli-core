"""
MCP protocol endpoint — the resource-server half of MCP support.

Mounted at /mcp. Exposes the same tool surface as the in-app chat agent
("Scrooge", domain/agents/tools.py) over the same application services — but
each tool here resolves user_id from the OAuth bearer token (the grant itself
is the scoping mechanism), rather than taking it as a parameter or relying on
Scrooge's ambient contextvar.

Scrooge's three write tools (create_account, create_reminder,
post_journal_entry) normally pause via langgraph.types.interrupt() for
in-chat human approval — that mechanism has no equivalent for a stateless MCP
tool call, so here they execute immediately once the client presents a valid
token. The OAuth consent screen (mcp_oauth.py) is the approval gate: it is
where the user authorizes this client to read *and write* their data: every
write is still recorded to the immutable audit log.

The actual OAuth authorization server (register/authorize/consent/token) lives
in mcp_oauth.py; this module is only the Resource Server half, verifying
tokens via McpOAuthService.verify_access_token through the MCP SDK's
TokenVerifier protocol.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any, cast

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl

from salli.application.services.mcp_oauth_service import McpOAuthService


class SalliTokenVerifier(TokenVerifier):
    """Bridges the MCP SDK's auth middleware to McpOAuthService — every call
    re-checks the live mcp_enabled gate, not just token expiry."""

    def __init__(self, mcp_oauth: McpOAuthService) -> None:
        self._mcp_oauth = mcp_oauth

    async def verify_token(self, token: str) -> AccessToken | None:
        record = await self._mcp_oauth.verify_access_token(token)
        if record is None:
            return None
        scopes: list[str] = [s for s in (record["scope"] or "").split()]
        return AccessToken(
            token=token,
            client_id=record["client_id"],
            scopes=scopes,
            expires_at=int(record["expires_at"].timestamp()),
            resource=record["resource"],
            subject=record["user_id"],
        )


def _current_user_id() -> str:
    access_token = get_access_token()
    if access_token is None or access_token.subject is None:
        raise RuntimeError("MCP tool called without an authenticated user")
    return access_token.subject


async def _log_audit(ledger_svc: Any, user_id: str, action: str, params: dict[str, Any]) -> None:
    """Record every write this MCP client makes to the immutable audit log.
    Never blocks the tool's own outcome on logging failure."""
    try:
        async with ledger_svc._uow_factory() as uow:
            await uow.audit_log.log(user_id, action, params, "approved")
    except Exception:
        pass


def build_mcp_server(services: Any, issuer_url: str) -> FastMCP:
    ledger_svc = services.ledger
    tax_svc = services.tax
    profile_svc = services.profile
    budget_svc = services.budget
    debt_svc = services.debt
    portfolio_svc = services.portfolio
    subscription_svc = services.subscription
    insurance_svc = services.insurance
    advisor_svc = services.advisor
    documents_svc = services.documents
    reminders_svc = services.reminders

    mcp = FastMCP(
        name="Salli",
        instructions=(
            "Access to one user's Salli financial data and account: net worth, "
            "budgets, debt payoff plans, portfolio, subscriptions, insurance coverage, "
            "tax position, saved documents/memories, and the Wealth Advisor. Numbers "
            "returned by read tools are authoritative. Do not recompute or adjust "
            "them. Tools that write (create_account, create_reminder, "
            "post_journal_entry, and the document/memory writers) take effect "
            "immediately. The user already authorized this when they connected."
        ),
        token_verifier=SalliTokenVerifier(services.mcp_oauth),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(issuer_url), resource_server_url=None, required_scopes=None
        ),
        # Default streamable_http_path ("/mcp") — main.py mounts this app at
        # root "/", so the served path is exactly /mcp, matching the resource
        # URL we advertise (no trailing slash, no redirect on a bare request).
        # Stateless: none of our tools need server-initiated notifications, and
        # a single-instance Render deploy restarts on every push — a stateful
        # session tied to in-memory server state would silently die under a
        # connected client on the very next deploy (each request gets its own
        # transport instead, so nothing is pinned to server-process memory).
        stateless_http=True,
        # FastMCP auto-enables an allowlist check on the Host header ("DNS
        # rebinding protection") whenever host defaults to 127.0.0.1 — which
        # it does here, since we never set host (we're mounted under our own
        # FastAPI app, not run standalone). That allowlist only ever contains
        # loopback patterns, so every real request — Host: <your public host>
        # — fails it with a 421, regardless of a valid bearer token. This
        # protection targets locally-exposed MCP servers trusted by same-host
        # browsers; it's meaningless for a public server that already requires
        # a valid OAuth bearer token on every request, so it's disabled here
        # rather than trying to keep a Host allowlist in sync with prod/dev.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @mcp.tool()
    async def get_trial_balance(
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        """Return the trial balance (account balances) for the user's ledger."""
        user_id = _current_user_id()
        balances = await ledger_svc.get_trial_balance(user_id, from_date, to_date)
        return {
            "trial_balance": {k: str(v) for k, v in balances.items()},
            "net": str(sum(balances.values(), Decimal(0))),
        }

    @mcp.tool()
    async def get_accounts() -> dict[str, Any]:
        """List all accounts in the user's chart of accounts."""
        user_id = _current_user_id()
        accounts = await ledger_svc.list_accounts(user_id)
        return {
            "accounts": [
                {"id": a.id, "code": a.code, "name": a.name, "type": a.type, "currency": a.currency}
                for a in accounts
            ]
        }

    @mcp.tool()
    async def get_tax_computation(year: str = "2025/26") -> dict[str, Any]:
        """Return the latest stored tax computation for the given year of assessment.
        If none exists, compute it now."""
        user_id = _current_user_id()
        result = await tax_svc.compute_tax(user_id, year)

        def _bw(bw: Any) -> dict[str, str]:
            if isinstance(bw, dict):
                d = cast("dict[str, Any]", bw)
                return {
                    "from": str(d.get("from_amount", "0")),
                    "to": str(d["to_amount"]) if d.get("to_amount") else "∞",
                    "rate": str(d.get("rate", "")),
                    "taxable_in_band": str(d.get("taxable_in_band", "0")),
                    "tax": str(d.get("tax", "0")),
                }
            return {
                "from": str(bw.from_amount),
                "to": str(bw.to_amount) if bw.to_amount else "∞",
                "rate": str(bw.rate),
                "taxable_in_band": str(bw.taxable_in_band),
                "tax": str(bw.tax),
            }

        return {
            "year": result.pack_year,
            "pack_version": result.pack_version,
            "gross_income": str(result.gross_income),
            "personal_relief": str(result.personal_relief_applied),
            "taxable_income": str(result.taxable_income),
            "tax_before_credits": str(result.tax_before_credits),
            "apit_credit": str(result.apit_credit),
            "ait_credit": str(result.ait_credit),
            "foreign_tax_credit": str(result.foreign_tax_credit),
            "tax_payable": str(result.tax_payable),
            "band_workings": [_bw(bw) for bw in result.band_workings],
        }

    @mcp.tool()
    def list_tax_packs() -> dict[str, Any]:
        """List available tax packs (country, year, version)."""
        packs = tax_svc.list_packs()
        return {
            "packs": [
                {
                    "country": p.country,
                    "year": p.year,
                    "version": p.version,
                    "period_start": p.period_start,
                    "period_end": p.period_end,
                }
                for p in packs
            ]
        }

    @mcp.tool()
    def explain_tax_band(band_index: int, year: str = "2025/26") -> dict[str, Any]:
        """Explain a specific tax band (rate, threshold, how much tax it generates)."""
        from salli.domain.tax.packs.registry import get_pack

        pack = get_pack("LK", year)
        if band_index < 0 or band_index >= len(pack.bands):
            return {"error": f"Band index {band_index} out of range (0–{len(pack.bands) - 1})"}
        band = pack.bands[band_index]
        return {
            "band_index": band_index,
            "upto": str(band.upto) if band.upto else "unbounded",
            "rate": str(band.rate),
            "rate_pct": f"{float(band.rate) * 100:.0f}%",
            "personal_relief": str(pack.personal_relief),
        }

    @mcp.tool()
    async def get_financial_profile() -> dict[str, Any]:
        """Return the user's fact-find profile: risk category, risk score, life stage,
        dependents, employment status, and residency."""
        user_id = _current_user_id()
        return await profile_svc.get_profile(user_id)

    @mcp.tool()
    async def get_budget_summary(budget_id: str | None = None) -> dict[str, Any]:
        """Return a budget's category limits vs. actual spend for its period."""
        user_id = _current_user_id()
        if budget_id is None:
            budgets = await budget_svc.list_budgets(user_id)
            if not budgets:
                return {"error": "No budgets found."}
            budget_id = budgets[0]["id"]
        summary = await budget_svc.get_summary(user_id, budget_id)
        if summary is None:
            return {"error": f"Budget {budget_id} not found"}
        return summary

    @mcp.tool()
    async def get_payoff_plan(
        extra_monthly_payment: str = "0",
        strategy: str = "avalanche",
    ) -> dict[str, Any]:
        """Return an avalanche or snowball payoff plan for the user's active debts."""
        if strategy not in ("avalanche", "snowball"):
            return {"error": f"Unknown strategy '{strategy}'. Use 'avalanche' or 'snowball'."}
        user_id = _current_user_id()
        return await debt_svc.get_payoff_plan(user_id, Decimal(extra_monthly_payment), strategy)

    @mcp.tool()
    async def get_portfolio_summary(target_allocation: str | None = None) -> dict[str, Any]:
        """Return the user's investment allocation by asset class, total gain/ROI,
        and (if a target allocation is given) rebalancing drift alerts. Target
        allocation format: 'asset_class:pct,...', e.g. 'equity:0.6,bond:0.3,cash:0.1'."""
        user_id = _current_user_id()
        parsed_target: dict[str, Decimal] | None = None
        if target_allocation:
            parsed_target = {}
            for pair in target_allocation.split(","):
                asset_class, _, pct = pair.strip().partition(":")
                if asset_class and pct:
                    parsed_target[asset_class] = Decimal(pct)
        return await portfolio_svc.get_summary(user_id, parsed_target)

    @mcp.tool()
    async def get_subscription_report(subscription_id: str | None = None) -> dict[str, Any]:
        """Return missed-charge/price-change report(s) for the user's recurring
        subscriptions."""
        user_id = _current_user_id()
        today = datetime.date.today().isoformat()
        if subscription_id is None:
            return {"reports": await subscription_svc.get_all_reports(user_id, today)}
        report = await subscription_svc.get_report(user_id, subscription_id, today)
        if report is None:
            return {"error": f"Subscription {subscription_id} not found"}
        return report

    @mcp.tool()
    async def get_coverage_report() -> dict[str, Any]:
        """Return the user's insurance coverage-gap report: declared target vs.
        actual coverage per policy type, uncovered policy types, and policies
        expiring within 30 days."""
        user_id = _current_user_id()
        today = datetime.date.today().isoformat()
        return await insurance_svc.get_report(user_id, today)

    @mcp.tool()
    async def get_latest_advisor_report() -> dict[str, Any]:
        """Return the user's most recent Wealth Advisor report (summary, FIRE tier
        assessment, prioritised recommendations) without generating a new one."""
        user_id = _current_user_id()
        report = await advisor_svc.get_latest_report(user_id)
        return report or {"error": "No advisor report found yet."}

    @mcp.tool()
    async def run_wealth_advisor() -> dict[str, Any]:
        """Generate a fresh Wealth Advisor report now — a structured, strategy-linked
        mentoring pass over the user's FI score, FIRE strategy, and goals. It is a
        fresh model run, so prefer get_latest_advisor_report unless the user
        explicitly asks for a fresh analysis."""
        from salli.domain.usage import UsageLimitReached

        user_id = _current_user_id()
        try:
            return await advisor_svc.run_advisor(user_id, email=None, trigger="manual")
        except UsageLimitReached as exc:
            return {"error": exc.message}

    # ── Documents & memories ─────────────────────────────────────────────

    @mcp.tool()
    async def save_document(
        title: str,
        content: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Save a text document to the user's document store. Documents persist
        across sessions."""
        user_id = _current_user_id()
        doc_id = await documents_svc.save_document(
            user_id,
            title=title,
            content=content,
            tags=tags,
            description=description,
            source="mcp_client",
            namespace="documents",
        )
        return {"doc_id": doc_id, "title": title, "saved": True}

    @mcp.tool()
    async def read_document(doc_id: str) -> dict[str, Any]:
        """Retrieve a saved document by its ID."""
        user_id = _current_user_id()
        doc = await documents_svc.get_document(user_id, doc_id)
        if not doc:
            return {"error": f"Document {doc_id} not found"}
        return doc

    @mcp.tool()
    async def update_document(
        doc_id: str,
        title: str | None = None,
        content: str | None = None,
    ) -> dict[str, Any]:
        """Update the title or content of an existing document."""
        user_id = _current_user_id()
        updates = {k: v for k, v in {"title": title, "content": content}.items() if v is not None}
        if not updates:
            return {"error": "No updates provided"}
        await documents_svc.update_document(user_id, doc_id, **updates)
        return {"doc_id": doc_id, "updated": list(updates.keys())}

    @mcp.tool()
    async def list_documents(
        namespace: str | None = None,
        tags: list[str] | None = None,
        search_query: str | None = None,
    ) -> dict[str, Any]:
        """List saved documents. Filter by namespace, tags, or a search query."""
        user_id = _current_user_id()
        docs = await documents_svc.list_documents(
            user_id, tags=tags or None, namespace=namespace, search=search_query
        )
        return {
            "documents": [
                {
                    "id": d.get("id"),
                    "title": d.get("title"),
                    "namespace": d.get("namespace"),
                    "tags": d.get("tags"),
                    "source": d.get("source"),
                    "description": d.get("description"),
                    "updated_at": d.get("updated_at"),
                }
                for d in docs
            ]
        }

    @mcp.tool()
    async def delete_document(doc_id: str) -> dict[str, Any]:
        """Permanently delete a document from the user's document store."""
        user_id = _current_user_id()
        await documents_svc.delete_document(user_id, doc_id)
        await _log_audit(ledger_svc, user_id, "delete_document", {"doc_id": doc_id})
        return {"doc_id": doc_id, "deleted": True}

    @mcp.tool()
    async def save_memory(slug: str, value: str) -> dict[str, Any]:
        """Save or update a named memory (e.g. 'accountant_name', 'tax_year_goal').
        Calling save_memory with the same slug overwrites the previous value."""
        user_id = _current_user_id()
        await documents_svc.save_memory(user_id, slug=slug, value=value)
        return {"slug": slug, "saved": True}

    @mcp.tool()
    async def get_memory(slug: str) -> dict[str, Any]:
        """Retrieve a named memory by its slug key."""
        user_id = _current_user_id()
        mem = await documents_svc.get_memory(user_id, slug=slug)
        if not mem:
            return {"slug": slug, "found": False}
        return {
            "slug": slug,
            "found": True,
            "value": mem.get("content"),
            "updated_at": mem.get("updated_at"),
        }

    @mcp.tool()
    async def list_memories() -> dict[str, Any]:
        """List all named memories stored for this user."""
        user_id = _current_user_id()
        memories = await documents_svc.list_memories(user_id)
        return {
            "count": len(memories),
            "memories": [
                {
                    "slug": m.get("title"),
                    "value": m.get("content"),
                    "updated_at": m.get("updated_at"),
                }
                for m in memories
            ],
        }

    # ── Writes (no in-chat approval step — the OAuth grant is the approval;
    # every call is still recorded to the audit log) ─────────────────────

    @mcp.tool()
    async def create_account(
        code: str,
        name: str,
        account_type: str,
        currency: str = "LKR",
    ) -> dict[str, Any]:
        """Create a new account in the chart of accounts. account_type is one of:
        asset, liability, equity, income, expense."""
        user_id = _current_user_id()
        params = {"code": code, "name": name, "type": account_type, "currency": currency}
        account_id = await ledger_svc.add_account(user_id, code, name, account_type, currency)
        await _log_audit(ledger_svc, user_id, "create_account", params)
        return {"account_id": account_id, "code": code, "name": name, "created": True}

    @mcp.tool()
    async def create_reminder(description: str, due_date: str) -> dict[str, Any]:
        """Create a new reminder / deadline. due_date is YYYY-MM-DD."""
        user_id = _current_user_id()
        params = {"description": description, "due_date": due_date}
        reminder_id = await reminders_svc.create_reminder(user_id, description, due_date)
        await _log_audit(ledger_svc, user_id, "create_reminder", params)
        return {"reminder_id": reminder_id, "description": description, "due_date": due_date}

    @mcp.tool()
    async def post_journal_entry(
        entry_date: str,
        description: str,
        debit_account_id: str,
        credit_account_id: str,
        amount: str,
        currency: str = "LKR",
    ) -> dict[str, Any]:
        """Post a double-entry journal entry to the ledger. amount is a decimal
        string, e.g. '10000.00'."""
        from salli.domain.accounting.models import Direction

        user_id = _current_user_id()
        params = {
            "entry_date": entry_date,
            "description": description,
            "debit_account_id": debit_account_id,
            "credit_account_id": credit_account_id,
            "amount": amount,
            "currency": currency,
        }
        postings_data = [
            {
                "account_id": debit_account_id,
                "direction": Direction.DEBIT,
                "amount": Decimal(amount),
                "currency": currency,
            },
            {
                "account_id": credit_account_id,
                "direction": Direction.CREDIT,
                "amount": Decimal(amount),
                "currency": currency,
            },
        ]
        try:
            entry_id = await ledger_svc.add_entry(
                user_id, entry_date, description, "manual", postings_data
            )
        except ValueError as exc:
            return {"error": f"Could not post entry: {exc}"}
        await _log_audit(ledger_svc, user_id, "post_journal_entry", params)
        return {"entry_id": entry_id, "posted": True}

    # Registered with FastMCP via the @mcp.tool() decorator above; referenced
    # here only so static analysis sees them as used.
    _ = (
        get_trial_balance,
        get_accounts,
        get_tax_computation,
        list_tax_packs,
        explain_tax_band,
        get_financial_profile,
        get_budget_summary,
        get_payoff_plan,
        get_portfolio_summary,
        get_subscription_report,
        get_coverage_report,
        get_latest_advisor_report,
        run_wealth_advisor,
        save_document,
        read_document,
        update_document,
        list_documents,
        delete_document,
        save_memory,
        get_memory,
        list_memories,
        create_account,
        create_reminder,
        post_journal_entry,
    )
    return mcp
