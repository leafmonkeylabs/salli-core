"""
The baseline's shapes: what goes in (`BaselineInputs`) and what comes out
(`Baseline`). Frozen dataclasses, Decimal money. No I/O.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from salli.domain.accounting.ledger import owned_and_owed
from salli.domain.accounting.models import Account, AssetRole, StoredJournalEntry
from salli.domain.fi.assumptions import FiAssumptions, OwnAssumptions, StrategyFigures
from salli.domain.reports.forecast import DeclaredCharge
from salli.domain.reports.insights import Recurring
from salli.domain.taxrules.inputs import RolePosting
from salli.domain.taxrules.schema import RuleSet

#: What a balance is, to the baseline: an asset account's own role, or a
#: liability.
Role = Literal["cash", "investment", "other_asset", "liability"]

ROLE_OF: dict[AssetRole, Role] = {
    "cash": "cash",
    "investment": "investment",
    "other": "other_asset",
}

#: The months of history the averages look back over, at most.
MONTHS_OBSERVED = 12


@dataclass(frozen=True)
class Rate:
    """The published rate into the base currency for the as-of date, as the
    FX port gave it (the convention tax uses too)."""

    currency: str
    #: Units of the base currency per unit; None when no source had one.
    rate: Decimal | None
    #: Who published it ("ecb", ...); None when missing.
    source: str | None
    #: The day the rate is for: a Sunday's rate is Friday's. None when missing.
    as_of: str | None


@dataclass(frozen=True)
class Balance:
    """One account's balance on the as-of date."""

    account_id: str
    code: str
    name: str
    role: Role
    currency: str
    #: Signed, debits positive (what is owed is negative), in the account's
    #: own currency; None when it can't be known.
    amount: Decimal | None
    #: The same in the base currency, at the as-of rate; None without one.
    value: Decimal | None
    is_active: bool
    #: Counted as cash: in the daily cash timeline and the monthly
    #: timeline's cash (`forecast.cash_accounts`).
    in_cash: bool
    #: The declared debt this liability account holds, if any.
    debt_id: str | None = None

    @property
    def owned(self) -> Decimal:
        """What is owned here, in the base currency (an overdrawn account owns
        nothing; an overpaid card owns its credit)."""
        return owned_and_owed("asset", self.value or Decimal(0))[0]

    @property
    def owed(self) -> Decimal:
        """What is owed here, in the base currency, as a positive amount."""
        return owned_and_owed("asset", self.value or Decimal(0))[1]


@dataclass(frozen=True)
class MonthFlow:
    """One calendar month's money in and out, in the base currency, signed
    amounts netted (a reversal cancels what it reverses)."""

    month: str
    income: Decimal
    expenses: Decimal
    #: Income less expenses.
    net: Decimal
    #: Expenses tagged `need: essential`.
    essential: Decimal
    #: Expenses tagged on the need axis at all.
    classified: Decimal


@dataclass(frozen=True)
class Flows:
    """Income and expenses under the one definition: netted per calendar
    month, averaged over the full months observed."""

    #: The full calendar months averaged over, oldest first: at most twelve,
    #: before the as-of month, from the month of the first income or expense.
    months: tuple[str, ...]
    by_month: tuple[MonthFlow, ...]
    #: Monthly averages (exact; rounded only where shown).
    income: Decimal
    expenses: Decimal
    #: income − expenses.
    surplus: Decimal
    #: surplus / income; None without income.
    savings_rate: Decimal | None
    #: Average essential spending; None while no spending in these months
    #: carries a need tag.
    essential: Decimal | None
    #: The share of spending that carries a need tag; None without spending.
    need_coverage: Decimal | None


@dataclass(frozen=True)
class DeclaredDebt:
    """A debt as the user declared it (the debts table), in the base currency."""

    id: str
    name: str
    principal: Decimal
    apr: Decimal
    minimum_payment: Decimal
    #: The liability account that holds it in the ledger, if linked.
    account_id: str | None = None


@dataclass(frozen=True)
class BaselineDebt:
    """A debt with terms, counted once; or a loan a scenario takes out."""

    debt_id: str
    name: str
    apr: Decimal
    minimum_payment: Decimal
    #: What is owed on the as-of date: the linked account's balance, or the
    #: declared principal. A scenario's loan: what it borrows.
    balance: Decimal
    #: "account" when the balance is the linked ledger account's, "declared"
    #: when the ledger doesn't hold it, "scenario" for a loan a scenario
    #: takes out.
    source: Literal["account", "declared", "scenario"]
    account_id: str | None
    #: The part of each month's payment the average surplus already pays:
    #: a linked debt's interest this month (its principal moves between
    #: accounts, so isn't spending); an unlinked debt's minimum payment (its
    #: payments were spending). The rest of its scheduled payment comes out
    #: of the regular surplus; once the debt is paid off, the payment is
    #: freed and joins it (`timelines.cash_plan`). Nothing, for a scenario's
    #: loan.
    already_paid: Decimal
    #: Paid on top of the minimum each month, from the first payment: out of
    #: cash, not the regular surplus.
    extra_payment: Decimal = Decimal(0)
    #: The calendar month ("YYYY-MM") a scenario's loan is taken out, owed
    #: from that month's end; None for a debt owed on the as-of date.
    opened: str | None = None
    #: The month of the first payment; None: the month after the as-of month.
    first_payment: str | None = None
    #: A loan's term in months: its last payment clears it.
    term_months: int | None = None


