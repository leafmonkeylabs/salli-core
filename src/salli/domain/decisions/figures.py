"""
The figures a principle's check reads: a fixed, documented set, computed
from one scenario's outlook (or the baseline's own). Pure, Decimal.

A principle (`principles.py`) is the user's rule of thumb, written in the
tax rules' safe expression language over these names, so it stays
deterministic and needs no model: `emergency_months >= 6`,
`max_debt_rate_while_investing <= 0.07`, `account_lowest >= 2000` (with the
principle naming the account). The set is fixed on purpose: a check written
today means the same thing next year, and an entry in the decision journal
records the figures it was checked against.

Every figure is the value Salli shows: an amount rounded to the base
currency's smallest unit (an account's, for `account_lowest`), months of
spending to the hundredth, a rate exact. So a check agrees with the number
the person reads. Each is one of:

- an **amount** in the base currency, either **nominal** (each day's or
  month's own money: the cash timeline, interest, borrowing) or **real**
  (today's money: the monthly timeline, the FI number);
- **months** of spending, a decimal;
- a **rate**, a yearly fraction (0.07 is 7%);
- a **count** of months, a whole number;
- **true or false**.

A figure Salli can't give (no spending to count months of, FI not within 50
years) is missing, with the reason, and a check that reads it can't be
evaluated: never kept, never broken.

The monthly figures come from the 50-year timeline, whatever horizon a
scenario shows, so a check at ten years works on a five-year scenario.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from salli.domain.baseline import timelines
from salli.domain.baseline.models import Baseline, BaselineDebt
from salli.domain.currency import quantize
from salli.domain.scenarios.engine import Outlook
from salli.domain.scenarios.tax import TaxOutcome

Kind = Literal["amount", "months", "rate", "count", "boolean"]
Terms = Literal["nominal", "real", "none"]
Group = Literal["cash", "resilience", "monthly", "debts", "fi", "tax"]

#: The years the monthly figures are read at.
YEARS = (1, 5, 10, 20)

_HUNDREDTH = Decimal("0.01")


@dataclass(frozen=True)
class FigureSpec:
    """One figure a check may read: its name, what it is, and its unit."""

    name: str
    kind: Kind
    terms: Terms
    group: Group
    description: str

    @property
    def unit(self) -> str:
        if self.name == "account_lowest":
            return "the account's own currency"
        return {
            "amount": "the base currency",
            "months": "months of spending",
            "rate": "a yearly fraction (0.07 is 7%)",
            "count": "months",
            "boolean": "true or false",
        }[self.kind]


def _monthly_specs() -> list[FigureSpec]:
    what = {
        "net_worth": "Net worth (cash and investments and other assets, less debts and other "
        "liabilities)",
        "cash": "Cash (the cash accounts together, a card's balance against them)",
        "investments": "Investments (grown at the real return)",
        "debts": "What the debts with terms (and the option's loans) still owe",
    }
    return [
        FigureSpec(
            f"{name}_{years}y",
            "amount",
            "real",
            "monthly",
            f"{text} at the end of the month {years} year{'s' if years > 1 else ''} after "
            "the as-of month, in today's money.",
        )
        for name, text in what.items()
        for years in YEARS
    ]


#: Every figure there is, in the order they are documented (docs/decisions.md).
FIGURES: tuple[FigureSpec, ...] = (
    FigureSpec(
        "lowest_cash",
        "amount",
        "nominal",
        "cash",
        "The lowest the cash accounts together get, on any day of the as-of month and the "
        "twelve after it.",
    ),
    FigureSpec(
        "cash_in_12_months",
        "amount",
        "nominal",
        "cash",
        "The cash accounts together at the end of the twelfth month after the as-of month.",
    ),
    FigureSpec(
        "safe_to_spend",
        "amount",
        "nominal",
        "cash",
        "What could go out on the as-of date without cash dropping below zero before money "
        "next comes in.",
    ),
    FigureSpec(
        "account_lowest",
        "amount",
        "nominal",
        "cash",
        "The lowest the principle's own account (its `account`, one of your cash accounts) "
        "gets over the same thirteen months, in that account's currency.",
    ),
    FigureSpec(
        "any_account_below_zero",
        "boolean",
        "none",
        "cash",
        "Whether any cash account goes below zero over the same thirteen months.",
    ),
    FigureSpec(
        "monthly_spending",
        "amount",
        "real",
        "resilience",
        "The monthly spending the emergency months are counted in: essential spending when "
        "your spending carries need tags, all of it otherwise.",
    ),
    FigureSpec(
        "emergency_months",
        "months",
        "none",
        "resilience",
        "The months of that spending your cash covers at its lowest over the same thirteen months.",
    ),
    FigureSpec(
        "emergency_months_in_12_months",
        "months",
        "none",
        "resilience",
        "The months of that spending your cash covers at the end of the twelfth month.",
    ),
    *_monthly_specs(),
    FigureSpec(
        "total_interest",
        "amount",
        "nominal",
        "debts",
        "The interest every debt (and the option's loans) costs over its schedule, each "
        "payment in its own money.",
    ),
    FigureSpec(
        "debt_free_months",
        "count",
        "none",
        "debts",
        "Months from the as-of month to the month the last debt is paid off; 0 when nothing "
        "is owed.",
    ),
    FigureSpec(
        "max_debt_rate",
        "rate",
        "none",
        "debts",
        "The highest yearly rate of any debt owed at any month's end in the next 50 years "
        "(the option's loans included); 0 when nothing is owed.",
    ),
    FigureSpec(
        "max_debt_rate_while_investing",
        "rate",
        "none",
        "debts",
        "The highest yearly rate of any debt still owed at the end of a month in which money "
        "moves into investments (the share of the surplus you invest, or an invest change); "
        "0 when no debt is owed while you invest.",
    ),
    FigureSpec(
        "borrowed",
        "amount",
        "nominal",
        "debts",
        "What the option borrows: its loans' principal together (0 for the baseline).",
    ),
    FigureSpec(
        "fi_number",
        "amount",
        "real",
        "fi",
        "A year of the spending you would live on, over your safe withdrawal rate.",
    ),
    FigureSpec(
        "fi_months",
        "count",
        "none",
        "fi",
        "Months from the as-of month to the month you reach the FI number.",
    ),
    FigureSpec(
        "fi_months_gained",
        "count",
        "none",
        "fi",
        "Months sooner (positive) or later (negative) the option reaches FI than the "
        "baseline does; 0 for the baseline.",
    ),
    FigureSpec(
        "tax_change_this_year",
        "amount",
        "nominal",
        "tax",
        "The change in the as-of date's tax year's tax (its `net`, after credits) the option "
        "makes, computed with your active tax rules from its changes tagged with a tax role; "
        "more tax is positive. 0 for the baseline and when nothing in the year is tagged; "
        "missing when the tax isn't computed (no active rules, say).",
    ),
)

BY_NAME: Mapping[str, FigureSpec] = {f.name: f for f in FIGURES}

Value = Decimal | bool


@dataclass(frozen=True)
class Figures:
    """The figures for one option (or the baseline): each one's value, or,
    for one Salli can't give, why not."""

    currency: str
    values: Mapping[str, Value]
    missing: Mapping[str, str]
    #: Each cash account at its lowest: id → (its currency, the amount).
    accounts: Mapping[str, tuple[str, Decimal]] = field(
        default_factory=dict[str, tuple[str, Decimal]]
    )

    def get(self, name: str, account: str | None = None) -> Value | None:
        """A figure's value; None when it is missing."""
        if name == "account_lowest":
            found = self.accounts.get(account) if account else None
            return None if found is None else found[1]
        return self.values.get(name)

    def why_missing(self, name: str, account: str | None = None) -> str | None:
        """Why a figure has no value, or None when it has one."""
        if name == "account_lowest":
            if not account:
                return "the principle names no account"
            if account not in self.accounts:
                return (
                    "its account isn't one of the cash accounts the forecast carries (closed, "
                    "or held in a currency with no rate)"
                )
            return None
        return self.missing.get(name)


