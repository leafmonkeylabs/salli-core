"""
Filing reminders from a rule set's `deadlines` (docs/taxrules.md).

A user's filing calendar is whatever their active rule sets say it is: each
deadline of an active version becomes a reminder, keyed by the rule set and
the deadline's key (`source_domain` "tax_rules", `source_id`
"<rule set id>:<deadline key>"). Activating a version replaces the reminders
the version it supersedes made: a deadline the new version keeps stays (still
done, if it was done and its date hasn't moved), a moved one is updated, a new
one added and a dropped one removed. Reminders the user made themselves are
never touched.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from salli.domain.taxrules.schema import RuleSet

#: `reminders.source_domain` of a reminder made from a rule set's deadline.
TAX_DEADLINE_SOURCE = "tax_rules"


def _name(rule_set: Mapping[str, Any]) -> str:
    return str(rule_set.get("name") or f"{rule_set['country']} {rule_set['year_label']}")


def deadline_items(
    rule_set: Mapping[str, Any], content: Mapping[str, Any]
) -> list[tuple[str, str, str]]:
    """(source_id, kind, due_date) for each deadline the document lists."""
    doc = RuleSet.model_validate(content)
    return [
        (f"{rule_set['id']}:{d.key}", f"{d.label} ({_name(rule_set)})", d.date.isoformat())
        for d in doc.deadlines
    ]


async def sync_deadlines(
    uow: Any, user_id: str, rule_set: Mapping[str, Any], content: Mapping[str, Any] | None
) -> dict[str, list[str]]:
    """Make the rule set's reminders the deadlines of `content` (its active
    version's document; None for none, which removes them). Inside the
    caller's unit of work."""
    items = deadline_items(rule_set, content) if content is not None else []
    return await uow.reminders.sync_source(
        user_id, TAX_DEADLINE_SOURCE, f"{rule_set['id']}:", items
    )