@dataclass(frozen=True)
class RuleSetRef:
    """An active tax rule set version whose year covers the as-of date, in
    the user's tax residency: which rules apply, recorded with every figure
    that rests on the baseline."""

    country: str
    region: str | None
    year: str
    rule_set_id: str
    version: int
    content_hash: str


@dataclass(frozen=True)
class TaxRules:
    """An active tax rule set version in the user's tax residency: which it
    is, and its document (the rules a scenario's tax is computed with)."""

    ref: RuleSetRef
    document: RuleSet

    @property
    def start(self) -> dt.date:
        return self.document.year.start

    @property
    def end(self) -> dt.date:
        return self.document.year.end

    @property
    def currency(self) -> str:
        return self.document.currency


@dataclass(frozen=True)
class TaxInputs:
    """What a scenario's tax is computed from, beyond the ledger: the active
    rule set versions in the user's tax residency whose year ends on or
    after the as-of date (and the latest one before it, which later years
    carry forward), why there are none when there are none, and the
    published rates from the base currency into a rule set's currency that
    the application fetched (by currency, then day: the as-of date's, and
    each day a posting in the as-of tax year needs one). Only active rules
    are ever gathered: a draft never computes."""

    residency: str | None = None
    rules: Sequence[TaxRules] = ()
    #: Why no rules compute the user's tax, in Salli's words and saying
    #: what to do (as `NoTaxRulesError` says it); None when some do.
    unavailable: str | None = None
    rates: Mapping[str, Mapping[str, Decimal]] = field(
        default_factory=dict[str, Mapping[str, Decimal]]
    )


@dataclass(frozen=True)
class BaselineTax:
    """What a scenario's tax starts from: the active rules (`TaxInputs`),
    the postings on accounts with a tax role those rules declare (to the
    as-of date, in each account's normal-balance direction), and each
    role's monthly average over the months the baseline observes, in the
    base currency (`domain/scenarios/tax.py` projects each tax year from
    them)."""

    residency: str | None = None
    rules: tuple[TaxRules, ...] = ()
    unavailable: str | None = None
    rates: Mapping[str, Mapping[str, Decimal]] = field(
        default_factory=dict[str, Mapping[str, Decimal]]
    )
    postings: tuple[RolePosting, ...] = ()
    #: Each role's postings netted per calendar month over the months
    #: observed (`Flows.months`), averaged, in the base currency at the
    #: rates they were booked at; zero for a role with none.
    average: Mapping[str, Decimal] = field(default_factory=dict[str, Decimal])
    #: Each account's tax role, by account id (a stopped flow's role).
    account_roles: Mapping[str, str] = field(default_factory=dict[str, str])
    #: Evaluations already made, keyed by their inputs: a cache, never
    #: part of what the baseline is.
    memo: dict[Any, Any] = field(
        default_factory=dict[Any, Any], compare=False, hash=False, repr=False
    )


@dataclass(frozen=True)
class BaselineInputs:
    """Everything the baseline is built from, gathered by the application."""

    as_of: dt.date
    currency: str
    #: Every account, closed ones included.
    accounts: Sequence[Account]
    #: (account id, currency, signed total in that currency, signed total in
    #: the base currency) for each asset and liability account, from every
    #: entry on or before the as-of date (`LedgerRepository.posting_totals`).
    totals: Sequence[tuple[str, str, Decimal, Decimal]]
    #: The published rate for the as-of date, for each currency an asset or
    #: liability account is held in other than the base.
    rates: Mapping[str, Rate]
    #: Entries from about two years before the as-of date to it: the months
    #: observed, and the rhythms the cash timeline projects.
    entries: Sequence[StoredJournalEntry]
    #: The date of the first entry touching an income or expense account, on
    #: or before the as-of date.
    first_flow: str | None
    debts: Sequence[DeclaredDebt]
    #: Active declared subscriptions, as the repository keeps them.
    subscriptions: Sequence[Mapping[str, object]] = ()
    #: Accounts a statement or a bank feed is imported into.
    statement_accounts: frozenset[str] = frozenset()
    own_assumptions: OwnAssumptions = field(default_factory=OwnAssumptions)
    strategy: StrategyFigures | None = None
    #: The active tax rule sets whose year covers the as-of date.
    rule_sets: Sequence[RuleSetRef] = ()
    #: What a scenario's tax is computed from.
    tax: TaxInputs = field(default_factory=TaxInputs)