def _months(value: Decimal) -> Decimal:
    return value.quantize(_HUNDREDTH, rounding=ROUND_HALF_UP)


def _owes(debt: timelines.DebtOutlook) -> bool:
    return any(owed > 0 for owed in debt.owed)


def compute(
    baseline: Baseline,
    mine: Outlook,
    base: Outlook,
    loans: Sequence[BaselineDebt] = (),
    tax: TaxOutcome | None = None,
) -> Figures:
    """The figures for `mine` (an option's outlook, or the baseline's own),
    against the baseline's outlook `base` (for the months gained), with the
    loans the option takes out (`loans`) and its tax (`tax`, its
    translation's; none for the baseline)."""
    currency = baseline.currency

    def money(value: Decimal) -> Decimal:
        return quantize(value, currency, strict=False)

    values: dict[str, Value] = {}
    missing: dict[str, str] = {}

    # Cash over the as-of month and the twelve after it.
    forecast = mine.cash.forecast
    values["lowest_cash"] = money(forecast.lowest)
    values["cash_in_12_months"] = money(forecast.end_balance)
    values["safe_to_spend"] = money(mine.safe.amount)
    cash_ids = {b.account_id for b in baseline.balances if b.role == "cash"}
    accounts = {
        a.account_id: (a.currency, quantize(a.lowest, a.currency, strict=False))
        for a in forecast.accounts
        if a.account_id in cash_ids
    }
    values["any_account_below_zero"] = any(lowest < 0 for _, lowest in accounts.values())

    # Resilience: what the scenario engine's emergency-fund months count.
    flows = baseline.flows
    spend: Decimal | None
    if flows.essential is not None and flows.essential > 0:
        spend = flows.essential
    elif flows.expenses > 0:
        spend = flows.expenses
    else:
        spend = None
    if spend is None:
        why = "there is no spending in your ledger to count months of"
        for name in ("monthly_spending", "emergency_months", "emergency_months_in_12_months"):
            missing[name] = why
    else:
        values["monthly_spending"] = money(spend)
        values["emergency_months"] = _months(forecast.lowest / spend)
        values["emergency_months_in_12_months"] = _months(forecast.end_balance / spend)

    # The monthly timeline, in today's money.
    points = mine.monthly.points
    for years in YEARS:
        point = points[12 * years + 1]
        values[f"net_worth_{years}y"] = money(point.net_worth)
        values[f"cash_{years}y"] = money(point.cash)
        values[f"investments_{years}y"] = money(point.investments)
        values[f"debts_{years}y"] = money(point.debts)

    # Debts.
    debts = mine.monthly.debts
    values["total_interest"] = money(sum((d.total_interest for d in debts), Decimal(0)))
    owing = [d for d in debts if _owes(d)]
    start = timelines.month_index(points[0].month)
    if not owing:
        values["debt_free_months"] = Decimal(0)
    elif mine.monthly.debt_free is None:
        missing["debt_free_months"] = "the debts aren't all paid off within 50 years"
    else:
        values["debt_free_months"] = Decimal(timelines.month_index(mine.monthly.debt_free) - start)
    values["max_debt_rate"] = max((d.apr for d in owing), default=Decimal(0))
    while_investing = Decimal(0)
    for i, point in enumerate(points[1:]):
        if point.invested <= 0:
            continue
        for d in owing:
            if i < len(d.owed) and d.owed[i] > 0 and d.apr > while_investing:
                while_investing = d.apr
    values["max_debt_rate_while_investing"] = while_investing
    values["borrowed"] = money(sum((loan.balance for loan in loans), Decimal(0)))

    # Financial independence.
    if mine.fi.fi_number > 0:
        values["fi_number"] = money(mine.fi.fi_number)
    else:
        missing["fi_number"] = "there is no spending to base it on"
    if mine.fi.months is not None:
        values["fi_months"] = Decimal(mine.fi.months)
    else:
        missing["fi_months"] = (
            "there is no FI number yet"
            if mine.fi.fi_number <= 0
            else "the FI number isn't reached within 50 years"
        )
    if mine.fi.months is not None and base.fi.months is not None:
        values["fi_months_gained"] = Decimal(base.fi.months - mine.fi.months)
    else:
        missing["fi_months_gained"] = (
            "FI isn't reached within 50 years under the baseline or the option"
        )

    # Tax.
    change = Decimal(0) if tax is None else tax.change_this_year
    if change is None:
        missing["tax_change_this_year"] = (
            tax.reason if tax is not None and tax.reason else "the tax isn't computed"
        )
    else:
        values["tax_change_this_year"] = money(change)

    return Figures(currency, values, missing, accounts)


def view(figures: Figures) -> dict[str, str | int | bool | None]:
    """Every figure as JSON-ready data, in `FIGURES`' order: amounts, months
    and rates as decimal strings, counts as whole numbers, missing as null.
    `account_lowest` is a principle's own and is not listed here."""
    out: dict[str, str | int | bool | None] = {}
    for spec in FIGURES:
        if spec.name == "account_lowest":
            continue
        out[spec.name] = value_text(spec.name, figures.values.get(spec.name))
    return out


def value_text(name: str, value: Value | None) -> str | int | bool | None:
    """One figure's value as JSON-ready data."""
    if value is None or isinstance(value, bool):
        return value
    spec = BY_NAME[name]
    if spec.kind == "count":
        return int(value)
    if spec.kind == "rate":
        # Without trailing zeros, and without `normalize`, which rounds to
        # the caller's decimal context.
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return "0" if text in ("", "-0") else text
    return format(value, "f")


def specs_view() -> list[dict[str, str]]:
    """The figure set, documented: what an agent reads before writing a check."""
    return [
        {
            "name": f.name,
            "kind": f.kind,
            "unit": f.unit,
            "terms": f.terms,
            "group": f.group,
            "description": f.description,
        }
        for f in FIGURES
    ]
