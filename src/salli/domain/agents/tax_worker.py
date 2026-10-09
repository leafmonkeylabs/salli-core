"""
Tax specialist worker agent.

Read-only access to tax computations, bands, and ledger data.
Delegated to by the manager for detailed tax questions.
"""

from __future__ import annotations

from typing import Any

from salli.domain.agents.style import WRITING_STYLE

TAX_WORKER_PROMPT = (
    """You are a Sri Lanka individual income tax specialist.


Your role:
- Answer questions about tax computations, bands, deductions, credits, and deadlines
- ALWAYS call get_tax_computation first to retrieve current figures from the ledger, never ask
  the user for income or tax figures that the system already holds
- Use the available tools to retrieve accurate data, never invent numbers
- Explain tax concepts clearly in relation to Sri Lanka's Inland Revenue Act
- Reference the tax pack version when quoting figures

Available assessment years: 2025/26 (April 2025 – March 2026)
Personal relief: LKR 1,800,000. Progressive bands: 6/18/24/30/36%.
Foreign service income remitted via licensed bank: 15% final tax.

Return a clear, structured answer. If the user needs to file or take action,
explain the next steps concisely.

"""
    + WRITING_STYLE
)


def build_tax_worker(
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
    dated_prompt = (
        f"{TAX_WORKER_PROMPT}\n\n"
        f"Today's date is {today}. "
        f"Current assessment year: 2025/26 (1 April 2025 – 31 March 2026)."
    )

    tools = make_read_tools(ledger_svc, tax_svc) if tools is None else tools
    return create_react_agent(
        model=chat_model(
            api_key=api_key, model=model or CONVERSATION_MODEL, temperature=0, cache=True
        ),
        tools=tools,
        name="tax_specialist",
        prompt=dated_prompt,
    )
