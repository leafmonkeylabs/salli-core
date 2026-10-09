"""
Deterministic sentiment heuristic for tone-aware chat responses.

Pure functions, no LLM call and no I/O, keeps this fast, free, and testable.
This is intentionally a coarse keyword heuristic, not a general-purpose
sentiment model: it exists only to catch a handful of clearly-signalled
emotional states in the user's latest chat message so Scrooge can adjust his
delivery, not to classify sentiment accurately in general. When in doubt it
returns "neutral": a missed signal is far cheaper than a wrong one here.
"""

from __future__ import annotations

import re
from typing import Literal

Sentiment = Literal["frustrated", "anxious", "neutral", "positive"]

_FRUSTRATED_WORDS = (
    "frustrated",
    "frustrating",
    "annoyed",
    "annoying",
    "angry",
    "furious",
    "fed up",
    "sick of",
    "ridiculous",
    "useless",
    "worst",
    "hate this",
    "so stupid",
    "this is stupid",
    "why does this always",
    "not working",
    "doesn't work",
    "broken",
)

_ANXIOUS_WORDS = (
    "worried",
    "worry",
    "anxious",
    "anxiety",
    "nervous",
    "scared",
    "afraid",
    "stressed",
    "stressful",
    "panic",
    "panicking",
    "overwhelmed",
    "don't know what to do",
    "dont know what to do",
    "help me",
    "i'm freaking out",
    "im freaking out",
)

_POSITIVE_WORDS = (
    "thank you",
    "thanks",
    "great",
    "awesome",
    "amazing",
    "excellent",
    "love this",
    "loved it",
    "fantastic",
    "wonderful",
    "perfect",
    "finally",
    "yay",
    "excited",
    "happy",
)


def _count_matches(text: str, phrases: tuple[str, ...]) -> int:
    return sum(1 for phrase in phrases if phrase in text)


def classify_sentiment(text: str) -> Sentiment:
    """Classify the dominant sentiment signal in a chat message.

    Priority order when signals overlap: frustrated > anxious > positive >
    neutral. Frustration and anxiety are prioritised over positive signals
    because a message like "thanks, but I'm so frustrated this keeps
    happening" needs the frustration acknowledged, not just the thanks.
    """
    if not text:
        return "neutral"

    normalized = re.sub(r"\s+", " ", text.lower()).strip()

    exclaim_count = text.count("!")

    frustrated_hits = _count_matches(normalized, _FRUSTRATED_WORDS)
    if frustrated_hits > 0 or exclaim_count >= 3:
        return "frustrated"

    if _count_matches(normalized, _ANXIOUS_WORDS) > 0:
        return "anxious"

    if _count_matches(normalized, _POSITIVE_WORDS) > 0:
        return "positive"

    return "neutral"


def tone_instruction(sentiment: Sentiment) -> str:
    """Return a short meta-instruction for the manager agent's tone, or an
    empty string when no adjustment is needed (neutral)."""
    if sentiment == "frustrated":
        return (
            "Tone note: the user's message reads as frustrated. Acknowledge it in "
            "one short line, then get straight to the fix, no lecturing, no "
            "restating the problem back at length."
        )
    if sentiment == "anxious":
        return (
            "Tone note: the user's message reads as anxious. Lead with a concrete, "
            "reassuring fact from their actual data before recommending action, "
            "don't pile on more numbers than they need right now."
        )
    if sentiment == "positive":
        return (
            "Tone note: the user's message reads as positive. Match their energy "
            "briefly, then keep the momentum toward the next concrete step."
        )
    return ""