@dataclass(frozen=True)
class Baseline:
    """A user's money as of a day: balances by role, the rates used, income
    and expenses under one definition, what keeps happening, debts with
    terms, and the assumptions planning rests on."""

    as_of: dt.date
    currency: str
    balances: tuple[Balance, ...]
    rates: tuple[Rate, ...]
    flows: Flows
    debts: tuple[BaselineDebt, ...]
    assumptions: FiAssumptions
    #: What the ledger says keeps happening (both directions), and the
    #: declared subscription that covers each, if any (same order).
    recurring: tuple[Recurring, ...]
    covered_by: tuple[str | None, ...]
    #: Declared subscriptions no rhythm in the ledger shows, in the base currency.
    charges: tuple[DeclaredCharge, ...]
    #: What was left out, and why.
    notes: tuple[str, ...]
    first_flow: str | None
    #: The notes about the cash accounts and what moves them: what the cash
    #: forecast says alongside its figures.
    cash_notes: tuple[str, ...] = ()
    #: The date of the newest entry on or before the as-of date (within the
    #: two years read), or None: how fresh the picture is.
    latest_entry: str | None = None
    #: The FIRE strategy's figures, when there is one (its version, and the
    #: monthly spending it aims at, if it names one).
    strategy: StrategyFigures | None = None
    #: The active tax rule sets whose year covers the as-of date.
    rule_sets: tuple[RuleSetRef, ...] = ()
    #: What a scenario's tax starts from (`BaselineTax`).
    tax: BaselineTax = field(default_factory=BaselineTax)
    #: A content hash of everything the baseline was built from
    #: (`fingerprint.of`): the same inputs, the same baseline.
    fingerprint: str = ""

    # ── Totals, in the base currency ─────────────────────────────────────────

    def _sum(self, role: Role) -> Decimal:
        return sum(
            (b.value for b in self.balances if b.role == role and b.value is not None),
            Decimal(0),
        )

    @property
    def cash_accounts(self) -> dict[str, tuple[str, Decimal]]:
        """The cash accounts (id → their currency and balance in it): what the
        daily cash timeline carries."""
        return {
            b.account_id: (b.currency, b.amount)
            for b in self.balances
            if b.in_cash and b.amount is not None
        }

    @property
    def cash(self) -> Decimal:
        """The cash accounts together, signed (a card's balance owed counts
        against them), at the as-of rates."""
        return sum(
            (b.value for b in self.balances if b.in_cash and b.value is not None), Decimal(0)
        )

    @property
    def liquid(self) -> Decimal:
        """What the cash-role accounts own: the emergency fund's money."""
        return sum((b.owned for b in self.balances if b.role == "cash"), Decimal(0))

    @property
    def investments(self) -> Decimal:
        return self._sum("investment")

    @property
    def other_assets(self) -> Decimal:
        return self._sum("other_asset")

    @property
    def debts_owed(self) -> Decimal:
        """What the debts with terms owe."""
        return sum((d.balance for d in self.debts), Decimal(0))

    @property
    def other_liabilities(self) -> Decimal:
        """What liabilities without terms owe, as a positive amount: the
        liability accounts that are neither cash nor a debt's (and anything a
        linked account holds beyond its debt, which counts against this)."""
        held = sum(
            (
                -b.value
                for b in self.balances
                if b.role == "liability" and not b.in_cash and b.value is not None
            ),
            Decimal(0),
        )
        linked = sum((d.balance for d in self.debts if d.source == "account"), Decimal(0))
        return held - linked

    @property
    def total_assets(self) -> Decimal:
        """Everything owned, each account judged on its own sign."""
        return sum((b.owned for b in self.balances), Decimal(0))

    @property
    def total_liabilities(self) -> Decimal:
        """Everything owed: each account judged on its own sign, and the
        debts the ledger doesn't hold."""
        declared = sum((d.balance for d in self.debts if d.source == "declared"), Decimal(0))
        return sum((b.owed for b in self.balances), Decimal(0)) + declared

    @property
    def net_worth(self) -> Decimal:
        return self.total_assets - self.total_liabilities

    @property
    def inflation(self) -> Decimal | None:
        return self.assumptions.inflation.value if self.assumptions.inflation else None

    @property
    def surplus_invested(self) -> Decimal:
        """The share (0 to 1) of each month's regular surplus that goes into
        investments (`timelines.cash_plan`); the user's, or the placeholder."""
        return self.assumptions.surplus_invested.value

    @property
    def placeholders(self) -> tuple[str, ...]:
        """Which assumptions are placeholders: FI's, and inflation when the
        user set none (nominal amounts then keep their real value)."""
        return (*self.assumptions.placeholders, *(("inflation",) if self.inflation is None else ()))
