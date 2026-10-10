"""
Tax specialist worker agent.

Read-only access to the user's tax as Salli's engine computes it from their own
rules, each line's explanation, and ledger data. Delegated to by the manager for
detailed tax questions.
"""

from __future__ import annotations

from typing import Any

from salli.domain.agents.style import WRITING_STYLE

TAX_WORKER_PROMPT = (
    """You are an individual income tax specialist.


Your role:
- Answer questions about the user's tax: its lines (income, reliefs, bands, credits, the
  amount owed or refunded) and their deadlines
- ALWAYS call get_tax_computation first to retrieve current figures from the ledger, never ask
  the user for income or tax figures that the system already holds
- Explain a figure with explain_tax_line: what it used and the source the rules cite for it.
  Refer to lines by their label; use the expression to say how a line is built, never to
  recompute it
- Every figure comes from the user's own active tax rules, applied by Salli's engine: never
  invent numbers or bring in a rate, threshold or rule from your own knowledge. The end of
  this prompt says where the user is taxed and which rules are active. If it names none, say
  Salli can't compute their tax, and that they can add rules (and activate them themselves);
  never apply another country's rules
- Say which rules computed the figures (the rule set version) and that Salli doesn't vouch
  for the law: the rules' sources do

Return a clear, structured answer. If the user needs to file or take action,
explain the next steps concisely.

"""
    + WRITING_STYLE
)


def build_tax_worker(
    ledger_svc: Any, tax_svc: Any, *, api_key: Any, model: str | None = None, tools: Any = None
) -> Any:
    """`api_key` is what the model runs on: an Anthropic key, or a resolved
    LLMClient for any provider (see model_factory). It is required and
    keyword-only on purpose: a missed call site must raise, not fall back to
    the ANTHROPIC_API_KEY environment variable.

    `tools` lets the caller pass an already-built tool list. They are
    user-independent (they read the current user from a contextvar at call
    time), and rebuilding them dominates graph construction cost, so the
    supervisor builds them once and shares them across both workers.
    """
    from langgraph.prebuilt import create_react_agent

    from salli.domain.agents.jurisdiction import tax_specialist_section
    from salli.domain.agents.model_factory import chat_model
    from salli.domain.agents.prompting import dynamic_prompt
    from salli.domain.agents.tools import make_read_tools

    tools = make_read_tools(ledger_svc, tax_svc) if tools is None else tools
    return create_react_agent(
        model=chat_model(api_key=api_key, model=model, temperature=0, cache=True),
        tools=tools,
        name="tax_specialist",
        # The date, the user's country, tax year and the ledger totals their
        # rules take, per call: the graph is shared by every user.
        prompt=dynamic_prompt(TAX_WORKER_PROMPT, tax_specialist_section),
    )
