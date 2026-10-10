"""
Return preparation workflow — deterministic StateGraph with a human approval gate.

Nodes:
  compute      → the user's tax with their active rule set (Salli's engine, NOT
                 the LLM), stored, with each return form the rules define filled
                 in from the result
  build_draft  → the worksheet: every form's fields, its filing instructions and
                 URL, and the computation behind them
  review       → interrupt(): the user approves, edits or rejects the draft
  finalize     → the worksheet, ready to file

The LLM is NOT invoked in this graph. It is pure Python orchestration.

Forms are the rule set's (`forms` in docs/taxrules.md): Salli knows no
country's return. A rule set without forms has no return to prepare; its
computation is still stored. Every figure on the worksheet is a form field's
value as the engine computed it: nobody edits a figure. "edit" means the
inputs change: the user may fix their ledger, or send new answers to the
rules' questions, and the workflow computes again and comes back to review.

The year, jurisdiction and answers are the user's: as asked, or derived as
TaxService.resolve derives them, and kept on the thread so a recomputation
after an edit is for the same return. The same interrupt gate is where filing
on the user's behalf would go, if an authority ever offers a channel for it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from salli.domain.secrets import error_label

DECISIONS = ("approve", "edit", "reject")

_NOTE = (
    "A worksheet Salli prepared from your own tax rules and ledger. Salli doesn't vouch "
    "for the law: check every figure, and the rules' sources, before you file. This is not "
    "tax advice."
)


@dataclass
class ReturnState:
    user_id: str = ""
    # As asked; "" for derived. Filled in by compute with what was used.
    country: str = ""
    region: str = ""
    year: str = ""
    # Answers to the rules' questions, by key.
    answers: dict[str, Any] = field(default_factory=dict)

    # Populated by compute
    computation: dict[str, Any] = field(default_factory=dict)
    forms: list[dict[str, Any]] = field(default_factory=list)

    # Populated by build_draft
    draft_return: dict[str, Any] = field(default_factory=dict)

    # Set by the review node
    review_decision: str = ""  # "approve" | "edit" | "reject"

    # Final output
    worksheet: dict[str, Any] = field(default_factory=dict)
    error: str = ""


# ── Nodes ──────────────────────────────────────────────────────────────────────


async def _compute(state: ReturnState, tax_svc: Any) -> dict[str, Any]:
    try:
        prepared = await tax_svc.prepare_return(
            state.user_id,
            country=state.country or None,
            region=state.region or None,
            year=state.year or None,
            answers=state.answers,
        )
    except Exception as e:  # noqa: BLE001 — anything else is unexpected: keep only its class
        return {"error": error_label(e)}
    if prepared.get("error"):
        return {"error": prepared["error"], "computation": prepared.get("computation") or {}}
    return {
        "error": "",
        "country": prepared["country"],
        "region": prepared["region"] or "",
        "year": prepared["year"],
        "computation": prepared["computation"],
        "forms": prepared["forms"],
    }


def _build_draft(state: ReturnState) -> dict[str, Any]:
    c = state.computation
    draft = {
        "country": c["country"],
        "region": c["region"],
        "year": c["year"],
        "currency": c["currency"],
        "computation_id": c["id"],
        "rule_set_id": c["rule_set_id"],
        "rule_set_version_id": c["rule_set_version_id"],
        "version": c["version"],
        "content_hash": c["content_hash"],
        "net": c["net"],
        "tax_payable": c["tax_payable"],
        "refund_due": c["refund_due"],
        "lines": c["lines"],
        "answers": c.get("answers") or {},
        "forms": state.forms,
        "warnings": c.get("warnings") or [],
        "note": _NOTE,
        "provenance": c.get("provenance", ""),
    }
    return {"draft_return": draft}


def _review(state: ReturnState) -> dict[str, Any]:
    """
    Human-in-the-loop gate. The graph pauses before this node; the caller
    shows the draft and resumes with Command(resume=...): a decision, or
    {"decision": "edit", "answers": {...}} to compute again with new answers.
    """
    resumed = interrupt(
        {
            "draft_return": state.draft_return,
            "message": "Review the draft return: approve it, edit (new answers, or after "
            "fixing your ledger: Salli computes again), or reject it.",
            "allowed_decisions": list(DECISIONS),
        }
    )
    answers: dict[str, Any] | None = None
    if isinstance(resumed, dict):
        decision = str(resumed.get("decision", ""))
        given = resumed.get("answers")
        answers = dict(given) if isinstance(given, dict) else None
    else:
        decision = str(resumed)
    out: dict[str, Any] = {"review_decision": decision}
    if decision == "edit" and answers is not None:
        out["answers"] = {**state.answers, **answers}
    return out


def _finalize(state: ReturnState) -> dict[str, Any]:
    if state.review_decision != "approve":
        return {
            "worksheet": {},
            "error": f"Return not approved (decision: {state.review_decision})",
        }
    return {"worksheet": {**state.draft_return, "status": "ready_to_file"}}


def _after_compute(state: ReturnState) -> str:
    return "error" if state.error else "build_draft"


def _after_review(state: ReturnState) -> str:
    return "compute" if state.review_decision == "edit" else "finalize"


# ── Graph construction ─────────────────────────────────────────────────────────


def build_return_workflow(ledger_svc: Any, tax_svc: Any, checkpointer: Any = None) -> Any:
    """
    Build and compile the return preparation StateGraph.

    The returned compiled graph is invoked with:
        await workflow.ainvoke(
            {"user_id": user_id, "year": year, "country": "", "region": "", "answers": {}},
            config={"configurable": {"thread_id": thread_id}},
        )
    And resumed (after the review interrupt) with:
        from langgraph.types import Command
        await workflow.ainvoke(
            Command(resume="approve"),  # or {"decision": "edit", "answers": {...}}
            config={"configurable": {"thread_id": thread_id}},
        )
    `ledger_svc` is unused (the computation reads the ledger) and kept for the
    builders' common signature.
    """
    from langgraph.checkpoint.memory import MemorySaver

    if checkpointer is None:
        checkpointer = MemorySaver()

    async def compute(state: ReturnState) -> dict[str, Any]:
        return await _compute(state, tax_svc)

    g = StateGraph(ReturnState)
    g.add_node("compute", compute)
    g.add_node("build_draft", _build_draft)
    g.add_node("review", _review)
    g.add_node("finalize", _finalize)

    g.add_edge(START, "compute")
    g.add_conditional_edges("compute", _after_compute, {"build_draft": "build_draft", "error": END})
    g.add_edge("build_draft", "review")
    g.add_conditional_edges("review", _after_review, {"compute": "compute", "finalize": "finalize"})
    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer, interrupt_before=["review"])
