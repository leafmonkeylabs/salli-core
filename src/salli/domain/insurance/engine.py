"""
Deterministic insurance coverage-gap engine.

Pure function: compute_report(policies, targets, today, expiry_warning_days) ->
CoverageGapReport. No I/O, no wall-clock reads — `today` is passed in.

Coverage per policy type is the sum of active policies' coverage_amount for that
type. A gap line is only produced for policy types the user has declared a target
for (mirroring the budget engine's "only declared categories get a line"
behaviour) — there is no universal "correct" coverage amount to assume otherwise.

`needs` is a needs analysis from the person's own figures: life cover from
income replacement years, debts and goals less assets; income protection from
spending; disability (income protection) cover from income replaced to the
planning age or a chosen benefit period, less the declared sick pay;
liability cover from what a claim against the person could reach,
their net worth. Figures only: it names no product and no provider. Where
the person typed no target for life, income-protection or liability cover, the report's gap
line for it comes from the needs analysis (`basis` "needs").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from salli.domain.insurance.models import (
    CoverageGapLine,
    CoverageGapReport,
    CoverageTarget,
    ExpiryAlert,
    Policy,
    PolicyType,
)


def compute_report(
    policies: list[Policy],
    targets: list[CoverageTarget],
    today: str,
    expiry_warning_days: int = 30,
    needed: Needs | None = None,
) -> CoverageGapReport:
    coverage_by_type: dict[str, Decimal] = {}
    for p in policies:
        if not p.is_active:
            continue
        coverage_by_type[p.policy_type] = (
            coverage_by_type.get(p.policy_type, Decimal(0)) + p.coverage_amount
        )

    lines: list[CoverageGapLine] = []
    missing_types: list[PolicyType] = []
    for target in targets:
        actual = coverage_by_type.get(target.policy_type, Decimal(0))
        lines.append(
            CoverageGapLine(
                policy_type=target.policy_type,
                target_amount=target.target_amount,
                actual_coverage=actual,
                gap=target.target_amount - actual,
            )
        )
        if actual == Decimal(0):
            missing_types.append(target.policy_type)
    if needed is not None:
        typed = {t.policy_type for t in targets}
        for kind, amount in (
            ("life", needed.life_cover_need),
            ("income_protection", needed.protection_need),
            ("liability", needed.liability_cover_need),
        ):
            if kind in typed or amount <= 0:
                continue
            actual = (
                needed.protection_held
                if kind == "income_protection"
                else coverage_by_type.get(kind, Decimal(0))
            )
            lines.append(CoverageGapLine(kind, amount, actual, amount - actual, "needs"))
            if actual == Decimal(0):
                missing_types.append(kind)

    today_date = date.fromisoformat(today)
    expiring_soon: list[ExpiryAlert] = []
    for p in policies:
        if not p.is_active:
            continue
        days_until = (date.fromisoformat(p.expiry_date) - today_date).days
        if 0 <= days_until <= expiry_warning_days:
            expiring_soon.append(
                ExpiryAlert(
                    policy_name=p.name,
                    policy_type=p.policy_type,
                    expiry_date=p.expiry_date,
                    days_until_expiry=days_until,
                )
            )

    return CoverageGapReport(
        lines=lines,
        missing_types=missing_types,
        expiring_soon=expiring_soon,
    )


@dataclass(frozen=True)
class Needs:
    """A needs analysis: figures, never a product. Every amount is in the
    base currency."""

    replacement_years: int
    #: Income × 12 × the years it would be replaced for.
    income_replacement: Decimal
    debts: Decimal
    goals: Decimal
    #: Cash, savings and investments that would be there to draw on.
    assets: Decimal
    #: income_replacement + debts + goals − assets, never below zero.
    life_cover_need: Decimal
    #: The active life policies' cover.
    life_cover_held: Decimal
    #: Need − held, never below zero.
    life_cover_gap: Decimal
    #: A month's spending: what an income-protection benefit would replace.
    income_protection_monthly: Decimal
    #: Net worth, never below zero: what a claim against the person could reach.
    liability_cover_need: Decimal = Decimal(0)
    #: The active liability policies' cover, and need − held (never below zero).
    liability_cover_held: Decimal = Decimal(0)
    liability_cover_gap: Decimal = Decimal(0)
    #: The months income would be replaced for if the person could not work:
    #: to the planning age, or the chosen benefit period.
    protection_months: int = 0
    #: What an employer would pay while off sick, as the person declares it.
    sick_pay: Decimal = Decimal(0)
    #: Income × protection_months − sick_pay, never below zero.
    protection_need: Decimal = Decimal(0)
    #: The active income-protection policies' monthly benefit × the months.
    protection_held: Decimal = Decimal(0)
    #: Need − held, never below zero.
    protection_gap: Decimal = Decimal(0)


def needs(
    monthly_income: Decimal,
    monthly_expenses: Decimal,
    debts: Decimal,
    goals: Decimal,
    assets: Decimal,
    life_cover_held: Decimal,
    replacement_years: int,
    net_worth: Decimal = Decimal(0),
    liability_cover_held: Decimal = Decimal(0),
    protection_months: int = 0,
    protection_benefit: Decimal = Decimal(0),
    sick_pay: Decimal = Decimal(0),
) -> Needs:
    """Life cover from replacing income for `replacement_years`, paying off
    debts and funding goals, less what is already there; income protection
    from monthly spending; disability cover from replacing income for
    `protection_months` less `sick_pay`, against the monthly
    `protection_benefit` held for as long."""
    replacement = max(monthly_income, Decimal(0)) * 12 * replacement_years
    need = max(replacement + debts + goals - assets, Decimal(0))
    protection = max(max(monthly_income, Decimal(0)) * protection_months - sick_pay, Decimal(0))
    held = protection_benefit * protection_months
    return Needs(
        replacement_years=replacement_years,
        income_replacement=replacement,
        debts=debts,
        goals=goals,
        assets=assets,
        life_cover_need=need,
        life_cover_held=life_cover_held,
        life_cover_gap=max(need - life_cover_held, Decimal(0)),
        income_protection_monthly=max(monthly_expenses, Decimal(0)),
        liability_cover_need=max(net_worth, Decimal(0)),
        liability_cover_held=liability_cover_held,
        liability_cover_gap=max(max(net_worth, Decimal(0)) - liability_cover_held, Decimal(0)),
        protection_months=protection_months,
        sick_pay=sick_pay,
        protection_need=protection,
        protection_held=held,
        protection_gap=max(protection - held, Decimal(0)),
    )
