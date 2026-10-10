"""Categorisation rules: deterministic, first match wins, learned from what you did."""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.rules.engine import (
    Actions,
    Condition,
    Facts,
    InvalidRule,
    Rule,
    first_match,
    matches,
    payee_key,
    suggest,
    validate,
)
from salli.domain.rules.history import booked_transactions

COFFEE = Facts("POS 1234 STARBUCKS #881 COLOMBO", Decimal("4.50"), "out", "USD")
SALARY = Facts("ACME CORP PAYROLL OCT", Decimal("5000"), "in", "USD")


def _rule(*conditions: Condition, priority: int = 100, **kw) -> Rule:
    return Rule(
        id=kw.pop("id", "r"),
        name=kw.pop("name", "rule"),
        conditions=conditions,
        actions=kw.pop("actions", Actions(account_id="food")),
        priority=priority,
        **kw,
    )


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        (Condition("description", "contains", "starbucks"), True),
        (Condition("description", "contains", "STARBUCKS   #881"), True),  # case, spacing
        (Condition("description", "not_contains", "uber"), True),
        (Condition("description", "starts_with", "pos"), True),
        (Condition("description", "ends_with", "colombo"), True),
        (Condition("description", "equals", "starbucks"), False),
        (Condition("description", "matches", r"star\w+ #\d+"), True),
        (Condition("amount", "lt", "5"), True),
        (Condition("amount", "gte", "4.50"), True),
        (Condition("amount", "gt", "4.50"), False),
        (Condition("amount", "between", "4", "5"), True),
        (Condition("amount", "equals", "4.5"), True),
        (Condition("direction", "equals", "out"), True),
        (Condition("direction", "equals", "in"), False),
        (Condition("currency", "equals", "usd"), True),
    ],
)
def test_each_condition(condition, expected):
    assert matches(_rule(condition), COFFEE) is expected


def test_all_or_any():
    yes, no = Condition("description", "contains", "starbucks"), Condition("amount", "gt", "100")
    assert not matches(_rule(yes, no), COFFEE)
    assert matches(_rule(yes, no, match_all=False), COFFEE)


def test_the_first_enabled_rule_by_priority_decides():
    broad = _rule(Condition("direction", "equals", "out"), id="broad", priority=200)
    specific = _rule(Condition("description", "contains", "starbucks"), id="specific", priority=10)
    off = _rule(Condition("description", "contains", "pos"), id="off", priority=1, enabled=False)
    assert first_match([broad, specific, off], COFFEE).id == "specific"
    assert first_match([broad, specific, off], SALARY) is None


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        (_rule(name=" "), "name"),
        (_rule(Condition("description", "contains", "x"), actions=Actions()), "do something"),
        (_rule(), "at least one condition"),
        (_rule(Condition("description", "gt", "x")), "can't be compared"),
        (_rule(Condition("amount", "contains", "1")), "can't be compared"),
        (_rule(Condition("amount", "lt", "a lot")), "not an amount"),
        (_rule(Condition("amount", "between", "50", "10")), "smaller amount first"),
        (_rule(Condition("amount", "between", "10")), "two amounts"),
        (_rule(Condition("description", "matches", "(unclosed")), "valid pattern"),
        (_rule(Condition("description", "matches", "a" * 201)), "limited"),
        (_rule(Condition("direction", "equals", "sideways")), "Direction"),
        (_rule(Condition("currency", "equals", "XYZ")), "ISO 4217"),
    ],
)
def test_a_rule_that_cannot_be_evaluated_is_refused(rule, message):
    with pytest.raises((InvalidRule, ValueError), match=message):
        validate(rule)


def test_payees_ignore_references_that_change_between_charges():
    assert payee_key("POS 1234 STARBUCKS #881 COLOMBO 03") == "pos starbucks colombo"
    assert payee_key("UBER *TRIP 8H3K2") == payee_key("UBER *TRIP Q99XP") == "uber trip"


