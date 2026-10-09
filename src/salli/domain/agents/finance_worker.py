"""
Finance specialist worker agent.

Read-only access to the ledger: accounts, entries, trial balance, income statement.
Delegated to by the manager for detailed finance/bookkeeping questions.
"""

from __future__ import annotations

from typing import Any

from salli.domain.agents.style import WRITING_STYLE

FINANCE_WORKER_PROMPT = (
    """You are a personal finance and bookkeeping specialist.


Your role:
- Answer questions about the user's ledger: account balances, journal entries,
  income statements, and spending patterns
- Use the available tools to retrieve accurate data, never invent figures
- Explain double-entry bookkeeping concepts where relevant
- Flag anything that looks like a discrepancy (trial balance not zero, etc.)

Currency: LKR by default. Foreign currency accounts are tracked with FX rates.
Always quote amounts with the currency code.

Return clear, concise answers. If the user needs to take action (e.g. post an
entry), explain what information you would need.

"""
    + WRITING_STYLE
)


def build_finance_worker(
    ledger_svc: Any, tax_svc: Any, *, api_key: Any, model: str | None = None, tools: Any = None
) -> Any:
    """`api_key` is required and keyword-only on purpose: a missed call site
    must raise, not fall back to the ANTHROPIC_API_KEY environment variable.

    `tools` lets the caller pass an already-built tool list. They are
    user-independent (they read the current user from a contextvar at call
    time), and rebuilding them dominates graph construction cost, so the
    supervisor builds them once and shares them across both workers.
    """
    import datetime

    from langgraph.prebuilt import create_react_agent

    from salli.domain.agents.model_factory import CONVERSATION_MODEL, chat_model
    from salli.domain.agents.tools import make_read_tools

    today = datetime.date.today().strftime("%A, %d %B %Y")
    dated_prompt = f"{FINANCE_WORKER_PROMPT}\n\nToday's date is {today}."

    tools = make_read_tools(ledger_svc, tax_svc) if tools is None else tools
    return create_react_agent(
        model=chat_model(
            api_key=api_key, model=model or CONVERSATION_MODEL, temperature=0, cache=True
        ),
        tools=tools,
        name="finance_specialist",
        prompt=dated_prompt,
    )
