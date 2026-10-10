"""
FIRE Strategy LLM agent. Generates a personalised AI FireStrategy.

The model receives the user's actual ledger data, applies the seven FIRE
theories, and returns a structured FireStrategy. It NEVER computes money;
all figures are passed in from the deterministic engine and ledger.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from salli.domain.agents.style import WRITING_STYLE

FIRE_SYSTEM_PROMPT = (
    """You are Salli's FIRE Strategy Architect, a deep-thinking financial independence advisor
who tailors strategy to the user's country and currency, with expertise in international FIRE literature.

You will analyse a user's REAL financial data (from their ledger) and produce a personalised
FIRE strategy using these seven foundational theories:

1. **Trinity Study / 4% Rule**: Derive the safe withdrawal rate (SWR) based on the user's
   situation, starting from the one in the assumptions (4% is the Trinity study's: 25x
   expenses). FatFIRE users with conservative needs may use 3.5%, and those with aggressive
   growth plans may use 4.5%.

2. **Barbell Strategy**: Create two poles, ultra-safe (emergency + bonds/FDs) and
   high-growth (equities/business). Avoid the mushy middle. The size of each pole depends
   on the user's risk appetite and income stability.

3. **Three-Bucket System**: Organise into Liquidity (emergency, 1-2y expenses), Stability
   (medium-term, bonds/FDs), and Growth (long-term, equities). Adapt bucket sizes to the
   user's timeline and income.

4. **Pay Yourself First**: Design the allocation buckets in automation order, emergency
   bucket first, then stability, then growth. Monthly contributions flow in this sequence.

5. **JL Collins Simple Path**: Favour low-cost index funds for the growth bucket. Suggest
   the kinds of fund to look for where the user lives (the end of this prompt says what is
   known about that), and for the international portion, broad index ETFs, via a foreign
   account where needed.

6. **Currency Diversification**: If the user has foreign income or multi-currency accounts,
   create a dedicated foreign currency / hedge bucket. Home-currency depreciation risk is
   real for many currencies: weight this bucket for the user's base currency.

7. **FIRE Tier Classification**: Classify the user:
   - LeanFIRE: savings rate < 30%, living lean
   - Standard FIRE: savings rate 30-50%
   - FatFIRE: savings rate ≥ 50%, or high income with comfort-first lifestyle
   - CoastFIRE: user wants to stop contributing but let investments compound

Generate allocation buckets appropriate to this user, not a generic template. The bucket
count, names, and target percentages should reflect their actual financial profile.

