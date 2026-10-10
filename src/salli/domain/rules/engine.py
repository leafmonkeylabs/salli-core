"""
Categorisation rules: deterministic "when a transaction looks like this, it
goes there" — the part of bookkeeping that should never need a model.

A rule is a list of conditions on a transaction's facts (its description,
amount, direction and currency) and what to do when they hold: which account
the other side of the entry goes to, which category and need tags it gets,
and a clean description to replace the bank's. Rules are applied before any
LLM classification, so a transaction a rule recognises is booked the same way
every time, and only the rest cost a model call.

Rules are checked in priority order (lowest number first) and the first that
matches wins. Pure: no I/O.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Literal

from salli.domain.currency import normalize_currency

Field = Literal["description", "amount", "direction", "currency"]
Operator = Literal[
    "contains",
    "not_contains",
    "equals",
    "starts_with",
    "ends_with",
    "matches",
    "gt",
    "gte",
    "lt",
    "lte",
    "between",
]
Direction = Literal["in", "out"]

TEXT_OPERATORS = frozenset(
    {"contains", "not_contains", "equals", "starts_with", "ends_with", "matches"}
)
NUMBER_OPERATORS = frozenset({"equals", "gt", "gte", "lt", "lte", "between"})
#: A rule's pattern is run against every imported transaction; a bound on its
#: size keeps a pathological one from doing much damage.
MAX_PATTERN_LENGTH = 200


class InvalidRule(ValueError):
    """A rule that cannot be evaluated: a bad operator, amount, pattern, …"""


@dataclass(frozen=True)
class Condition:
    field: Field
    operator: Operator
    value: str
    #: The upper bound, for `between`.
    value2: str | None = None


@dataclass(frozen=True)
class Actions:
    #: The account the other side of the entry goes to (the expense, the
    #: income, the account a transfer goes to).
    account_id: str | None = None
    category: str | None = None
    need: str | None = None
    #: Replaces the bank's description ("AMZN MKTP US*2K4…" → "Amazon").
    description: str | None = None

    def is_empty(self) -> bool:
        return not (self.account_id or self.category or self.need or self.description)


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    conditions: tuple[Condition, ...]
    actions: Actions
    priority: int = 100
    #: All conditions must hold (AND), or any one of them (OR).
    match_all: bool = True
    enabled: bool = True


@dataclass(frozen=True)
class Facts:
    """What a rule can look at. `amount` is always positive; the sign is
    `direction`: money "in" to the account the statement is for, or "out"."""

    description: str
    amount: Decimal
    direction: Direction
    currency: str


@dataclass(frozen=True)
class Suggestion:
    """A rule the user has, in effect, been applying by hand."""

    name: str
    conditions: tuple[Condition, ...]
    actions: Actions
    #: How many past transactions it would have matched, and how many of
    #: those went to the suggested account.
    support: int
    agreement: int
    examples: tuple[str, ...] = field(default_factory=tuple)


# ── evaluating ────────────────────────────────────────────────────────────────


def _text(value: str) -> str:
    return " ".join(value.casefold().split())


def _number(value: str) -> Decimal:
    try:
        number = Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise InvalidRule(f"{value!r} is not an amount") from None
    if not number.is_finite():
        raise InvalidRule(f"{value!r} is not an amount")
    return number


def validate(rule: Rule) -> None:
    """Raise InvalidRule for anything that could not be evaluated."""
    if not rule.name.strip():
        raise InvalidRule("A rule needs a name")
    if not rule.conditions:
        raise InvalidRule("A rule needs at least one condition")
    if rule.actions.is_empty():
        raise InvalidRule("A rule needs to do something: set an account, a tag, or a description")
    for c in rule.conditions:
        if c.field == "description":
            if c.operator not in TEXT_OPERATORS:
                raise InvalidRule(f"A description can't be compared with {c.operator!r}")
            if not c.value.strip():
                raise InvalidRule("A description condition needs some text")
            if c.operator == "matches":
                if len(c.value) > MAX_PATTERN_LENGTH:
                    raise InvalidRule(f"Patterns are limited to {MAX_PATTERN_LENGTH} characters")
                try:
                    re.compile(c.value)
                except re.error as exc:
                    raise InvalidRule(f"Not a valid pattern: {exc}") from None
        elif c.field == "amount":
            if c.operator not in NUMBER_OPERATORS:
                raise InvalidRule(f"An amount can't be compared with {c.operator!r}")
            low = _number(c.value)
            if c.operator == "between":
                if c.value2 is None:
                    raise InvalidRule("`between` needs two amounts")
                if _number(c.value2) < low:
                    raise InvalidRule("`between` needs the smaller amount first")
        elif c.field == "direction":
            if c.operator != "equals" or c.value not in ("in", "out"):
                raise InvalidRule('Direction is `equals` "in" or "out"')
        elif c.field == "currency":
            if c.operator != "equals":
                raise InvalidRule("Currency is compared with `equals`")
            normalize_currency(c.value)
        else:  # pragma: no cover - Literal keeps this unreachable from typed callers
            raise InvalidRule(f"Unknown field {c.field!r}")


def _holds(c: Condition, facts: Facts) -> bool:
    if c.field == "description":
        text, want = _text(facts.description), _text(c.value)
        if c.operator == "contains":
            return want in text
        if c.operator == "not_contains":
            return want not in text
        if c.operator == "equals":
            return text == want
        if c.operator == "starts_with":
            return text.startswith(want)
        if c.operator == "ends_with":
            return text.endswith(want)
        return re.search(c.value, facts.description, re.IGNORECASE) is not None
    if c.field == "amount":
        amount, value = facts.amount, _number(c.value)
        if c.operator == "equals":
            return amount == value
        if c.operator == "gt":
            return amount > value
        if c.operator == "gte":
            return amount >= value
        if c.operator == "lt":
            return amount < value
        if c.operator == "lte":
            return amount <= value
        return value <= amount <= _number(c.value2 or c.value)
    if c.field == "direction":
        return facts.direction == c.value
    return facts.currency.upper() == c.value.upper()


def matches(rule: Rule, facts: Facts) -> bool:
    results = (_holds(c, facts) for c in rule.conditions)
    return all(results) if rule.match_all else any(results)


def first_match(rules: Iterable[Rule], facts: Facts) -> Rule | None:
    """The rule that decides this transaction: the first enabled one, by
    priority then name, whose conditions hold."""
    for rule in sorted(rules, key=lambda r: (r.priority, r.name.casefold(), r.id)):
        if rule.enabled and matches(rule, facts):
            return rule
    return None


# ── learning from what the user already did ───────────────────────────────────

# Splits a bank description into words. Anything with a digit in it is a
# reference, a card number, a date or an amount, which differ between two
# charges from the same payee ("UBER *TRIP 8H3K2", "UBER *TRIP Q99XP").
_SPLIT = re.compile(r"[\s*_/\\|,;:()\[\]{}<>\"`~!?=+#@]+")

#: Words every bank puts in front of half its descriptions: useless for
#: telling one payee from another.
_GENERIC = frozenset(
    [
        "pos",
        "card",
        "purchase",
        "payment",
        "debit",
        "credit",
        "transfer",
        "atm",
        "visa",
        "mastercard",
        "online",
        "the",
        "and",
        "ref",
        "txn",
        "trx",
        "inward",
        "outward",
        "fund",
        "funds",
        "trf",
        "ach",
        "direct",
        "dd",
        "so",
        "bill",
        "charge",
        "fee",
        "from",
        "to",
        "via",
        # Company forms, anywhere: "SPOTIFY AB", "BOLT OPERATIONS OU".
        "ltd",
        "limited",
        "pvt",
        "inc",
        "corp",
        "llc",
        "co",
        "plc",
        "gmbh",
        "ag",
        "ab",
        "bv",
        "nv",
        "oy",
        "ou",
        "pty",
        "srl",
        "sarl",
        "sa",
        "kk",
    ]
)


#: A web address's ending: "NETFLIX.COM", "AMAZON.CO.UK" and "BOLT.EU" are
#: Netflix, Amazon and Bolt.
_DOMAIN = re.compile(
    r"(?<=[a-z0-9]{2})\.(?:[a-z]{2,3}|app|info|shop|store|online|site|tech|dev|cloud|live)"
    r"(?:\.[a-z]{2})?$"
)


def payee_key(description: str) -> str:
    """The stable part of a bank description: its first words that are not
    references. "POS 1234 STARBUCKS #881 COLOMBO 03" → "pos starbucks colombo"."""
    words = (_DOMAIN.sub("", w.casefold().strip(".-'&")) for w in _SPLIT.split(description))
    kept = [w for w in words if len(w) > 1 and not any(ch.isdigit() for ch in w)]
    return " ".join(kept[:3])


def payee_word(description: str) -> str | None:
    """Who was paid, as one word: the first that is not a generic banking word.
    "POS 1234 STARBUCKS #881 COLOMBO" and "STARBUCKS 4413 KANDY" are both
    "starbucks"; "UBER *TRIP 8H3K2" and "UBER *EATS 77Q" are both "uber"."""
    return next(
        (w for w in payee_key(description).split() if w not in _GENERIC and len(w) >= 3),
        None,
    )


def payee_name(description: str) -> str:
    """Who was paid, to show: the stable words without the generic ones.
    "POS 1234 STARBUCKS #881 COLOMBO" → "Starbucks Colombo"."""
    words = [w for w in payee_key(description).split() if w not in _GENERIC]
    return " ".join(words).title()


def suggest(
    history: Sequence[tuple[Facts, str]],
    existing: Sequence[Rule],
    *,
    min_support: int = 3,
    min_agreement: float = 0.8,
) -> list[Suggestion]:
    """Rules the user's own history implies.

    `history` is (facts, the account the other side went to) for transactions
    they have already booked. A payee seen at least `min_support` times, going
    to the same account at least `min_agreement` of the time, and not already
    decided by an existing rule, becomes a suggestion — one that is checked to
    match every transaction it was learned from.
    """
    groups: dict[tuple[str, Direction], list[tuple[Facts, str]]] = defaultdict(list)
    for facts, account_id in history:
        payee = payee_word(facts.description)
        if payee:
            groups[(payee, facts.direction)].append((facts, account_id))

    suggestions: list[Suggestion] = []
    for (word, direction), rows in groups.items():
        if len(rows) < min_support:
            continue
        if any(first_match(existing, facts) for facts, _ in rows):
            continue
        account_id, agreement = Counter(account for _, account in rows).most_common(1)[0]
        if agreement / len(rows) < min_agreement:
            continue
        rule = Rule(
            id="",
            name=word.title(),
            conditions=(
                Condition("description", "contains", word),
                Condition("direction", "equals", direction),
            ),
            actions=Actions(account_id=account_id),
        )
        if not all(matches(rule, facts) for facts, _ in rows):
            continue
        suggestions.append(
            Suggestion(
                name=rule.name,
                conditions=rule.conditions,
                actions=rule.actions,
                support=len(rows),
                agreement=agreement,
                examples=tuple(dict.fromkeys(f.description for f, _ in rows))[:3],
            )
        )
    suggestions.sort(key=lambda s: (-s.support, s.name))
    return suggestions
