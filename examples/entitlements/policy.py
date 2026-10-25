"""
A reference EntitlementPolicy: plan tiers mapped to the hypotheses in
business/thesis.md. An example for a hosted deployment's own (closed)
extension, not part of Salli; the open core shows everything (FullAccess).

Salli always computes the whole, truthful payload; a policy only decides how
much of it a person sees, and says what it held back (`withheld`), so nothing
shown is ever a different figure. Where a person's tier comes from (the
deployment's own records) is the deployment's: pass `tier_of`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from salli.application.ports import EntitlementPolicy, PayloadView, Surface
from salli.extensions import Extension, ExtensionContext, ExtensionSpec


@dataclass(frozen=True)
class Tier:
    """What one tier sees, and the thesis hypothesis it tests."""

    #: The row of business/thesis.md whose hypothesis the tier tests.
    tests: str
    #: Years of FI projections shown; None for all of them.
    projection_years: int | None = None
    #: Whether the monthly briefing is shown in full.
    briefing: bool = True


#: The tiers, after business/thesis.md ("Who pays", "Pricing hypotheses",
#: "The design-partner pilot"). A tier not named here sees what `trial` sees.
TIERS: dict[str, Tier] = {
    # The open core, and anyone the deployment hasn't placed: everything.
    "self_hosted": Tier("What is sold: the self-hosted open core, free"),
    # Design partners see everything, so the pilot measures activation, not limits.
    "pilot": Tier("The design-partner pilot: activation and retention"),
    # Salaried professionals keeping their own books: time saved importing.
    "hosted_person": Tier("Who pays: salaried professionals; hosted, one person"),
    # Households in two currencies: one net worth across them, shared read access.
    "hosted_household": Tier("Who pays: households in two currencies; hosted, a household"),
    # Before a choice: the books in full, a look ahead to five years, the
    # briefing's headline. Tests whether the deeper view is what is paid for.
    "trial": Tier("Pricing hypotheses: which depth people pay for", 5, False),
}


class _View:
    def __init__(self, tier: Tier) -> None:
        self._tier = tier

    def shape(self, surface: Surface, payload: dict[str, Any]) -> dict[str, Any]:
        if surface is Surface.FI_PROJECTIONS and self._tier.projection_years is not None:
            points = payload.get("points") or []
            shown = points[: self._tier.projection_years]
            if len(shown) < len(points):
                return {**payload, "points": shown, "withheld": ["points"]}
        if surface is Surface.ADVISOR_REPORT and not self._tier.briefing:
            kept = {k: v for k, v in payload.items() if k != "notes"}
            return {**kept, "withheld": ["notes"]}
        return payload


class TierPolicy(EntitlementPolicy):
    """Each person's tier, looked up once per request by `tier_of`."""

    def __init__(self, tier_of: Callable[[str], Awaitable[str | None]]) -> None:
        self._tier_of = tier_of

    async def for_user(self, user_id: str, email: str | None = None) -> PayloadView:
        name = await self._tier_of(user_id)
        return _View(TIERS.get(name or "", TIERS["trial"]))


async def _everyone_self_hosted(user_id: str) -> str:
    return "self_hosted"


def build(ctx: ExtensionContext) -> Extension:
    return Extension(name="tiers", entitlements=TierPolicy(_everyone_self_hosted))


spec = ExtensionSpec(name="tiers", build=build)
