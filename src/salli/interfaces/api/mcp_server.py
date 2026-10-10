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
from pydantic import AnyHttpUrl, BaseModel, Field

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


class TransactionChoice(BaseModel):
    """Where one pending transaction goes."""

    transaction_id: str
    #: An account id from get_accounts: where the money came from or went.
    account_id: str
    category: str | None = None
    need: str | None = Field(default=None, description="essential, discretionary or savings")


def _window(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


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
    insights_svc = services.insights
    parsing_svc = services.parsing
    rules_svc = services.rules
    fi_svc = services.fi

    mcp = FastMCP(
        name="Salli",
        instructions=(
            "Access to one user's Salli financial data and account: cash flow, "
            "spending, net worth over time, recurring payments, a cash forecast, "
            "budgets, debt payoff plans, portfolio, subscriptions, insurance coverage, "
            "tax position, transactions waiting for review, categorisation rules, "
            "saved documents/memories, and the Wealth Advisor. Numbers returned by "
            "read tools are authoritative and already computed by Salli: quote them, "
            "never recompute, estimate or adjust them. Tools that write "
            "(create_account, create_reminder, post_journal_entry, "
            "categorize_transactions, post_transactions, discard_transactions, "
            "create_rule, and the document/memory writers) take effect immediately: "
            "show the user what you will do and get their go-ahead first."
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
    async def get_tax_computation(year: str | None = None) -> dict[str, Any]:
        """Compute the user's income tax for a tax year (e.g. "2025/26") with their
        country's tax pack; omit the year for the latest one Salli can compute."""
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
            "country": result.pack_country,
            "year": result.pack_year,
            "pack_version": result.pack_version,
            "currency": result.currency,
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
    async def explain_tax_band(band_index: int, year: str | None = None) -> dict[str, Any]:
        """Explain a band of the user's own tax pack (rate, threshold); omit the
        year for the latest one Salli can compute."""
        pack = await tax_svc.pack(_current_user_id(), year)
        if band_index < 0 or band_index >= len(pack.bands):
            return {"error": f"Band index {band_index} out of range (0–{len(pack.bands) - 1})"}
        band = pack.bands[band_index]
        return {
            "country": pack.country,
            "year": pack.year,
            "currency": pack.currency,
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
        from salli.domain.llm import LLMError
        from salli.domain.usage import UsageLimitReached

        user_id = _current_user_id()
        try:
            return await advisor_svc.run_advisor(user_id, email=None, trigger="manual")
        except (UsageLimitReached, LLMError) as exc:
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
        currency: str = "",
    ) -> dict[str, Any]:
        """Create a new account in the chart of accounts. account_type is one of:
        asset, liability, equity, income, expense. currency is the ISO 4217 code
        the account is held in; leave it empty for the user's base currency."""
        user_id = _current_user_id()
        currency = currency or await ledger_svc.base_currency(user_id)
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
        currency: str = "",
        fx_rate: str = "",
    ) -> dict[str, Any]:
        """Post a double-entry journal entry to the ledger. amount is a decimal
        string, e.g. '10000.00'. currency is an ISO 4217 code; leave it empty
        for the user's base currency. For another currency, fx_rate is units of
        the base currency per unit (the rate the bank used); leave it empty to
        use the published rate for entry_date."""
        from salli.domain.accounting.models import Direction

        user_id = _current_user_id()
        currency = currency or await ledger_svc.base_currency(user_id)
        rate = Decimal(fx_rate) if fx_rate else None
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
                "fx_rate": rate,
            },
            {
                "account_id": credit_account_id,
                "direction": Direction.CREDIT,
                "amount": Decimal(amount),
                "currency": currency,
                "fx_rate": rate,
            },
        ]
        try:
            entry_id = await ledger_svc.add_entry(
                user_id, entry_date, description, "manual", postings_data
            )
        except (ValueError, LookupError) as exc:
            # LookupError covers FxUnavailableError: no published rate, so the
            # caller has to send fx_rate.
            return {"error": f"Could not post entry: {exc}"}
        await _log_audit(ledger_svc, user_id, "post_journal_entry", params)
        return {"entry_id": entry_id, "posted": True}

    # ── Insights and the forecast ────────────────────────────────────────────

    @mcp.tool()
    async def get_cash_flow(months: int = 12) -> dict[str, Any]:
        """Income, spending, what was left and the savings rate, month by month,
        ending with this month, in the user's base currency."""
        return await insights_svc.cash_flow(_current_user_id(), _window(months, 1, 120))

    @mcp.tool()
    async def get_spending(months: int = 3, by: str = "category") -> dict[str, Any]:
        """Where the money went over the last `months` months, largest first: by
        "category", "account" or "need", with each month's figure and its share."""
        if by not in ("category", "account", "need"):
            return {"error": "by is category, account or need"}
        return await insights_svc.spending(_current_user_id(), _window(months, 1, 120), by)  # type: ignore[arg-type]

    @mcp.tool()
    async def get_net_worth_history(months: int = 24) -> dict[str, Any]:
        """What the user owns less what they owe, at the end of each month."""
        return await insights_svc.net_worth(_current_user_id(), _window(months, 1, 600))

    @mcp.tool()
    async def get_recurring_payments() -> dict[str, Any]:
        """Payments that keep coming back (subscriptions, rent, bills) found in
        the ledger, when each is next expected, and whether a declared
        subscription already tracks it."""
        return await insights_svc.recurring(_current_user_id())

    @mcp.tool()
    async def get_cash_forecast(days: int = 60) -> dict[str, Any]:
        """Each cash account's balance from today to `days` ahead (at most 366),
        the total, its lowest point and the day it falls, and the expected
        income and payments that move it. Use it to answer "can I afford…" and
        "will I make it to payday": never estimate a future balance yourself."""
        return await insights_svc.forecast(_current_user_id(), _window(days, 1, 366))

    @mcp.tool()
    async def simulate_purchase(
        amount: str, term_months: int | None = None, annual_interest_rate: str = "0"
    ) -> dict[str, Any]:
        """What a purchase costs in months of financial freedom: paid in cash,
        and (given term_months) in installments at annual_interest_rate (a
        fraction: "0.18" is 18%). amount is a decimal string in the base currency."""
        try:
            return await fi_svc.simulate_purchase(
                _current_user_id(),
                Decimal(amount),
                term_months=term_months,
                annual_interest_rate=Decimal(annual_interest_rate),
            )
        except (ArithmeticError, ValueError) as exc:
            return {"error": f"Could not simulate that purchase: {exc}"}

    # ── Transactions waiting for review ──────────────────────────────────────

    @mcp.tool()
    async def list_pending_transactions(statement_id: str | None = None) -> dict[str, Any]:
        """Transactions imported from statements or bank connections and waiting
        for review: date, description, amount (a decimal string, always
        positive), whether money came in, the statement's own account, the
        accounts a rule or a model chose so far (empty when undecided), and
        whether it may duplicate something already booked."""
        txns = await parsing_svc.get_pending(_current_user_id(), statement_id)
        return {
            "transactions": [
                {
                    "id": t.id,
                    "statement_id": t.statement_id,
                    "date": t.raw.date,
                    "description": t.raw.description,
                    "amount": str(t.raw.amount),
                    "currency": t.raw.currency,
                    "money_in": t.raw.credit_flag,
                    "statement_account_id": t.account_id or None,
                    "debit_account_id": t.debit_account_id or None,
                    "credit_account_id": t.credit_account_id or None,
                    "category": t.category or None,
                    "need": t.need or None,
                    "decided_by_rule": bool(t.rule_id),
                    "possible_duplicate_of": t.duplicate_of or None,
                }
                for t in txns
            ]
        }

    @mcp.tool()
    async def categorize_transactions(choices: list[TransactionChoice]) -> dict[str, Any]:
        """Choose where pending transactions go (the account from get_accounts
        that the money came from or went to, and optionally a category and a
        need). The statement's own account stays the other side. Nothing is
        booked until post_transactions. Show the user your choices first."""
        user_id = _current_user_id()
        try:
            updated = await parsing_svc.categorize(
                user_id, [c.model_dump(exclude_none=True) for c in choices]
            )
        except KeyError as exc:
            return {"error": f"No pending transaction {exc}"}
        except ValueError as exc:
            return {"error": str(exc)}
        await _log_audit(ledger_svc, user_id, "categorize_transactions", {"choices": len(updated)})
        return {"updated": updated}

    @mcp.tool()
    async def post_transactions(transaction_ids: list[str]) -> dict[str, Any]:
        """Book pending transactions as journal entries, with the accounts chosen
        for them. Only after the user has approved exactly these. A transaction
        with no account chosen, or already booked, is skipped."""
        user_id = _current_user_id()
        entry_ids = await parsing_svc.post_approved(user_id, transaction_ids)
        await _log_audit(
            ledger_svc, user_id, "post_transactions", {"transaction_ids": transaction_ids}
        )
        return {"posted": len(entry_ids), "entry_ids": entry_ids}

    @mcp.tool()
    async def discard_transactions(
        statement_id: str, transaction_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """Discard pending transactions of a statement (those listed, or every
        one) that are not real: they are never booked and leave review."""
        user_id = _current_user_id()
        count = await parsing_svc.discard(user_id, statement_id, transaction_ids)
        if count is None:
            return {"error": f"No statement {statement_id}"}
        await _log_audit(
            ledger_svc,
            user_id,
            "discard_transactions",
            {"statement_id": statement_id, "transaction_ids": transaction_ids},
        )
        return {"discarded": count}

    # ── Rules ────────────────────────────────────────────────────────────────

    @mcp.tool()
    async def suggest_rules() -> dict[str, Any]:
        """Rules the user's own bookkeeping implies: payees they always book to
        the same account. Offer them; create one with create_rule if they agree."""
        return {"suggestions": await rules_svc.suggestions(_current_user_id())}

    @mcp.tool()
    async def create_rule(
        name: str,
        description_contains: str,
        account_id: str,
        category: str | None = None,
        need: str | None = None,
    ) -> dict[str, Any]:
        """Teach Salli to book every transaction whose description contains
        `description_contains` to `account_id` (with a category and need), every
        time, before any model is asked. Get the user's agreement first."""
        from salli.domain.rules.engine import InvalidRule

        user_id = _current_user_id()
        actions = {"account_id": account_id, "category": category, "need": need}
        rule = {
            "name": name,
            "conditions": [
                {"field": "description", "operator": "contains", "value": description_contains}
            ],
            "actions": {k: v for k, v in actions.items() if v},
            "priority": 100,
            "match_all": True,
            "enabled": True,
        }
        try:
            rule_id = await rules_svc.create(user_id, rule)
        except InvalidRule as exc:
            return {"error": str(exc)}
        await _log_audit(ledger_svc, user_id, "create_rule", {"name": name})
        return {"rule_id": rule_id}

    # ── Prompts: what a user can start with in their AI client ──────────────

    @mcp.prompt()
    def review_my_month(month: str = "") -> str:
        """A short review of the month: what came in and went out, what
        changed, what needs attention, and a few actions."""
        when = f"for {month}" if month else "for this month"
        return (
            f"Review my finances {when} with Salli's tools: get_cash_flow, "
            "get_spending, get_recurring_payments and get_cash_forecast. Quote Salli's "
            "numbers exactly; never compute or estimate amounts yourself. Tell me, "
            "briefly: how this month compares with my usual months, anything that "
            "needs attention (a forecast low point before payday, a new or more "
            "expensive recurring charge, a category well above usual), and at most "
            "three concrete things I could do. Keep it short and plain."
        )

    @mcp.prompt()
    def sort_pending_transactions() -> str:
        """Sort what came in from statements and banks, then book what the user approves."""
        return (
            "Help me sort my imported transactions with Salli. Call "
            "list_pending_transactions and get_accounts. For each transaction with no "
            "account chosen, propose an account from my chart (never invent one), a "
            "short category, and a need (essential, discretionary or savings). Show "
            "me your proposals grouped by account, and point out possible duplicates. "
            "Only after I approve: call categorize_transactions, then post_transactions "
            "for exactly what I approved. Then offer rules for payees that keep "
            "coming back (suggest_rules, or create_rule) so Salli books them itself "
            "next time; create a rule only if I say yes."
        )

    @mcp.prompt()
    def can_i_afford(amount: str, when: str = "", what: str = "") -> str:
        """Whether a purchase fits, from the user's own forecast and plan."""
        thing = f" for {what}" if what else ""
        date = f" on {when}" if when else " now"
        return (
            f"Can I afford {amount}{thing}{date}? Use Salli: get_cash_forecast for a "
            "window covering that date and the next payday, and simulate_purchase for "
            "what it costs my plan in months of freedom (paid at once, and in "
            "installments if that is an option). Answer with Salli's numbers only, "
            "never your own arithmetic: my lowest balance afterwards and when it "
            "falls, whether that stays above zero and above my usual buffer, and the "
            "cost in months of freedom. Say what you assumed, and the trade-off in "
            "one sentence."
        )

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
        get_cash_flow,
        get_spending,
        get_net_worth_history,
        get_recurring_payments,
        get_cash_forecast,
        simulate_purchase,
        list_pending_transactions,
        categorize_transactions,
        post_transactions,
        discard_transactions,
        suggest_rules,
        create_rule,
        review_my_month,
        sort_pending_transactions,
        can_i_afford,
    )
    return mcp
