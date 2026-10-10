"""
Default FIRE pack — the method behind the FI score: how its parts are weighed.

It holds no planning assumption. The safe withdrawal rate and the returns the
score and projections use are the user's own, their FIRE strategy's, or
labelled placeholders (domain/fi/assumptions.py), passed to the engine
explicitly.

Must be reviewed by a financial planner before being presented as advice in
production.
"""

from __future__ import annotations

from decimal import Decimal

from salli.domain.fi.models import FiPack

DEFAULT_V1 = FiPack(
    # 2.0.0: the assumptions moved out of the pack, and projections run in real
    # terms from the user's figures or labelled placeholders.
    version="2.0.0",
    emergency_fund_target_months=6,
    savings_rate_for_full_score=Decimal("0.50"),  # saving 50%+ of income scores full marks
    weights={
        "savings_rate": Decimal("0.25"),
        "emergency_fund": Decimal("0.15"),
        "fi_progress": Decimal("0.35"),
        "debt": Decimal("0.10"),
        "goals": Decimal("0.15"),
    },
)
