"""
LangGraph tool definitions for the Salli agent system.

Tools are grouped:
  - READ tools: trial balance, accounts, tax computation, tax packs (no approval)
  - WEB tools: Tavily web search (no approval)
  - DOCUMENT tools: save/read/list/update/delete documents and named memories (no approval)
  - WRITE tools: create account, post entry, create reminder (interrupt → user approval)

The write tools use langgraph interrupt() to pause execution and ask the user to
approve or deny the action before it executes. The agent resumes via Command(resume=...).
"""

from __future__ import annotations

import contextvars
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from langchain_core.tools import tool

# The authenticated user for the current agent run. Set per-request by AgentService
# before the graph executes, so tools always act on the signed-in user's data —
# the user_id is NEVER taken from the LLM (correctness + tenant isolation).
# No default: a run that forgot to set it raises LookupError instead of
# quietly acting on some fixed account.
_current_user: contextvars.ContextVar[str] = contextvars.ContextVar("salli_current_user")


def set_current_user(user_id: str) -> None:
    _current_user.set(user_id)


# ── Read-only tools (re-exported for worker agents) ───────────────────────────


def _make_get_accounts_tool(ledger_svc: Any) -> Any:
    """Shared `get_accounts` tool body — used by both worker agents (via
    `make_read_tools`) and the manager agent (via `make_manager_tools`), so the
    one agent that actually calls `post_journal_entry`/`create_account` can look
    up real account ids directly instead of only through sub-agent delegation."""

    @tool
    async def get_accounts() -> dict[str, Any]:
        """List all accounts in the user's chart of accounts."""
        user_id = _current_user.get()
        accounts = await ledger_svc.list_accounts(user_id)
        return {
            "accounts": [
                {"id": a.id, "code": a.code, "name": a.name, "type": a.type, "currency": a.currency}
                for a in accounts
            ]
        }

    return get_accounts