def _history(pairs):
    return [(Facts(d, Decimal("10"), direction, "USD"), account) for d, direction, account in pairs]


def test_suggestions_come_from_payees_booked_the_same_way():
    history = _history(
        [
            ("POS 1234 STARBUCKS #881 COLOMBO", "out", "coffee"),
            ("POS 9921 STARBUCKS #12 COLOMBO", "out", "coffee"),
            ("STARBUCKS 4413 KANDY", "out", "coffee"),
            ("UBER *TRIP 8H3K2", "out", "transport"),
            ("UBER *EATS 77Q", "out", "transport"),
            ("UBER *TRIP Q99XP", "out", "transport"),
            ("AMAZON MKTP", "out", "shopping"),
            ("AMAZON PRIME", "out", "subscriptions"),
            ("AMAZON MKTP 2", "out", "shopping"),  # only 2 of 3 agree: not suggested
            ("ACME PAYROLL", "in", "salary"),  # only one: not suggested
        ]
    )
    found = {s.name: s for s in suggest(history, [])}
    assert set(found) == {"Starbucks", "Uber"}
    starbucks = found["Starbucks"]
    assert (starbucks.support, starbucks.agreement, starbucks.actions.account_id) == (
        3,
        3,
        "coffee",
    )
    assert starbucks.conditions == (
        Condition("description", "contains", "starbucks"),
        Condition("direction", "equals", "out"),
    )
    # Every suggestion matches the transactions it was learned from.
    for s in found.values():
        rule = _rule(*s.conditions, actions=s.actions)
        assert all(matches(rule, Facts(e, Decimal("10"), "out", "USD")) for e in s.examples)


def test_a_payee_a_rule_already_decides_is_not_suggested_again():
    history = _history([(f"UBER *TRIP {i}X", "out", "transport") for i in range(3)])
    existing = [_rule(Condition("description", "contains", "uber"), actions=Actions(category="x"))]
    assert suggest(history, existing) == []


# ── reading booked entries ─────────────────────────────────────────────────────


def _account(id_: str, type_: str) -> Account:
    return Account(id=id_, user_id="u", code=id_, name=id_, type=type_, currency="USD")


def _entry(id_, description, debit, credit, amount="10", **kw) -> StoredJournalEntry:
    return StoredJournalEntry(
        id=id_,
        user_id="u",
        entry_date="2026-10-01",
        description=description,
        source=kw.pop("source", "statement"),
        postings=[
            Posting(
                account_id=debit, direction=Direction.DEBIT, amount=Decimal(amount), currency="USD"
            ),
            Posting(
                account_id=credit,
                direction=Direction.CREDIT,
                amount=Decimal(amount),
                currency="USD",
            ),
        ],
        **kw,
    )


def test_entries_are_read_as_money_in_or_out_of_an_account():
    accounts = [
        _account("bank", "asset"),
        _account("food", "expense"),
        _account("salary", "income"),
        _account("savings", "asset"),
    ]
    entries = [
        _entry("e1", "STARBUCKS", "food", "bank"),
        _entry("e2", "PAYROLL", "bank", "salary", amount="5000"),
        _entry("e3", "TO SAVINGS", "savings", "bank"),
        _entry("e4", "REVERSAL: STARBUCKS", "bank", "food"),
        _entry("e5", "STARBUCKS", "food", "bank", reversed_by="e4"),
        _entry("e6", "SYSTEM THING", "food", "bank", source="system"),
    ]
    booked = {b.entry.id: b for b in booked_transactions(entries, accounts)}
    assert set(booked) == {"e1", "e2", "e3"}
    assert (booked["e1"].facts.direction, booked["e1"].counter_account_id) == ("out", "food")
    assert (booked["e2"].facts.direction, booked["e2"].counter_account_id) == ("in", "salary")
    # A transfer between two of your accounts: the one the money left is the money side.
    assert (booked["e3"].money_account_id, booked["e3"].counter_account_id) == ("bank", "savings")
