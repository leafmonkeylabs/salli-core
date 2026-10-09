"""
RulesService — the user's categorisation rules (domain/rules/engine.py):
keeping them, checking a rule against what is already booked before saving
it, learning rules from what the user has been doing by hand, and deciding
new transactions with them.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from salli.domain.rules.engine import (
    Actions,
    Condition,
    Facts,
    InvalidRule,
    Rule,
    first_match,
    matches,
    suggest,
    validate,
)
from salli.domain.rules.history import booked_transactions

NEED_TAGS = ("essential", "discretionary", "savings")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,48}$")


def rule_from_row(row: dict[str, Any]) -> Rule:
    return Rule(
        id=row.get("id", ""),
        name=row["name"],
        priority=int(row.get("priority", 100)),
        match_all=bool(row.get("match_all", True)),
        enabled=bool(row.get("enabled", True)),
        conditions=tuple(
            Condition(
                field=c["field"],
                operator=c["operator"],
                value=str(c["value"]),
                value2=None if c.get("value2") is None else str(c["value2"]),
            )
            for c in row["conditions"]
        ),
        actions=Actions(**{k: v for k, v in (row.get("actions") or {}).items() if v is not None}),
    )


def rule_to_row(rule: Rule) -> dict[str, Any]:
    return {
        "name": rule.name.strip(),
        "priority": rule.priority,
        "match_all": rule.match_all,
        "enabled": rule.enabled,
        "conditions": [
            {k: v for k, v in asdict(c).items() if v is not None} for c in rule.conditions
        ],
        "actions": {k: v for k, v in asdict(rule.actions).items() if v is not None},
    }


class RulesService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    # ── keeping them ──────────────────────────────────────────────────────────

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return await uow.rules.list(user_id)

    async def get(self, user_id: str, rule_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            return await uow.rules.get(user_id, rule_id)

    async def _check(self, uow: Any, user_id: str, rule: Rule) -> None:
        """The domain's checks, plus the ones only the user's data can answer."""
        validate(rule)
        actions = rule.actions
        if actions.account_id:
            account = await uow.ledger.get_account(user_id, actions.account_id)
            if account is None or not account.is_active:
                raise InvalidRule("The rule's account doesn't exist or isn't active")
        if actions.category and not _SLUG.match(actions.category):
            raise InvalidRule("A category is a short lowercase slug, like `groceries`")
        if actions.need and actions.need not in NEED_TAGS:
            raise InvalidRule(f"A need is one of: {', '.join(NEED_TAGS)}")

    async def create(self, user_id: str, data: dict[str, Any]) -> str:
        rule = rule_from_row(data)
        async with self._uow_factory() as uow:
            await self._check(uow, user_id, rule)
            return await uow.rules.save(user_id, rule_to_row(rule))

    async def update(self, user_id: str, rule_id: str, data: dict[str, Any]) -> bool:
        async with self._uow_factory() as uow:
            current = await uow.rules.get(user_id, rule_id)
            if current is None:
                return False
            rule = rule_from_row({**current, **{k: v for k, v in data.items() if v is not None}})
            await self._check(uow, user_id, rule)
            return await uow.rules.update(user_id, rule_id, rule_to_row(rule))

    async def delete(self, user_id: str, rule_id: str) -> bool:
        async with self._uow_factory() as uow:
            return await uow.rules.delete(user_id, rule_id)

    # ── against what is already booked ────────────────────────────────────────

    async def _history(self, uow: Any, user_id: str) -> list[Any]:
        accounts = await uow.ledger.get_accounts(user_id)
        entries = await uow.ledger.get_entries(user_id)
        return booked_transactions(entries, accounts)

    async def test(self, user_id: str, data: dict[str, Any], limit: int = 50) -> dict[str, Any]:
        """Which booked transactions a rule (saved or not) would decide.

        Each match says where the transaction went then, so a rule that would
        disagree with how the user has been booking something is visible
        before it is saved."""
        rule = rule_from_row({**data, "enabled": True})
        validate(rule)
        async with self._uow_factory() as uow:
            history = await self._history(uow, user_id)
        hits = [b for b in history if matches(rule, b.facts)]
        hits.sort(key=lambda b: b.entry.entry_date, reverse=True)
        target = rule.actions.account_id
        return {
            "total": len(hits),
            "agreeing": sum(1 for b in hits if target and b.counter_account_id == target),
            "matches": [
                {
                    "entry_id": b.entry.id,
                    "entry_date": b.entry.entry_date,
                    "description": b.facts.description,
                    "amount": str(b.facts.amount),
                    "currency": b.facts.currency,
                    "direction": b.facts.direction,
                    "account_id": b.counter_account_id,
                }
                for b in hits[:limit]
            ],
        }

    async def suggestions(self, user_id: str) -> list[dict[str, Any]]:
        """Rules the user has, in effect, been applying by hand."""
        async with self._uow_factory() as uow:
            history = await self._history(uow, user_id)
            existing = [rule_from_row(r) for r in await uow.rules.list(user_id)]
        found = suggest([(b.facts, b.counter_account_id) for b in history], existing)
        return [
            {
                **rule_to_row(Rule(id="", name=s.name, conditions=s.conditions, actions=s.actions)),
                "support": s.support,
                "agreement": s.agreement,
                "examples": list(s.examples),
            }
            for s in found
        ]

    # ── deciding new transactions ─────────────────────────────────────────────

    async def decide(self, user_id: str, facts: Sequence[Facts]) -> list[Rule | None]:
        """The rule that decides each transaction (or None), in order, and a
        hit recorded on every rule that decided one."""
        async with self._uow_factory() as uow:
            rules = [rule_from_row(r) for r in await uow.rules.list(user_id)]
            if not rules:
                return [None] * len(facts)
            decided = [first_match(rules, f) for f in facts]
            counts = Counter(r.id for r in decided if r is not None)
            if counts:
                await uow.rules.record_hits(user_id, dict(counts), datetime.now(UTC))
        return decided