def make_read_tools(ledger_svc: Any, tax_svc: Any) -> list[Any]:
    """Return the 5 read-only tools for worker agents."""

    @tool
    async def get_trial_balance(
        from_date: Annotated[str | None, "Start date YYYY-MM-DD"] = None,
        to_date: Annotated[str | None, "End date YYYY-MM-DD"] = None,
    ) -> dict[str, Any]:
        """Return the trial balance (account balances) for the user's ledger."""
        user_id = _current_user.get()
        balances = await ledger_svc.get_trial_balance(user_id, from_date, to_date)
        return {
            "trial_balance": {k: str(v) for k, v in balances.items()},
            "net": str(sum(balances.values(), Decimal(0))),
        }

    get_accounts = _make_get_accounts_tool(ledger_svc)

    @tool
    async def get_tax_computation(
        year: Annotated[
            str | None,
            "Tax year as its pack names it, e.g. 2025/26; omit for the latest year "
            "Salli can compute for the user",
        ] = None,
    ) -> dict[str, Any]:
        """
        Compute the user's income tax for a year with their country's tax pack.
        Numbers here are authoritative; narrate them, do NOT recompute or
        adjust them.

        The band table covers taxable_income only. Foreign service income is
        taxed separately at a flat rate, so the bands will not sum to
        tax_before_credits whenever fsi_tax is non-zero. Use band_tax, fsi_tax
        and the how_* fields to explain the total rather than inferring where a
        difference came from.
        """
        user_id = _current_user.get()
        result = await tax_svc.compute_tax(user_id, year)

        def _bw(bw: Any) -> dict[str, str]:
            if isinstance(bw, dict):
                return {
                    "from": str(bw.get("from_amount", "0")),
                    "to": str(bw["to_amount"]) if bw.get("to_amount") else "∞",
                    "rate": str(bw.get("rate", "")),
                    "taxable_in_band": str(bw.get("taxable_in_band", "0")),
                    "tax": str(bw.get("tax", "0")),
                }
            return {
                "from": str(bw.from_amount),
                "to": str(bw.to_amount) if bw.to_amount else "∞",
                "rate": str(bw.rate),
                "taxable_in_band": str(bw.taxable_in_band),
                "tax": str(bw.tax),
            }

        band_tax = sum((Decimal(_bw(bw)["tax"]) for bw in result.band_workings), Decimal(0))

        return {
            "country": result.pack_country,
            "year": result.pack_year,
            "pack_version": result.pack_version,
            "currency": result.currency,
            "gross_income": str(result.gross_income),
            # Split out, because the bands only ever apply to `regular_income`.
            # Without these the band table looks like it should reconcile to
            # tax_before_credits, it does not, and the gap gets explained away
            # as something else. That happened: a reply summed the bands to
            # 9.4L against a 14.9L total and told the user "the rest comes from
            # credits", which is wrong twice over, since credits reduce a bill
            # rather than add to it.
            "regular_income": str(result.regular_income),
            "foreign_service_income": str(result.foreign_service_income),
            "personal_relief": str(result.personal_relief_applied),
            "qualifying_payment_deduction": str(result.qp_deduction),
            "taxable_income": str(result.taxable_income),
            "band_tax": str(band_tax),
            "fsi_tax": str(result.fsi_tax),
            "tax_before_credits": str(result.tax_before_credits),
            # Spelled out so the arithmetic never has to be inferred from the
            # numbers. The model narrates this computation; it does not redo it.
            "how_tax_before_credits_is_built": (
                "band_tax + fsi_tax = tax_before_credits. The band table applies "
                "to taxable_income only, which is regular_income after personal "
                "relief and qualifying payments. Foreign service income is taxed "
                "separately at a flat rate and never appears in the bands."
            ),
            "apit_credit": str(result.apit_credit),
            "ait_credit": str(result.ait_credit),
            "foreign_tax_credit": str(result.foreign_tax_credit),
            "total_credits": str(result.total_credits),
            "how_tax_payable_is_built": (
                "tax_before_credits - total_credits = tax_payable. Credits only "
                "ever reduce the bill."
            ),
            "tax_payable": str(result.tax_payable),
            "band_workings": [_bw(bw) for bw in result.band_workings],
        }

    @tool
    def list_tax_packs() -> dict[str, Any]:
        """List available tax packs (country, year, version) and the withholding
        kinds each credits."""
        packs = tax_svc.list_packs()
        return {
            "packs": [
                {
                    "country": p.country,
                    "year": p.year,
                    "version": p.version,
                    "period_start": p.period_start,
                    "period_end": p.period_end,
                    "withholding_kinds": [
                        {"code": k.code, "label": k.label, "description": k.description}
                        for k in p.withholding_kinds
                    ],
                }
                for p in packs
            ]
        }

    @tool
    async def explain_tax_band(
        band_index: Annotated[int, "0-indexed band number"],
        year: Annotated[
            str | None, "Tax year, e.g. 2025/26; omit for the latest Salli can compute"
        ] = None,
    ) -> dict[str, Any]:
        """
        Explain a specific band of the user's own tax pack (rate, threshold).
        Returns the band definition from the tax pack — do NOT invent numbers.
        """
        pack = await tax_svc.pack(_current_user.get(), year)
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

    return [get_trial_balance, get_accounts, get_tax_computation, list_tax_packs, explain_tax_band]


# ── Manager tools factory (web search + documents + write with approval) ───────


