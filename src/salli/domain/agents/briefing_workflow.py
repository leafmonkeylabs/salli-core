"""
Monthly financial-health briefing workflow. A StateGraph with a human review gate.

Nodes:
  gather    → metered deterministic gather (AdvisorService.gather_context)
  narrate   → the one LLM call (advisor.generate_advice)
  review    → interrupt(): human approves, edits, or rejects the draft briefing
  finalize  → persist the approved briefing as an advisory report

Unlike return_workflow.py, the LLM IS invoked here (in narrate). That is the
whole point of a briefing. The review gate sits after narrate and before
finalize/persist, mirroring return_workflow's gather→compute→review→finalize
shape but with narrate standing in for compute as the one step that produces
the thing a human reviews.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from salli.domain.secrets import error_label

# ── State ──────────────────────────────────────────────────────────────────────


@dataclass
class BriefingState:
    user_id: str = ""
    email: str | None = None

    # Populated by gather
    context: dict[str, Any] = field(default_factory=dict)

    # Populated by narrate: an Advice model (see domain/agents/advisor.py)
    advice: Any = None

    # Set by review node
    review_decision: str = ""  # "approve" | "edit" | "reject"

    # Final output
    report: dict[str, Any] = field(default_factory=dict)
    error: str = ""


# ── Nodes ──────────────────────────────────────────────────────────────────────


async def _gather(state: BriefingState, advisor_svc: Any) -> dict[str, Any]:
    try:
        context = await advisor_svc.gather_context(state.user_id, state.email)
    except Exception as e:
        return {"error": error_label(e)}
    return {"context": context}


async def _narrate(state: BriefingState, advisor_svc: Any) -> dict[str, Any]:
    from salli.domain.agents import advisor as advisor_llm

    try:
        # The user's own model, on whichever provider they use: resolved here,
        # per run, exactly as a manual advisor run resolves it.
        llm = await advisor_svc.llm_for(state.user_id)
        advice = await advisor_llm.generate_advice(state.context, llm=llm)
    except Exception as e:
        # generate_advice calls the provider, so `e` can be an SDK error whose
        # message embeds the rejected API key, see error_label.
        return {"error": error_label(e)}
    return {"advice": advice}


def _review(state: BriefingState) -> dict[str, Any]:
    """
    Human-in-the-loop gate. The graph pauses here and surfaces the briefing to
    the user before it's persisted. In Phase 1 (CLI), the caller reads the
    interrupt payload and resumes with a Command. In Phase 2 (FastAPI), the SSE
    stream surfaces the __interrupt__ event to the client.
    """
    advice = state.advice
    decision = interrupt(
        {
            "summary": advice.summary if advice else "",
            "fire_tier_assessment": advice.fire_tier_assessment if advice else "",
            "recommendations": [r.model_dump() for r in advice.recommendations] if advice else [],
            "message": "Please review this month's financial-health briefing. "
            "Reply with 'approve', 'edit', or 'reject'.",
            "allowed_decisions": ["approve", "edit", "reject"],
        }
    )
    return {"review_decision": decision}


async def _finalize(state: BriefingState, advisor_svc: Any) -> dict[str, Any]:
    if state.review_decision != "approve":
        return {
            "report": {},
            "error": f"Briefing not approved (decision: {state.review_decision})",
        }
    report = await advisor_svc.persist_report(state.user_id, "scheduled", state.advice)
    return {"report": report}


def _should_narrate(state: BriefingState) -> str:
    return "error" if state.error else "narrate"


def _should_review(state: BriefingState) -> str:
    return "error" if state.error else "review"


# ── Graph construction ─────────────────────────────────────────────────────────


def build_briefing_workflow(advisor_svc: Any, checkpointer: Any = None) -> Any:
    """
    Build and compile the monthly briefing StateGraph.

    The returned compiled graph is invoked with:
        await workflow.ainvoke(
            {"user_id": user_id, "email": email},
            config={"configurable": {"thread_id": thread_id}},
        )
    And resumed (after review interrupt) with:
        from langgraph.types import Command
        await workflow.ainvoke(
            Command(resume="approve"),
            config={"configurable": {"thread_id": thread_id}},
        )
    """
    from langgraph.checkpoint.memory import MemorySaver

    if checkpointer is None:
        checkpointer = MemorySaver()

    # Bind services into closures
    async def gather(state: BriefingState) -> dict[str, Any]:
        return await _gather(state, advisor_svc)

    async def narrate(state: BriefingState) -> dict[str, Any]:
        return await _narrate(state, advisor_svc)

    def review(state: BriefingState) -> dict[str, Any]:
        return _review(state)

    async def finalize(state: BriefingState) -> dict[str, Any]:
        return await _finalize(state, advisor_svc)

    g = StateGraph(BriefingState)
    g.add_node("gather", gather)
    g.add_node("narrate", narrate)
    g.add_node("review", review)
    g.add_node("finalize", finalize)

    g.add_edge(START, "gather")
    g.add_conditional_edges("gather", _should_narrate, {"narrate": "narrate", "error": END})
    g.add_conditional_edges("narrate", _should_review, {"review": "review", "error": END})
    g.add_edge("review", "finalize")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer, interrupt_before=["review"])
