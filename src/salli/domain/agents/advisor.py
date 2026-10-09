"""
Financial Independence Mentor LLM. Turns DETERMINISTIC financial figures and the
user's active FIRE strategy into prioritised, strategy-linked mentoring recommendations.
The model never computes money; it is handed the FI score, strategy buckets, projections,
and current rates, and only narrates/prioritises against the user's actual plan.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from salli.domain.agents.style import WRITING_STYLE

ADVISOR_PROMPT = (
    """You are Salli's Financial Independence Mentor, a deeply experienced FIRE coach \
who tailors advice to the user's country and currency, with expertise in the seven FIRE theories.

You have the user's complete financial picture: their FI score, actual ledger-derived income and \
expense breakdown, their AI-generated FIRE strategy (including specific allocation buckets, target \
SWR, FIRE tier, return assumptions, and theories applied), portfolio projections, goals, and current \
market rates.

Your role is NOT generic money coaching. You give STRATEGY-SPECIFIC mentoring tied to the user's \
actual FIRE strategy. When you have a strategy, every recommendation must reference it explicitly.

FIRE-Tier mentoring focus:
- lean: prioritise savings rate maximisation, cost cutting, and high-yield safe instruments
- standard: balance growth investing with stability; activate all strategy buckets properly
- fat: focus on asset quality, tax efficiency, diversification; idle cash is the enemy
- coast: stop contributing stress; protect principal; ensure compounding works uninterrupted

FIRE Strategy Alignment (when strategy is present):
- Reference the user's specific allocation buckets by name and key
- If a bucket's target_pct is unmet (surplus not being routed there), flag it specifically
- Reference actual return assumptions from the strategy (conservative/base/growth rates)
- Reference the projected years-to-FIRE and which scenario the user is tracking toward
- Reference theories applied (e.g. "As your Barbell Strategy specifies...")

Mentoring framework (apply in this priority order):
1. Emergency moat: is the emergency bucket funded to its target? Nothing else compounds safely without it.
2. High-interest debt elimination: destroys compounding faster than any investment can recover.
3. Bucket activation: is the monthly surplus flowing to the right strategy buckets in the right proportions?
4. Yield on safe assets: idle cash and safety-bucket holdings should earn best-available FD/T-bill yields.
5. Growth bucket deployment: accumulated growth-bucket money must be invested, not just held in savings.
6. Currency/FX resilience: if there's a currency hedge bucket, ensure foreign income flows there.
7. Goal alignment: user's stated goals should map to specific buckets. Surface the connection.
8. Tax efficiency: maximise after-tax returns within the strategy framework.

Rules:
- NEVER recompute or invent numbers, reference provided figures exactly
- Each rationale: 1–2 sentences, specific to THIS person's data and strategy
- If the recommendation relates to a specific strategy bucket, set bucket_key to that bucket's key
- Produce 4–7 recommendations ordered by priority (1 = highest)
- fire_tier_assessment: 1 sentence confirming their FIRE tier and its primary implication
- The summary references their years-to-FIRE, savings rate, and the #1 move

"""
    + WRITING_STYLE
)


class SuggestedAction(BaseModel):
    type: Literal["none", "reminder"] = "none"
    label: str = Field(default="", description="Human label, e.g. 'Open a 1-year fixed deposit'")
    due_in_days: int | None = Field(default=None, description="If a reminder, days from today")


class Recommendation(BaseModel):
    title: str = Field(description="Short imperative recommendation")
    rationale: str = Field(description="1–2 sentences grounded in the figures and strategy")
    category: str = Field(
        description="emergency_fund|debt|savings|investing|spending|tax|goal|bucket_allocation"
    )
    priority: int = Field(default=2, description="1 high, 2 medium, 3 low")
    bucket_key: str | None = Field(
        default=None,
        description="Key of the relevant FIRE allocation bucket if this rec targets one, else null",
    )
    action: SuggestedAction = SuggestedAction()


class Advice(BaseModel):
    summary: str = Field(
        description="2–3 sentences: where they stand on their FIRE journey, "
        "years-to-FIRE if known, and the single most important move"
    )
    fire_tier_assessment: str = Field(
        description="1 sentence confirming their FIRE tier classification and its primary implication"
    )
    recommendations: list[Recommendation] = Field(default_factory=list)


async def generate_advice(context: dict[str, Any], *, llm: Any) -> Advice:
    """Prioritised recommendations for `context`, validated. `llm` is the
    user's resolved LLMClient (application/ports.py)."""
    from pydantic import ValidationError

    from salli.domain.llm import LLMUnreadableAnswer, parse_json_answer

    payload = json.dumps(context, indent=2, default=str)
    text = await llm.generate(
        instructions=ADVISOR_PROMPT,
        input=f"Here is the person's current financial picture:\n\n{payload}\n\n"
        f"Produce 4–7 prioritised mentoring recommendations tied to their FIRE strategy.",
        tier="best",
        schema=Advice,
        temperature=0.3,
        max_output_tokens=2000,
    )
    try:
        return Advice.model_validate(parse_json_answer(text))
    except ValidationError as exc:
        raise LLMUnreadableAnswer(
            "The advice the AI wrote could not be read. Please try again."
        ) from exc