def make_manager_tools(
    doc_svc: Any,
    ledger_svc: Any,
    tax_svc: Any,
    profile_svc: Any = None,
    budget_svc: Any = None,
    debt_svc: Any = None,
    portfolio_svc: Any = None,
    subscription_svc: Any = None,
    insurance_svc: Any = None,
    advisor_svc: Any = None,
    fi_svc: Any = None,
) -> list[Any]:
    """
    Return the manager-only tools:
      - web_search (Tavily)
      - save_document, read_document, update_document, list_documents, delete_document
      - save_memory, get_memory, list_memories
      - get_financial_profile (fact-find profile: risk category, life stage, dependents)
      - get_budget_summary (category limits vs. actual spend for a budget period)
      - get_payoff_plan (avalanche/snowball debt payoff plan)
      - get_portfolio_summary (allocation, rebalancing drift, ROI)
      - get_subscription_report (missed-charge/price-change alerts for recurring subscriptions)
      - get_coverage_report (insurance coverage gap, missing types, expiring-soon policies)
      - get_latest_advisor_report (most recent Wealth Advisor report, no new LLM call)
      - run_wealth_advisor (generate a fresh Wealth Advisor report now; a fresh model run)
      - get_freedom_snapshot (FI score, Freedom number, progress, years to FI)
      - can_i_afford (costs a prospective purchase in months of freedom)
      - get_accounts (the user's chart of accounts — call before create_account/post_journal_entry)
      - create_account, create_reminder, post_journal_entry (all need user approval)
    """

    get_accounts = _make_get_accounts_tool(ledger_svc)

    # ── Web search ────────────────────────────────────────────────────────────
    try:
        from langchain_community.tools.tavily_search import TavilySearchResults

        web_search = TavilySearchResults(
            max_results=5,
            description=(
                "Search the internet for current tax laws and revenue-authority guidance "
                "(such as the circulars of the user's tax authority), "
                "exchange rates, financial news, or any other real-time information. "
                "Always cite the source URL in your response."
            ),
        )
    except Exception:
        # Tavily not configured — provide a stub so the agent still loads
        @tool
        def web_search(query: Annotated[str, "Search query"]) -> str:
            """Search the internet. (Currently unavailable — TAVILY_API_KEY not set.)"""
            return "Web search unavailable: TAVILY_API_KEY is not configured."

    # ── Document tools ────────────────────────────────────────────────────────

    @tool
    async def save_document(
        title: Annotated[str, "Document title"],
        content: Annotated[str, "Document content (plain text or markdown)"],
        tags: Annotated[list[str], "Optional list of tags for categorisation"] = [],  # noqa: B006 — never mutated; LangChain derives the tool schema from it
        description: Annotated[str | None, "Short description of the document"] = None,
    ) -> dict[str, Any]:
        """
        Save a text document to the user's document store.
        Use this to record notes, summaries, extracted data, or any information
        the user might want to retrieve later. Documents persist across sessions.
        """
        user_id = _current_user.get()
        doc_id = await doc_svc.save_document(
            user_id,
            title=title,
            content=content,
            tags=tags,
            description=description,
            source="agent_created",
            namespace="documents",
        )
        return {"doc_id": doc_id, "title": title, "saved": True}

    @tool
    async def read_document(
        doc_id: Annotated[str, "Document ID returned by save_document or list_documents"],
    ) -> dict[str, Any]:
        """Retrieve a saved document by its ID."""
        user_id = _current_user.get()
        doc = await doc_svc.get_document(user_id, doc_id)
        if not doc:
            return {"error": f"Document {doc_id} not found"}
        return doc

    @tool
    async def update_document(
        doc_id: Annotated[str, "Document ID to update"],
        title: Annotated[str | None, "New title (leave None to keep current)"] = None,
        content: Annotated[str | None, "New content (leave None to keep current)"] = None,
    ) -> dict[str, Any]:
        """Update the title or content of an existing document."""
        updates: dict[str, Any] = {}
        if title is not None:
            updates["title"] = title
        if content is not None:
            updates["content"] = content
        if not updates:
            return {"error": "No updates provided"}
        user_id = _current_user.get()
        await doc_svc.update_document(user_id, doc_id, **updates)
        return {"doc_id": doc_id, "updated": True}

    @tool
    async def list_documents(
        namespace: Annotated[str | None, "Filter by namespace: 'documents' or 'memories'"] = None,
        tags: Annotated[list[str], "Filter by tags"] = [],  # noqa: B006 — never mutated; LangChain derives the tool schema from it
        search_query: Annotated[str | None, "Full-text search over title and content"] = None,
    ) -> dict[str, Any]:
        """List saved documents. Filter by namespace, tags, or a search query."""
        user_id = _current_user.get()
        docs = await doc_svc.list_documents(
            user_id,
            tags=tags or None,
            namespace=namespace,
            search=search_query,
        )
        return {
            "count": len(docs),
            "documents": [
                {
                    "id": d["id"],
                    "title": d["title"],
                    "namespace": d["namespace"],
                    "tags": d["tags"],
                    "source": d["source"],
                    "description": d.get("description"),
                    "updated_at": d.get("updated_at"),
                }
                for d in docs
            ],
        }

    @tool
    async def delete_document(
        doc_id: Annotated[str, "Document ID to delete"],
    ) -> dict[str, Any]:
        """Permanently delete a document from the user's document store."""
        user_id = _current_user.get()
        await doc_svc.delete_document(user_id, doc_id)
        return {"doc_id": doc_id, "deleted": True}

    # ── Memory tools ──────────────────────────────────────────────────────────

    @tool
    async def save_memory(
        slug: Annotated[str, "Unique memory key, e.g. 'accountant_name', 'tax_year_goal'"],
        value: Annotated[str, "Value to store (plain text)"],
    ) -> dict[str, Any]:
        """
        Save or update a named memory. Memories persist across all sessions.
        Use slugs like 'accountant_name', 'tax_notes_2025', 'employer_name'.
        Calling save_memory with the same slug overwrites the previous value.
        """
        user_id = _current_user.get()
        doc_id = await doc_svc.save_memory(user_id, slug=slug, value=value)
        return {"slug": slug, "saved": True, "doc_id": doc_id}

    @tool
    async def get_memory(
        slug: Annotated[str, "Memory key to retrieve"],
    ) -> dict[str, Any]:
        """Retrieve a named memory by its slug key."""
        user_id = _current_user.get()
        mem = await doc_svc.get_memory(user_id, slug=slug)
        if not mem:
            return {"slug": slug, "found": False}
        return {
            "slug": slug,
            "found": True,
            "value": mem.get("content"),
            "updated_at": mem.get("updated_at"),
        }

    @tool
    async def list_memories() -> dict[str, Any]:
        """List all named memories stored for this user."""
        user_id = _current_user.get()
        mems = await doc_svc.list_memories(user_id)
        return {
            "count": len(mems),
            "memories": [
                {
                    "slug": m.get("slug"),
                    "value": m.get("content"),
                    "updated_at": m.get("updated_at"),
                }
                for m in mems
            ],
        }

    # ── Profile tool ──────────────────────────────────────────────────────────

    @tool
    async def get_financial_profile() -> dict[str, Any]:
        """
        Return the user's fact-find profile: risk category, risk score, life stage,
        dependents, employment status, and residency. Use this to tailor guidance
        (e.g. "given your conservative risk profile...") — do NOT ask the user for
        facts already available here.
        """
        if profile_svc is None:
            return {"error": "Profile service unavailable"}
        user_id = _current_user.get()
        return await profile_svc.get_profile(user_id)

    # ── Freedom (FI) tools ────────────────────────────────────────────────────

    @tool
    async def get_freedom_snapshot() -> dict[str, Any]:
        """
        Return the user's Freedom (financial independence) position: overall score
        and grade, Freedom number, investable asset base net of debt, monthly
        surplus, savings rate, emergency-fund months, and projected years to FI.

        Use this for "how am I doing?", "when can I retire?", or before discussing
        any trade-off between spending now and retiring sooner. Figures are
        engine-computed and authoritative — never recompute or estimate them.
        """
        if fi_svc is None:
            return {"error": "Freedom service unavailable"}
        user_id = _current_user.get()
        return await fi_svc.get_or_compute_score(user_id)

    @tool
    async def can_i_afford(
        amount: Annotated[str, "Purchase price as a decimal string, e.g. '450000'"],
        term_months: Annotated[
            int | None,
            "If the user is considering paying in instalments, the number of months; "
            "omit for a straight cash purchase",
        ] = None,
        annual_interest_rate: Annotated[
            str,
            "Annual interest/finance rate on the instalment plan as a DECIMAL FRACTION "
            "(0.18 for 18%, never 18). Use '0' for a genuine 0% plan.",
        ] = "0",
    ) -> dict[str, Any]:
        """
        Cost a prospective purchase in MONTHS OF FREEDOM — the delay it adds to the
        user's financial-independence date — and compare paying cash against
        instalments.

        This is Salli's core question. Use it whenever the user asks whether they
        can afford something, whether to finance it, or which way is cheaper.

        Returns, all engine-computed: the delay in months for each funding option,
        total cost and interest, the monthly payment, whether that payment exceeds
        their monthly surplus, whether the price is even coverable from liquid
        savings, and what paying cash would leave in their emergency fund.

        Reporting rules:
        - State the months of delay and the emergency-fund effect. A user can
          usually "afford" something on paper while wrecking their buffer, and that
          is the part they most need told plainly.
        - `months_delay: null` means the FI date is not reachable on current
          figures, NOT that the purchase is free. Say so.
        - If `is_stale` is true, do NOT give an affordability verdict. Tell the user
          their ledger's last entry is from `data_as_of` and ask them to bring it up
          to date first — a confident answer from an old balance sheet is worse than
          no answer.
        - Never derive your own figures from these; quote them.
        """
        if fi_svc is None:
            return {"error": "Freedom service unavailable"}
        user_id = _current_user.get()
        try:
            value = Decimal(amount)
        except (InvalidOperation, ValueError):
            return {"error": f"Could not read '{amount}' as an amount"}
        if value < 0:
            return {"error": "Purchase amount cannot be negative"}
        try:
            rate = Decimal(annual_interest_rate)
        except (InvalidOperation, ValueError):
            return {"error": f"Could not read '{annual_interest_rate}' as a rate"}
        # A model that passes 18 for 18% would overstate the finance cost ~100x.
        if not (Decimal(0) <= rate <= Decimal(1)):
            return {
                "error": (
                    f"annual_interest_rate must be a fraction between 0 and 1, got {rate}. "
                    "Use 0.18 for 18%."
                )
            }
        return await fi_svc.simulate_purchase(
            user_id, value, term_months=term_months, annual_interest_rate=rate
        )

    # ── Budget tool ───────────────────────────────────────────────────────────

    @tool
    async def get_budget_summary(
        budget_id: Annotated[
            str | None, "Budget ID; omit to use the user's most recent budget"
        ] = None,
    ) -> dict[str, Any]:
        """
        Return a budget's category limits vs. actual spend for its period — use this
        to answer "am I over budget?" or "how much have I spent on groceries?".
        Numbers here are authoritative — do NOT recompute or estimate them.
        """
        if budget_svc is None:
            return {"error": "Budget service unavailable"}
        user_id = _current_user.get()
        if budget_id is None:
            budgets = await budget_svc.list_budgets(user_id)
            if not budgets:
                return {"error": "No budgets found. Create one first."}
            budget_id = budgets[0]["id"]
        summary = await budget_svc.get_summary(user_id, budget_id)
        if summary is None:
            return {"error": f"Budget {budget_id} not found"}
        return summary

    # ── Debt tool ─────────────────────────────────────────────────────────────

    @tool
    async def get_payoff_plan(
        extra_monthly_payment: Annotated[
            str, "Extra monthly payment beyond minimums, as a decimal string, e.g. '200'"
        ] = "0",
        strategy: Annotated[
            str,
            "'avalanche' (highest APR first, minimizes interest) or 'snowball' (smallest balance first)",
        ] = "avalanche",
    ) -> dict[str, Any]:
        """
        Return an avalanche or snowball payoff plan for the user's active debts —
        months to payoff, total interest paid, and the month-by-month schedule.
        Numbers here are authoritative — do NOT recompute or estimate them.
        """
        if debt_svc is None:
            return {"error": "Debt service unavailable"}
        if strategy not in ("avalanche", "snowball"):
            return {"error": f"Unknown strategy '{strategy}'. Use 'avalanche' or 'snowball'."}
        user_id = _current_user.get()
        return await debt_svc.get_payoff_plan(user_id, Decimal(extra_monthly_payment), strategy)

    # ── Portfolio tool ────────────────────────────────────────────────────────

    @tool
    async def get_portfolio_summary(
        target_allocation: Annotated[
            str | None,
            "Optional target allocation as 'asset_class:pct,...', e.g. "
            "'equity:0.6,bond:0.3,cash:0.1'. Omit to skip rebalancing alerts.",
        ] = None,
    ) -> dict[str, Any]:
        """
        Return the user's investment allocation by asset class, total gain/ROI,
        and (if a target allocation is given) rebalancing drift alerts. Values
        come from each holding's transactions at the latest price the user
        recorded (or as the user declared them), never a live feed — they are
        only as fresh as those prices; `notes` says what is carried at cost.
        Numbers here are authoritative — do NOT recompute them.
        """
        if portfolio_svc is None:
            return {"error": "Portfolio service unavailable"}
        user_id = _current_user.get()
        parsed_target: dict[str, Decimal] | None = None
        if target_allocation:
            parsed_target = {}
            for pair in target_allocation.split(","):
                asset_class, _, pct = pair.strip().partition(":")
                if not asset_class or not pct:
                    return {
                        "error": f"Invalid target allocation entry '{pair}'. Use asset_class:pct."
                    }
                parsed_target[asset_class.strip()] = Decimal(pct.strip())
        return await portfolio_svc.get_summary(user_id, parsed_target)

    # ── Subscription tool ─────────────────────────────────────────────────────

    @tool
    async def get_subscription_report(
        subscription_id: Annotated[
            str | None, "Subscription ID; omit to get reports for all active subscriptions"
        ] = None,
    ) -> dict[str, Any]:
        """
        Return missed-charge/price-change report(s) for the user's recurring
        subscriptions — use this to answer "did Netflix charge me yet?" or "has
        any subscription gone up in price?". Numbers here are authoritative —
        do NOT recompute or estimate them.
        """
        if subscription_svc is None:
            return {"error": "Subscription service unavailable"}
        user_id = _current_user.get()
        import datetime

        today = datetime.date.today().isoformat()
        if subscription_id is None:
            return {"reports": await subscription_svc.get_all_reports(user_id, today)}
        report = await subscription_svc.get_report(user_id, subscription_id, today)
        if report is None:
            return {"error": f"Subscription {subscription_id} not found"}
        return report

    # ── Insurance tool ────────────────────────────────────────────────────────

    @tool
    async def get_coverage_report() -> dict[str, Any]:
        """
        Return the user's insurance coverage-gap report: declared target vs.
        actual coverage per policy type, policy types with no active coverage
        at all, and policies expiring within 30 days. Use this to answer "am I
        under-insured?" or "is anything about to lapse?". Numbers here are
        authoritative — do NOT recompute or estimate them.
        """
        if insurance_svc is None:
            return {"error": "Insurance service unavailable"}
        user_id = _current_user.get()
        import datetime

        today = datetime.date.today().isoformat()
        return await insurance_svc.get_report(user_id, today)

    # ── Wealth Advisor tools ──────────────────────────────────────────────────

    @tool
    async def get_latest_advisor_report() -> dict[str, Any]:
        """
        Return the user's most recent Wealth Advisor report (summary, FIRE tier
        assessment, prioritised recommendations) without generating a new one.
        Use this before run_wealth_advisor — most questions about "what has the
        advisor told me" are answered by the existing report, not a fresh run.
        """
        if advisor_svc is None:
            return {"error": "Advisor service unavailable"}
        user_id = _current_user.get()
        report = await advisor_svc.get_latest_report(user_id)
        return report or {"error": "No advisor report found yet. Run the advisor first."}

    @tool
    async def run_wealth_advisor() -> dict[str, Any]:
        """
        Generate a fresh Wealth Advisor report now — a structured, strategy-linked
        mentoring pass over the user's FI score, FIRE strategy, and goals. It is
        a fresh model run, so prefer get_latest_advisor_report unless the user
        explicitly asks for a fresh analysis or their situation has clearly
        changed since the last report.
        """
        if advisor_svc is None:
            return {"error": "Advisor service unavailable"}
        user_id = _current_user.get()
        from salli.domain.llm import LLMError
        from salli.domain.usage import UsageLimitReached

        try:
            return await advisor_svc.run_advisor(user_id, email=None, trigger="manual")
        except (UsageLimitReached, LLMError) as exc:
            return {"error": exc.message}

    # ── Write tools (require user approval via interrupt) ─────────────────────

    async def _log_audit(user_id: str, action: str, params: dict[str, Any], decision: str) -> None:
        """Record every agent-initiated write decision — approved or denied —
        to the immutable audit log. Never blocks the tool's own outcome on
        logging failure; a broken audit write must not break a legitimate action."""
        try:
            async with ledger_svc._uow_factory() as uow:
                await uow.audit_log.log(user_id, action, params, decision)
        except Exception:
            pass

    @tool
    async def create_account(
        code: Annotated[str, "Account code, e.g. '1010'"],
        name: Annotated[str, "Account name, e.g. 'Cash (BOC)'"],
        account_type: Annotated[str, "One of: asset, liability, equity, income, expense"],
        currency: Annotated[
            str, "ISO currency code the account is held in; empty for the user's base currency"
        ] = "",
    ) -> str:
        """
        Create a new account in the chart of accounts.
        This action modifies the ledger and requires user approval before execution.
        """
        from langgraph.types import interrupt

        user_id = _current_user.get()
        currency = currency or await ledger_svc.base_currency(user_id)
        params = {"code": code, "name": name, "type": account_type, "currency": currency}
        decision = interrupt(
            {
                "type": "action_approval",
                "action": "create_account",
                "description": f"Create account '{code} – {name}' (type: {account_type}, currency: {currency})",
                "params": params,
            }
        )
        await _log_audit(user_id, "create_account", params, decision)
        if decision == "approved":
            try:
                acct_id = await ledger_svc.add_account(
                    user_id,
                    code,
                    name,
                    account_type,  # type: ignore[arg-type]
                    currency=currency,
                )
            except ValueError as exc:
                return f"Could not create the account: {exc}"
            return f"Account created: {name} ({code}), id={acct_id}"
        return "Action cancelled by user."

    @tool
    async def create_reminder(
        description: Annotated[str, "Reminder description / kind"],
        due_date: Annotated[str, "Due date as YYYY-MM-DD"],
    ) -> str:
        """
        Create a new reminder / deadline.
        This action modifies app data and requires user approval before execution.
        """
        from langgraph.types import interrupt

        user_id = _current_user.get()
        params = {"description": description, "due_date": due_date}
        decision = interrupt(
            {
                "type": "action_approval",
                "action": "create_reminder",
                "description": f"Create reminder: '{description}' due {due_date}",
                "params": params,
            }
        )
        await _log_audit(user_id, "create_reminder", params, decision)
        if decision == "approved":
            from salli.application.services.reminder_service import ReminderService

            reminder_svc = ReminderService(ledger_svc._uow_factory)
            reminder_id = await reminder_svc.create_reminder(user_id, description, due_date)
            return f"Reminder created: '{description}' due {due_date}, id={reminder_id}"
        return "Action cancelled by user."

    @tool
    async def post_journal_entry(
        entry_date: Annotated[str, "Transaction date YYYY-MM-DD"],
        description: Annotated[str, "Human-readable description of the transaction"],
        debit_account_id: Annotated[str, "Account ID to debit"],
        credit_account_id: Annotated[str, "Account ID to credit"],
        amount: Annotated[str, "Amount as a decimal string, e.g. '10000.00'"],
        currency: Annotated[str, "ISO currency code; empty for the user's base currency"] = "",
    ) -> str:
        """
        Post a double-entry journal entry to the ledger.
        This action modifies financial records and requires user approval before execution.
        """
        from langgraph.types import interrupt

        user_id = _current_user.get()
        currency = currency or await ledger_svc.base_currency(user_id)
        params = {
            "entry_date": entry_date,
            "description": description,
            "debit_account_id": debit_account_id,
            "credit_account_id": credit_account_id,
            "amount": amount,
            "currency": currency,
        }
        decision = interrupt(
            {
                "type": "action_approval",
                "action": "post_journal_entry",
                "description": (
                    f"Post {currency} {amount}, Dr {debit_account_id} / Cr {credit_account_id} "
                    f"on {entry_date}: {description}"
                ),
                "params": params,
            }
        )
        await _log_audit(user_id, "post_journal_entry", params, decision)
        if decision == "approved":
            from decimal import Decimal as D

            from salli.domain.accounting.models import Direction

            postings_data = [
                {
                    "account_id": debit_account_id,
                    "direction": Direction.DEBIT,
                    "amount": D(amount),
                    "currency": currency,
                },
                {
                    "account_id": credit_account_id,
                    "direction": Direction.CREDIT,
                    "amount": D(amount),
                    "currency": currency,
                },
            ]
            try:
                entry_id = await ledger_svc.add_entry(
                    user_id, entry_date, description, "manual", postings_data
                )
            except (ValueError, LookupError) as exc:
                # LookupError covers FxUnavailableError: no rate for that
                # currency on that date, so the user has to give one.
                return f"Could not post entry: {exc}"
            return f"Journal entry posted: id={entry_id}"
        return "Action cancelled by user."

    return [
        web_search,
        save_document,
        read_document,
        update_document,
        list_documents,
        delete_document,
        save_memory,
        get_memory,
        list_memories,
        get_financial_profile,
        get_freedom_snapshot,
        can_i_afford,
        get_budget_summary,
        get_payoff_plan,
        get_portfolio_summary,
        get_subscription_report,
        get_coverage_report,
        get_latest_advisor_report,
        run_wealth_advisor,
        get_accounts,
        create_account,
        create_reminder,
        post_journal_entry,
    ]


# ── Backward-compat factory (original 5-tool signature) ───────────────────────


def make_tools(ledger_svc: Any, tax_svc: Any) -> list[Any]:
    """Legacy factory — returns read-only tools. Used by tax_agent.py."""
    return make_read_tools(ledger_svc, tax_svc)
