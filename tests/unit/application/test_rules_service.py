"""Rules against a user's real accounts and history, and in quick add."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from salli.application.services.entry_parse_service import EntryParseService
from salli.application.services.rules_service import RulesService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.rules.engine import Facts, InvalidRule
from tests.fakes import FakeLLM

USER = "u1"


def _account(id_: str, type_: str, active: bool = True) -> Account:
    return Account(
        id=id_, user_id=USER, code=id_, name=id_, type=type_, currency="USD", is_active=active
    )


ACCOUNTS = {
    a.id: a
    for a in (
        _account("bank", "asset"),
        _account("food", "expense"),
        _account("transport", "expense"),
        _account("old", "expense", active=False),
    )
}


def _entry(id_: str, description: str, counter: str) -> StoredJournalEntry:
    return StoredJournalEntry(
        id=id_,
        user_id=USER,
        entry_date=f"2026-10-{int(id_[1:]):02d}",
        description=description,
        source="statement",
        postings=[
            Posting(
                account_id=counter, direction=Direction.DEBIT, amount=Decimal("12"), currency="USD"
            ),
            Posting(
                account_id="bank", direction=Direction.CREDIT, amount=Decimal("12"), currency="USD"
            ),
        ],
    )


class Rules:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.hits: dict[str, int] = {}

    async def list(self, user_id):
        return sorted(self.rows.values(), key=lambda r: (r["priority"], r["name"]))

    async def get(self, user_id, rule_id):
        return self.rows.get(rule_id)

    async def save(self, user_id, rule):
        rule_id = f"r{len(self.rows) + 1}"
        self.rows[rule_id] = {"id": rule_id, **rule}
        return rule_id

    async def update(self, user_id, rule_id, fields):
        self.rows[rule_id].update(fields)
        return True

    async def delete(self, user_id, rule_id):
        return self.rows.pop(rule_id, None) is not None

    async def record_hits(self, user_id, counts, at: datetime):
        for rule_id, n in counts.items():
            self.hits[rule_id] = self.hits.get(rule_id, 0) + n


@pytest.fixture
def world():
    rules = Rules()
    entries = [
        _entry("e1", "UBER *TRIP 8H3K2", "transport"),
        _entry("e2", "UBER *TRIP Q99XP", "transport"),
        _entry("e3", "UBER *EATS 77Q", "food"),
        _entry("e4", "STARBUCKS 4413", "food"),
    ]
    ledger = SimpleNamespace(
        get_account=AsyncMock(side_effect=lambda user_id, account_id: ACCOUNTS.get(account_id)),
        get_accounts=AsyncMock(return_value=list(ACCOUNTS.values())),
        get_entries=AsyncMock(return_value=entries),
    )

    @asynccontextmanager
    async def uow_factory():
        yield SimpleNamespace(rules=rules, ledger=ledger)

    return RulesService(uow_factory), rules


def _draft(**kw: Any) -> dict[str, Any]:
    return {
        "name": kw.pop("name", "Uber"),
        "conditions": kw.pop(
            "conditions", [{"field": "description", "operator": "contains", "value": "uber"}]
        ),
        "actions": kw.pop("actions", {"account_id": "transport"}),
        **kw,
    }


async def test_a_rule_must_point_at_an_active_account_of_yours(world):
    service, _ = world
    assert await service.create(USER, _draft())
    for account in ("nope", "old"):
        with pytest.raises(InvalidRule, match="account"):
            await service.create(USER, _draft(actions={"account_id": account}))


async def test_tags_must_be_real_tags(world):
    service, _ = world
    with pytest.raises(InvalidRule, match="slug"):
        await service.create(USER, _draft(actions={"category": "Food & Drink"}))
    with pytest.raises(InvalidRule, match="need"):
        await service.create(USER, _draft(actions={"need": "luxury"}))
    assert await service.create(
        USER, _draft(actions={"category": "eating-out", "need": "discretionary"})
    )


async def test_testing_a_rule_shows_what_it_would_decide_and_who_disagrees(world):
    service, rules = world
    result = await service.test(USER, _draft())
    assert result["total"] == 3
    assert result["agreeing"] == 2  # the Uber Eats charge was booked to food
    assert {m["entry_id"] for m in result["matches"]} == {"e1", "e2", "e3"}
    assert rules.rows == {}  # testing saves nothing


async def test_an_update_is_checked_like_a_new_rule(world):
    service, _ = world
    rule_id = await service.create(USER, _draft())
    assert await service.update(USER, rule_id, {"priority": 5})
    with pytest.raises(InvalidRule):
        await service.update(USER, rule_id, {"actions": {"account_id": "nope"}})
    assert not await service.update(USER, "missing", {"priority": 1})


async def test_deciding_records_which_rules_did_the_work(world):
    service, rules = world
    uber = await service.create(USER, _draft())
    facts = [
        Facts("UBER *TRIP X", Decimal("9"), "out", "USD"),
        Facts("LYFT", Decimal("9"), "out", "USD"),
        Facts("UBER *TRIP Y", Decimal("9"), "out", "USD"),
    ]
    decided = await service.decide(USER, facts)
    assert [r.id if r else None for r in decided] == [uber, None, uber]
    assert rules.hits == {uber: 2}


async def test_suggestions_skip_what_rules_already_decide(world):
    service, _ = world
    assert await service.suggestions(USER) == []  # 2 of 3 Uber charges agree: below 80%
    await service.create(
        USER,
        _draft(
            conditions=[{"field": "description", "operator": "contains", "value": "starbucks"}],
            actions={"account_id": "food"},
        ),
    )
    assert await service.suggestions(USER) == []


# ── quick add ─────────────────────────────────────────────────────────────────


def _quick_add(rules: RulesService | None) -> EntryParseService:
    ledger = MagicMock()
    ledger.list_accounts = AsyncMock(return_value=list(ACCOUNTS.values()))
    ledger.base_currency = AsyncMock(return_value="USD")
    llm = FakeLLM(
        json.dumps(
            {
                "entry_type": "expense",
                "amount": "12.00",
                "description": "Ride",
                "debit_account_id": "food",  # the model's (wrong) guess
                "credit_account_id": "bank",
                "debit_account_hint": None,
                "credit_account_hint": None,
                "currency": "USD",
                "confidence": 0.6,
            }
        )
    )
    credentials = MagicMock()
    credentials.resolve = AsyncMock(return_value=SimpleNamespace(llm=llm))
    return EntryParseService(ledger, credentials=credentials, rules=rules)


async def test_a_rule_beats_the_models_guess_in_quick_add(world):
    service, _ = world
    await service.create(USER, _draft(actions={"account_id": "transport", "description": "Uber"}))
    draft = await _quick_add(service).parse_draft(USER, "uber home 12")
    assert draft["debit_account_id"] == "transport"
    assert draft["description"] == "Uber"
    assert draft["rule"] == "Uber"


async def test_without_a_matching_rule_the_draft_is_the_models(world):
    service, _ = world
    draft = await _quick_add(service).parse_draft(USER, "lunch 12")
    assert draft["debit_account_id"] == "food"
    assert "rule" not in draft
