"""
Default FIRE pack — the method behind the FI score: how its parts are weighed.

It holds no planning assumption. The safe withdrawal rate and the returns the
score and projections use are the user's own or labelled placeholders (domain/fi/assumptions.py), passed to the engine
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
    # 3.0.0: the top grades need progress to FI ("FI-ready" at 100%, "Strong"
    # at 50%); debt is scored by what it costs (rates weighted by balance)
    # where rates are known, by its share of assets otherwise; and under two
    # full months of income and spending the grade is "Not enough data".
    # 4.0.0: debt is scored by its size too: half of the debt component is
    # the debt-service ratio (scheduled payments ÷ income), nothing at 40%.
    version="4.0.0",
    emergency_fund_target_months=6,
    savings_rate_for_full_score=Decimal("0.50"),  # saving 50%+ of income scores full marks
    weights={
        "savings_rate": Decimal("0.25"),
        "emergency_fund": Decimal("0.15"),
        "fi_progress": Decimal("0.35"),
        "debt": Decimal("0.10"),
        "goals": Decimal("0.15"),
    },
    debt_rate_for_zero_score=Decimal("0.20"),  # a 20% average rate scores no marks
    debt_service_for_zero_score=Decimal("0.40"),  # payments of 40% of income score no marks
    debt_service_weight=Decimal("0.5"),
    progress_for_fi_ready=Decimal(1),
    progress_for_strong=Decimal("0.5"),
)
