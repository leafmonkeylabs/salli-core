"""
What is experimental (docs/scope.md): engines no pilot user has yet relied
on. They work and are tested; the API marks their operations
`x-experimental: true` and tags them `experimental`, and SALLI_EXPERIMENTAL
=false takes their MCP tools and prompts out of an agent's list. Nothing
here changes what they compute.
"""

from __future__ import annotations

from typing import Any

#: Insurance needs, the investment policy (drift, look-through, tax-aware
#: sales), Monte Carlo odds with guardrails, and the decision lab.
OPERATIONS = frozenset(
    {
        "insurance.needs",
        "insurance.targets.list",
        "insurance.targets.set",
        "insurance.targets.delete",
        "ips.get",
        "ips.adopt",
        "ips.versions",
        "ips.drift",
        "ips.riskProfile",
        "fi.odds",
        "scenarios.run",
        "scenarios.compare",
        "scenarios.odds",
        "principles.list",
        "principles.create",
        "principles.figures",
        "principles.check",
        "principles.update",
        "principles.archive",
        "decisions.templates.list",
        "decisions.templates.get",
        "decisions.start",
        "decisions.list",
        "decisions.record",
        "decisions.reviews.due",
        "decisions.export",
        "decisions.exportMarkdown",
        "decisions.get",
        "decisions.markdown",
        "decisions.notes.add",
        "decisions.review",
    }
)

#: The same engines' MCP tools and prompts.
MCP_TOOLS = frozenset(
    {
        "get_investment_policy",
        "get_fi_odds",
        "get_scenario_schema",
        "list_decision_templates",
        "start_decision",
        "run_scenario",
        "compare_options",
        "list_principles",
        "add_principle",
        "check_principles",
        "record_decision",
        "list_decisions",
        "get_decision",
        "list_due_reviews",
        "review_decision",
    }
)
MCP_PROMPTS = frozenset({"think_through_decision", "can_i_afford"})

TAG = {
    "name": "experimental",
    "description": "Working and tested, but no pilot has relied on it yet: its shape "
    "may change (docs/scope.md). Also marked `x-experimental: true`.",
}


def mark(document: dict[str, Any]) -> dict[str, Any]:
    """Mark the experimental operations in an OpenAPI document."""
    for item in document.get("paths", {}).values():
        for operation in item.values():
            if isinstance(operation, dict) and operation.get("operationId") in OPERATIONS:
                operation["x-experimental"] = True
                operation["tags"] = [*operation.get("tags", []), TAG["name"]]
    document["tags"] = [*document.get("tags", []), TAG]
    return document
