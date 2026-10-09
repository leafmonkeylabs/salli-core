"""
The AI model catalogue — pure domain, no I/O.

One source of truth for which models exist, what they cost relative to each
other, and which one every conversation runs on. Before this module the answer was split
across three places that had already drifted: the model constants in
`domain/agents/model_factory.py`, a `_MODEL_TIERS` dict in
`adapters/llm/anthropic_adapter.py`, and a bare literal inside
`adapters/parsing/llm_classifier.py`.

The catalogue is kept in full even though only one entry is reachable today:
pinning is a one-line change to undo, and a deployment that meters usage may
price by `relative_cost`.

## Why the relative costs are exact, not estimates

Every current Claude model prices output at exactly 5x its input, and the
models are exact integer multiples of each other:

    Haiku 4.5    $1 / $5     x1
    Sonnet 5     $3 / $15    x3
    Opus 5       $5 / $25    x5
    Fable 5      $10 / $50   x10

So a single integer per model is true cost passthrough rather than an
approximation, and the ratios stay correct no matter how the input/output
split of a particular request happens to fall.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AiModel:
    id: str
    name: str
    blurb: str
    #: The provider's list price as a multiple of Haiku 4.5's (see above).
    relative_cost: int


MODELS: dict[str, AiModel] = {
    "claude-haiku-4-5-20251001": AiModel(
        id="claude-haiku-4-5-20251001",
        name="Haiku 4.5",
        blurb="Fastest and cheapest. Good for quick questions and logging spending.",
        relative_cost=1,
    ),
    "claude-sonnet-5": AiModel(
        id="claude-sonnet-5",
        name="Sonnet 5",
        blurb="The balanced default. Strong at tax reasoning and planning.",
        relative_cost=3,
    ),
    "claude-opus-5": AiModel(
        id="claude-opus-5",
        name="Opus 5",
        blurb="Deeper reasoning for complex tax positions. Five times the price of Haiku.",
        relative_cost=5,
    ),
    "claude-fable-5": AiModel(
        id="claude-fable-5",
        name="Fable 5",
        blurb="The most capable model. Ten times the price of Haiku.",
        relative_cost=10,
    ),
}

#: The model every conversation runs on.
#:
#: This used to be "the model used when a user has expressed no preference",
#: with a picker letting anyone move to Sonnet, Opus or Fable. Model choice is
#: gone: the picker is removed from both clients, the selection endpoint is
#: deleted, and `get_preferred_model` returns this id for every user regardless
#: of what they had previously chosen.
#:
#: Haiku 4.5 because it is relative cost 1 — the cheapest of the four, and the
#: same model bulk extraction already ran on.
#:
#: The `preferred_model` column is deliberately left in place, still holding
#: whatever people last chose. Nothing reads it, and keeping it means restoring
#: the feature is a code revert rather than a migration plus lost data.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

#: Bulk row classification and free-text entry parsing. These are mechanical
#: extraction jobs where Haiku is the right tool. It is the same id as
#: DEFAULT_MODEL today — conversation and extraction have converged now that
#: choice is gone — but the two are kept separate because they are pinned for
#: different reasons, and only one of them would move if choice came back.
EXTRACTION_MODEL = "claude-haiku-4-5-20251001"


def get_model(model_id: str | None) -> AiModel:
    """Return the model for an id, falling back to the default."""
    return MODELS.get(model_id or DEFAULT_MODEL, MODELS[DEFAULT_MODEL])


def is_valid_model(model_id: str) -> bool:
    return model_id in MODELS
