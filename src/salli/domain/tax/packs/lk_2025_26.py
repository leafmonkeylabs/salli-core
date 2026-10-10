"""
Sri Lanka — Year of Assessment 2025/26 (1 April 2025 – 31 March 2026).

Source: Inland Revenue (Amendment) Act No. 2 of 2025 and IRD Notice PN/IT/2025-01.
This pack must be reviewed by a chartered accountant before use in production.

Key changes from 2024/25:
- Personal relief raised from LKR 1,200,000 to LKR 1,800,000
- First band raised from LKR 500,000 to LKR 1,000,000 (6%)
- 12% bracket eliminated entirely
"""

from decimal import Decimal

from salli.domain.tax.models import (
    Band,
    FilingCalendar,
    ForeignServiceIncomeRegime,
    TaxPack,
)

LK_2025_26 = TaxPack(
    country="LK",
    year="2025/26",
    version="1.0.0",
    currency="LKR",
    period_start="2025-04-01",
    period_end="2026-03-31",
    #
    # LKR 1,800,000 personal relief (effective 1 April 2025).
    personal_relief=Decimal("1_800_000"),
    #
    # Bands applied to taxable income AFTER deducting relief (and QPDs).
    # Thresholds are cumulative from zero.
    bands=[
        Band(upto=Decimal("1_000_000"), rate=Decimal("0.06")),
        Band(upto=Decimal("1_500_000"), rate=Decimal("0.18")),
        Band(upto=Decimal("2_000_000"), rate=Decimal("0.24")),
        Band(upto=Decimal("2_500_000"), rate=Decimal("0.30")),
        Band(upto=None, rate=Decimal("0.36")),  # balance — unbounded
    ],
    #
    # 15% maximum / final tax on employment income remitted via a Sri Lankan bank.
    foreign_service_income=ForeignServiceIncomeRegime(
        max_rate=Decimal("0.15"),
        requires_bank_remittance=True,
    ),
    #
    # Credits (applied in this order by the engine):
    #   APIT    — Advanced Personal Income Tax withheld by employer
    #   AIT     — Advance Income Tax on bank interest (10%)
    #   FTC     — Foreign Tax Credit under s.80 (even without a DTA;
    #             pay only the shortfall if foreign tax < 15%)
    credits=["APIT", "AIT_INTEREST_10", "FOREIGN_TAX_CREDIT"],
    #
    rounding="nearest_rupee",
    #
    filing=FilingCalendar(
        set_due="08-15",  # SET + 1st installment
        installments=["08-15", "11-15", "02-15", "05-15"],
        final_installment_due="09-30",
        return_due="11-30",  # 30 November
    ),
)
