"""
The decision lab's guardrails, as checks a test can make: Salli never ranks
options, and neither does anything it says about them (docs/design/
decision-lab.md, decision 1). A template, a decision's start, a comparison,
a prompt: none has a field that ranks or scores, or calls an option best,
recommended or what one should do. And a digest never presses: no urgency,
no streaks, no countdowns, no `!` (phase 3, decision 30).
"""

from __future__ import annotations

import re
from typing import Any, cast

#: Words that rank, recommend or advise. A person's own words (their labels,
#: their principles) are theirs; Salli's never use these.
RANKING_WORDS = re.compile(
    r"\b(best|better|worse|worst|recommend\w*|optimal|optimum|winner|should|ought|"
    r"ideal|smartest|wisest|rank|ranked|ranking|score|scored|scoring)\b",
    re.IGNORECASE,
)
#: A word right after a negation ("not a recommendation", "never best") is a
#: disclaimer, not a ranking.
NEGATED = re.compile(r"\b(not|never|nor|no)\s+(?:an?\s+|the\s+|one\s+)?\w+", re.IGNORECASE)
#: Field names that would rank or score.
RANKING_KEYS = re.compile(r"rank|score|best|recommend|winner|prefer|verdict", re.IGNORECASE)


def texts(node: Any, path: str = "$") -> list[tuple[str, str]]:
    """Every string in a JSON-ready value, with where it is; keys too."""
    out: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in cast("dict[Any, Any]", node).items():
            out.append((f"{path}.{key} (key)", str(key)))
            out.extend(texts(value, f"{path}.{key}"))
    elif isinstance(node, list | tuple):
        for i, value in enumerate(cast("list[Any]", node)):
            out.extend(texts(value, f"{path}[{i}]"))
    elif isinstance(node, str):
        out.append((path, node))
    return out


def assert_never_ranks(document: Any) -> None:
    """No field ranks or scores, and no text ranks, recommends or advises."""
    for where, text in texts(document):
        if where.endswith("(key)"):
            assert not RANKING_KEYS.search(text), f"a ranking field at {where}: {text!r}"
        else:
            found = RANKING_WORDS.search(NEGATED.sub(r"\1", text))
            assert not found, f"{found.group(0)!r} at {where}: {text!r}"


#: Words that press, count streaks or count down (the design's "never" list
#: for nudges: docs/design/decision-lab.md, "Nudges"; phase 3, decision 30).
#: Salli's messages say what is waiting and when, never how soon or how often.
URGENCY_WORDS = re.compile(
    r"\b(urgent\w*|hurry|today only|last chance|don'?t miss|act fast|act now|"
    r"deadline approaching|streaks?|in a row|consecutive\w*|days? left|countdown|"
    r"score\w*|level|points?)\b",
    re.IGNORECASE,
)
#: A number of days, counted down or up ("3 days", "in 5 days"): a message
#: gives a date instead.
DAY_COUNTS = re.compile(r"\b\d+\s+(days?|weeks?|hours?)\b", re.IGNORECASE)


def assert_never_urges(document: Any) -> None:
    """No urgency, streak or countdown word, no number of days, and no `!`,
    in any text; and nothing that ranks (`assert_never_ranks`)."""
    assert_never_ranks(document)
    for where, text in texts(document):
        if where.endswith("(key)"):
            continue
        found = URGENCY_WORDS.search(text) or DAY_COUNTS.search(text)
        assert not found, f"{found.group(0)!r} at {where}: {text!r}"
        assert "!" not in text, f"'!' at {where}: {text!r}"