Planning assumptions: Salli plans in REAL terms (after inflation, in today's money). The
data's `assumptions` gives the base scenario's real return and the safe withdrawal rate Salli
applies for this user, and their inflation if they set one. Each has an `origin`: `user` when
they (or their agent) set it, with the `source` they cited, or `placeholder` when it is
Salli's neutral stand-in, a round figure that is no forecast and no country's figure.
`status` is `placeholder` while any is one. Use them:
- Choose three REAL yearly returns (conservative, base, growth), after inflation: never
  nominal ones. Your base should be near the real return given, or say in ai_rationale why not
- Keep to any assumption whose origin is `user`: Salli applies theirs over yours
- In ai_rationale, say which assumptions you built on and where each came from. Call a
  placeholder what it is, and suggest the user set their own figures, with sources

Rules:
- Target percentages across all buckets must sum to 100%
- All figures you reference MUST come from the data provided, never invent or estimate
- Be specific: reference actual account types, income sources, and amounts from the data
- If re-running, reference what has changed and what stays the same
- The ai_rationale should be detailed markdown (300-500 words) explaining the full strategy

"""
    + WRITING_STYLE
)


class BucketSchema(BaseModel):
    key: str = Field(description="Unique key, snake_case, e.g. 'emergency_moat'")
    name: str = Field(description="Display name, e.g. 'Emergency Moat'")
    target_pct: float = Field(
        ge=0.0,
        le=1.0,
        description="A FRACTION between 0.0 and 1.0 (e.g. 0.25 for 25%), never a percentage",
    )
    description: str = Field(
        description="1-2 sentences explaining this bucket and what to invest in"
    )
    color: str = Field(description="One of: emerald, blue, amber, violet, rose, teal, orange")


class FireStrategySchema(BaseModel):
    """
    Bounds are load-bearing, not cosmetic. These rates divide and compound the
    user's money downstream, so a model that answers `3.5` where `0.035` is
    meant would silently shrink the Freedom Number ~100x and report FI as
    already reached. Reject such a response rather than serve a wrong number
    (CLAUDE.md: "LLM never computes money or tax").
    """

    fire_style: Literal["lean", "standard", "fat", "coast"] = Field(
        description="FIRE tier classification"
    )
    swr: float = Field(
        ge=0.02,
        le=0.06,
        description="Safe withdrawal rate as a FRACTION, e.g. 0.04 for 4%, never 4",
    )
    real_return_conservative: float = Field(
        ge=-0.05,
        le=0.15,
        description="Conservative yearly REAL return (after inflation) as a FRACTION, e.g. 0.02",
    )
    real_return_base: float = Field(
        ge=-0.05,
        le=0.15,
        description="Base yearly REAL return (after inflation) as a FRACTION, e.g. 0.04",
    )
    real_return_growth: float = Field(
        ge=-0.05,
        le=0.15,
        description="Growth yearly REAL return (after inflation) as a FRACTION, e.g. 0.06",
    )
    target_monthly_expenses: float | None = Field(
        default=None,
        ge=0.0,
        description="Target monthly expenses at retirement; null = use current actuals",
    )
    target_age: int | None = Field(
        default=None, ge=18, le=100, description="Target retirement age, or null"
    )
    buckets: list[BucketSchema] = Field(
        description="AI-generated allocation buckets; target_pct must sum to 1.0"
    )
    ai_rationale: str = Field(
        description="Detailed markdown explanation of the strategy (300-500 words)"
    )
    theories_applied: list[str] = Field(
        description="List of theory names applied, e.g. ['Trinity Study', 'Barbell']"
    )

    @model_validator(mode="after")
    def _normalise_buckets(self) -> FireStrategySchema:
        """
        Rescale bucket weights to sum to exactly 1.0.

        Unlike the rates above, a bucket sum that is merely close (0.99, 1.02)
        is recoverable and not worth failing a whole generation over, the
        allocation's *relative* split is what the model was reasoning about.
        A sum of 0 carries no information, so it is rejected.
        """
        if not self.buckets:
            return self
        total = sum(b.target_pct for b in self.buckets)
        if total <= 0:
            raise ValueError("bucket target_pct values must sum to a positive number")
        if abs(total - 1.0) > 1e-9:
            for b in self.buckets:
                b.target_pct = b.target_pct / total
        return self

    @model_validator(mode="after")
    def _returns_ordered(self) -> FireStrategySchema:
        """Conservative <= base <= growth, or the three scenarios are meaningless."""
        if not (self.real_return_conservative <= self.real_return_base <= self.real_return_growth):
            raise ValueError(
                "returns must be ordered conservative <= base <= growth, got "
                f"{self.real_return_conservative}, {self.real_return_base}, "
                f"{self.real_return_growth}"
            )
        return self


async def generate_strategy(
    context: dict[str, Any], *, llm: Any, model: str | None = None
) -> FireStrategySchema:
    """The strategy the model proposes for `context`, validated.

    `llm` is the user's resolved LLMClient (application/ports.py), on whichever
    provider they use; `model` is the one the usage meter was told about, so
    the model priced is the model that runs (None: the client's "best").
    """
    from pydantic import ValidationError

    from salli.domain.llm import LLMUnreadableAnswer, parse_json_answer

    payload = json.dumps(context, indent=2, default=str)

    is_refresh = bool(context.get("previous_strategy"))
    task = (
        "Review the user's current strategy and update it based on what has changed. "
        "Preserve decisions that are still sound. Clearly explain in ai_rationale what changed and why."
        if is_refresh
        else "Generate a comprehensive, personalised FIRE strategy for this user based on their actual financial data."
    )

    from salli.domain.agents.jurisdiction import investing_context

    # Where the user invests, and nothing else about it: Salli keeps no notes
    # on any country's products, so the strategy suggests kinds, not names.
    system = f"{FIRE_SYSTEM_PROMPT}\n\n{investing_context(context.get('tax_residency'))}"
    text = await llm.generate(
        instructions=system,
        input=f"Here is the user's financial profile:\n\n{payload}\n\nTask: {task}",
        tier="best",
        model=model,
        schema=FireStrategySchema,
        temperature=0.3,
        max_output_tokens=8000,
    )
    try:
        return FireStrategySchema.model_validate(parse_json_answer(text))
    except ValidationError as exc:
        # The bounds above are what stand between a misread rate and a wrong
        # Freedom Number, so an answer outside them is refused, not repaired.
        raise LLMUnreadableAnswer(
            "The strategy the AI proposed was not usable. Please try again."
        ) from exc
