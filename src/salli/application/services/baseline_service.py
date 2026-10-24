"""
BaselineService — gathers what the baseline is built from (domain/baseline)
and builds it, as of a day.

One read, many uses: FI, insights' cash forecast and safe-to-spend, the debt
plan and `GET /v1/baseline` all start from `build`, so they agree about what
a user earns, spends, owns and owes. Everything here reads; nothing writes.

The as-of date is the caller's, or today by this service's clock (injectable,
for tests and for replaying a past day). What is dated after it is not read:
balances are summed to it, entries end at it, and the published exchange
rates are the ones for it.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from salli.application.fx import published_rate
from salli.application.market_data import symbol_key
from salli.application.ports import FxRatePort
from salli.application.services.portfolio_service import history
from salli.application.services.tax_service import ADD_RULES
from salli.domain.baseline import (
    Baseline,
    BaselineInputs,
    DeclaredDebt,
    HoldingInputs,
    Rate,
    TaxInputs,
    TaxRules,
    Worth,
    build,
    timelines,
    worth_by_day,
)
from salli.domain.baseline.models import RuleSetRef
from salli.domain.currency import quantize
from salli.domain.fi.assumptions import (
    OwnAssumptions,
    assumptions_dict,
    rate_text,
)
from salli.domain.jurisdiction import country_phrase
from salli.domain.money import from_minor
from salli.domain.portfolio.valuation import Close
from salli.domain.reports.forecast import Flow
from salli.domain.taxrules.inputs import dates_needing_rates, role_postings
from salli.domain.taxrules.schema import RuleSet

#: How far back the rhythms the cash timeline projects are looked for: a
#: yearly payment's last three charges, and their slack.
RECURRING_DAYS = 2 * 366 + 30

#: The monthly timeline's horizon when none is asked for.
DEFAULT_HORIZON_YEARS = 30


async def statement_accounts(uow: Any, user_id: str) -> frozenset[str]:
    """Accounts a statement or a bank feed is imported into."""
    fed: set[str] = set()
    for statement in await uow.statements.list_statements(user_id, 1000):
        if statement.get("account_id"):
            fed.add(statement["account_id"])
    for connection in await uow.bank_connections.list(user_id):
        fed |= {a["account_id"] for a in connection.get("accounts", []) if a["account_id"]}
    return frozenset(fed)


def declared_debts(rows: Iterable[dict[str, Any]], currency: str) -> list[DeclaredDebt]:
    """The debts table's active rows, in the base currency."""
    return [
        DeclaredDebt(
            id=str(row["id"]),
            name=row["name"],
            principal=from_minor(row["principal_minor"], currency),
            apr=Decimal(str(row["apr"])),
            minimum_payment=from_minor(row["minimum_payment_minor"], currency),
            account_id=row.get("account_id") or None,
        )
        for row in rows
        if row.get("is_active", True)
    ]


def covering_rule_sets(
    rows: Iterable[dict[str, Any]], residency: str | None, as_of: dt.date
) -> list[RuleSetRef]:
    """The active rule set versions in the user's tax residency whose year
    covers `as_of` (usually one; a region's and the nation's may both)."""
    if not residency:
        return []
    found: list[RuleSetRef] = []
    for row in rows:
        version: dict[str, Any] = row.get("version") or {}
        content: dict[str, Any] = version.get("content") or {}
        year: dict[str, Any] = content.get("year") or {}
        if row.get("country") != residency or not year:
            continue
        try:
            start = dt.date.fromisoformat(str(year["start"]))
            end = dt.date.fromisoformat(str(year["end"]))
        except (KeyError, ValueError):
            continue
        if start <= as_of <= end:
            region: str | None = row.get("region")
            found.append(
                RuleSetRef(
                    country=str(row["country"]),
                    region=region,
                    year=str(row.get("year_label") or year.get("label") or ""),
                    rule_set_id=str(row["id"]),
                    version=int(version["version"]),
                    content_hash=str(version["content_hash"]),
                )
            )
    return found


def holding_inputs(
    holdings: Iterable[dict[str, Any]],
    transactions: Iterable[dict[str, Any]],
    prices: Iterable[dict[str, Any]],
    base: str,
    as_of: dt.date,
) -> list[HoldingInputs]:
    """Each of the user's holdings (sold ones too) with its transactions and
    the closes recorded for its symbol in its currency, both dated on or
    before `as_of`: what the baseline values it from. Its symbol and name
    are the person's own."""
    rows: dict[str, list[dict[str, Any]]] = {}
    for row in transactions:
        rows.setdefault(row["holding_id"], []).append(row)
    quotes = list(prices)
    out: list[HoldingInputs] = []
    for h in holdings:
        currency = str(h["currency"])
        key = symbol_key(str(h["symbol"]))
        mine = [t for t in history(rows.get(h["id"], []), currency) if t.on <= as_of]
        closes = [
            Close(dt.date.fromisoformat(q["price_date"]), Decimal(q["close"]), str(q["source"]))
            for q in quotes
            if symbol_key(str(q["symbol"])) == key
            and q["currency"] == currency
            and q["price_date"] <= as_of.isoformat()
        ]
        out.append(
            HoldingInputs(
                holding_id=str(h["id"]),
                symbol=str(h["symbol"]),
                name=str(h["name"]),
                currency=currency,
                account_id=h.get("account_id") or None,
                transactions=tuple(mine),
                closes=tuple(sorted(closes, key=lambda c: c.on)),
                declared_value=from_minor(h.get("current_value_minor") or 0, base),
                is_active=bool(h.get("is_active", True)),
            )
        )
    return out


def _ref(row: dict[str, Any], version: dict[str, Any], year: dict[str, Any]) -> RuleSetRef:
    return RuleSetRef(
        country=str(row["country"]),
        region=row.get("region"),
        year=str(row.get("year_label") or year.get("label") or ""),
        rule_set_id=str(row["id"]),
        version=int(version["version"]),
        content_hash=str(version["content_hash"]),
    )


def tax_rules(
    rows: Iterable[dict[str, Any]], residency: str | None, as_of: dt.date
) -> list[TaxRules]:
    """The active rule set versions in the user's tax residency a scenario's
    tax is computed with: every one whose year ends on or after the as-of
    date, and the latest (by its year's start) of those that ended before
    it, which later years carry forward when none of their own covers them.
    Only active versions: a draft never computes."""
    if not residency:
        return []
    found: list[TaxRules] = []
    for row in rows:
        version: dict[str, Any] = row.get("version") or {}
        if row.get("country") != residency or not version.get("content_hash"):
            continue
        try:
            document = RuleSet.model_validate(version.get("content") or {})
        except ValidationError:
            continue
        found.append(TaxRules(_ref(row, version, {"label": document.year.label}), document))
    ended = [r for r in found if r.end < as_of]
    latest = max((r.start for r in ended), default=None)
    return sorted(
        (r for r in found if r.end >= as_of or r.start == latest),
        key=lambda r: (r.start, r.ref.region or "", r.ref.rule_set_id),
    )


def no_tax_rules(residency: str | None, sets: Iterable[dict[str, Any]]) -> str:
    """Why no active rules compute the user's tax, and what to do: the
    words `TaxService` uses (`NoTaxRulesError`)."""
    if not residency:
        return (
            "Salli doesn't know where you're taxed. Set your tax residency "
            "(`salli profile set --tax-residency <country>`), or name the country. " + ADD_RULES
        )
    place = country_phrase(residency)
    ours = [s for s in sets if s.get("country") == residency]
    if ours:
        names = ", ".join(str(s.get("name")) for s in ours)
        return (
            f"You have tax rules for {place} ({names}), but none is active yet. Review and "
            "activate one yourself: `salli tax rules activate <set>`."
        )
    return f"You have no tax rules for {place}. " + ADD_RULES


def _money(value: Decimal | None, currency: str) -> str | None:
    return None if value is None else str(quantize(value, currency, strict=False))


def _ratio(value: Decimal | None) -> str | None:
    return None if value is None else str(value.quantize(Decimal("0.0001")))


class BaselineService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        fx: FxRatePort | None = None,
        today: Callable[[], dt.date] = dt.date.today,
    ) -> None:
        self._uow_factory = uow_factory
        self._fx = fx
        self._today = today

    def today(self) -> dt.date:
        return self._today()

    async def build(self, user_id: str, as_of: dt.date | None = None) -> Baseline:
        """The user's baseline as of `as_of` (today when None)."""
        as_of = as_of or self._today()
        day = as_of.isoformat()
        since = (as_of - dt.timedelta(days=RECURRING_DAYS)).isoformat()
        async with self._uow_factory() as uow:
            base = await uow.user_profiles.base_currency(user_id)
            profile: dict[str, Any] = await uow.user_profiles.get(user_id) or {}
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            money = [a for a in accounts if a.type in ("asset", "liability")]
            totals = await uow.ledger.posting_totals(user_id, [a.id for a in money], to_date=day)
            entries = await uow.ledger.get_entries(user_id, from_date=since, to_date=day)
            first_flow = await uow.ledger.first_flow_date(user_id, to_date=day)
            debts = await uow.debts.list(user_id, active_only=True)
            subscriptions = await uow.recurring_subscriptions.list(user_id, active_only=True)
            fed = await statement_accounts(uow, user_id)
            active_rules = await uow.tax_rule_sets.active_versions(user_id)
            residency: str | None = profile.get("tax_residency") or None
            rules = tax_rules(active_rules, residency, as_of)
            sets: list[dict[str, Any]] = [] if rules else await uow.tax_rule_sets.list_sets(user_id)
            claims = goal_claims(
                await uow.goals.list(user_id, active_only=True),
                await uow.goals.list_allocations(user_id),
                base,
            )
            held = await uow.holdings.list(user_id, active_only=False)
            holdings = (
                holding_inputs(
                    held,
                    await uow.holding_transactions.list(user_id),
                    await uow.holding_prices.list(user_id, None, None, day),
                    base,
                    as_of,
                )
                if held
                else []
            )

        currencies = {a.currency for a in money} | {h.currency for h in holdings}
        rates = await self._rates(currencies - {base}, base, day)

        tax = TaxInputs(
            residency=residency,
            rules=rules,
            unavailable=None if rules else no_tax_rules(residency, sets),
            rates=await self._tax_rates(rules, accounts, entries, base, as_of),
        )
        return build(
            BaselineInputs(
                as_of=as_of,
                currency=base,
                accounts=accounts,
                totals=totals,
                rates=rates,
                entries=entries,
                first_flow=first_flow,
                debts=declared_debts(debts, base),
                subscriptions=subscriptions,
                statement_accounts=fed,
                own_assumptions=OwnAssumptions.from_stored(profile.get("fi_assumptions")),
                goal_claims=claims,
                rule_sets=covering_rule_sets(active_rules, residency, as_of),
                tax=tax,
                holdings=holdings,
            )
        )

    async def worth(self, user_id: str, days: Sequence[dt.date]) -> list[Worth]:
        """What is owned and owed as of each of `days` (ascending), as the
        baseline as of that day counts it (`build.worth`): the ledger summed
        once to the first day and its entries read from there to the last,
        and each currency's published rate for each day asked for once."""
        first, last = days[0], days[-1]
        async with self._uow_factory() as uow:
            base = await uow.user_profiles.base_currency(user_id)
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            money = [a for a in accounts if a.type in ("asset", "liability")]
            opening = await uow.ledger.posting_totals(
                user_id, [a.id for a in money], to_date=first.isoformat()
            )
            entries = await uow.ledger.get_entries(
                user_id,
                from_date=(first + dt.timedelta(days=1)).isoformat(),
                to_date=last.isoformat(),
            )
            debts = declared_debts(await uow.debts.list(user_id, active_only=True), base)
        foreign = {a.currency for a in money} - {base}
        rates = {
            day: await self._rates(foreign, base, day)
            for day in dict.fromkeys(d.isoformat() for d in days)
        }
        return worth_by_day(days, base, accounts, opening, entries, rates, debts)

    async def _rates(self, currencies: Iterable[str], base: str, day: str) -> dict[str, Rate]:
        """Each currency's published rate into `base` for `day`, or a Rate of
        None when no source has one."""
        rates: dict[str, Rate] = {}
        for currency in sorted(currencies):
            quote = await published_rate(self._fx, currency, base, day)
            rates[currency] = (
                Rate(currency, None, None, None)
                if quote is None
                else Rate(currency, quote.rate, quote.source, quote.as_of)
            )
        return rates

    async def _tax_rates(
        self,
        rules: Sequence[TaxRules],
        accounts: Sequence[Any],
        entries: Sequence[Any],
        base: str,
        as_of: dt.date,
    ) -> dict[str, dict[str, Decimal]]:
        """The published rates from the base currency into each rules'
        currency other than it: the as-of date's (for projected and tagged
        amounts), and each day a posting in the year before the as-of date
        needs one (its actuals). A rate no source has is left out: the year
        it is needed for is then not computed, never at a guessed rate."""
        out: dict[str, dict[str, Decimal]] = {}
        roles = sorted({r.key for rules_ in rules for r in rules_.document.roles})
        since = as_of - dt.timedelta(days=366)
        postings = role_postings(entries, accounts, roles, since, as_of) if roles else []
        for currency in sorted({r.currency for r in rules} - {base}):
            days = [as_of.isoformat(), *dates_needing_rates(postings, base, currency)]
            found: dict[str, Decimal] = {}
            for day in dict.fromkeys(days):
                quote = await published_rate(self._fx, base, currency, day)
                if quote is not None:
                    found[day] = quote.rate
            out[currency] = found
        return out

    async def get_baseline(
        self,
        user_id: str,
        as_of: dt.date | None = None,
        horizon_years: int = DEFAULT_HORIZON_YEARS,
        *,
        daily: bool = True,
        changes: Sequence[Flow] = (),
    ) -> dict[str, Any]:
        """The baseline and its two timelines, as the API and MCP serve them.
        `daily=False` leaves the day-by-day series out (its month-ends and
        lowest point stay)."""
        timelines.horizon_months(horizon_years)  # refuse a bad horizon before reading
        baseline = await self.build(user_id, as_of)
        return view(baseline, horizon_years, daily=daily, changes=changes)


def view(
    baseline: Baseline,
    horizon_years: int,
    *,
    daily: bool = True,
    changes: Sequence[Flow] = (),
) -> dict[str, Any]:
    """The baseline as JSON-ready data: money as strings in each currency's
    precision, rates and ratios as decimal strings."""
    cur = baseline.currency
    cash = timelines.daily(baseline, changes)
    monthly = timelines.monthly(baseline, horizon_years, changes)
    flows = baseline.flows
    outlook = {o.debt_id: o for o in monthly.debts}
    result = cash.forecast
    return {
        "as_of": baseline.as_of.isoformat(),
        "currency": cur,
        "months_observed": list(flows.months),
        "flows": {
            "monthly_income": _money(flows.income, cur),
            "monthly_expenses": _money(flows.expenses, cur),
            "monthly_surplus": _money(flows.surplus, cur),
            "savings_rate": _ratio(flows.savings_rate),
            "essential_monthly": _money(flows.essential, cur),
            "need_coverage": _ratio(flows.need_coverage),
            "by_month": [
                {
                    "month": m.month,
                    "income": _money(m.income, cur),
                    "expenses": _money(m.expenses, cur),
                    "net": _money(m.net, cur),
                    "essential": _money(m.essential, cur),
                }
                for m in flows.by_month
            ],
        },
        "rates": [
            {
                "currency": r.currency,
                "rate": None if r.rate is None else rate_text(r.rate),
                "source": r.source,
                "as_of": r.as_of,
            }
            for r in baseline.rates
        ],
        "balances": [
            {
                "account_id": b.account_id,
                "code": b.code,
                "name": b.name,
                "role": b.role,
                "currency": b.currency,
                "amount": _money(b.amount, b.currency),
                "value": _money(b.value, cur),
                "in_cash": b.in_cash,
                "debt_id": b.debt_id,
            }
            for b in baseline.balances
        ],
        "totals": {
            "cash": _money(baseline.cash, cur),
            "savings": _money(baseline.savings, cur),
            "liquid": _money(baseline.liquid, cur),
            "investments": _money(baseline.investments, cur),
            "other_assets": _money(baseline.other_assets, cur),
            "debts": _money(baseline.debts_owed, cur),
            "other_liabilities": _money(baseline.other_liabilities, cur),
            "total_assets": _money(baseline.total_assets, cur),
            "total_liabilities": _money(baseline.total_liabilities, cur),
            "net_worth": _money(baseline.net_worth, cur),
        },
        "debts": [
            {
                "debt_id": d.debt_id,
                "name": d.name,
                "source": d.source,
                "account_id": d.account_id,
                "balance": _money(d.balance, cur),
                "apr": rate_text(d.apr),
                "minimum_payment": _money(d.minimum_payment, cur),
                "already_paid": _money(d.already_paid, cur),
                "paid_off": outlook[d.debt_id].paid_off,
                "total_interest": _money(outlook[d.debt_id].total_interest, cur),
            }
            for d in baseline.debts
        ],
        "debt_free": monthly.debt_free,
        "cash": {
            "start": result.start,
            "end": result.end,
            "today": _money(result.today, cur),
            "lowest": _money(result.lowest, cur),
            "lowest_date": result.lowest_date,
            "month_ends": [
                {
                    "month": month,
                    "cash": _money(value, cur),
                    "unscheduled": _money(rest, cur),
                    "invested": _money(invested, cur),
                }
                for (month, value), (_, rest), (_, invested) in zip(
                    cash.month_ends, cash.unscheduled, cash.invested, strict=True
                )
            ],
            "daily": [{"date": d, "balance": _money(v, cur)} for d, v in result.daily]
            if daily
            else None,
        },
        "monthly": {
            "horizon_years": horizon_years,
            "real_return": rate_text(monthly.real_return),
            "surplus_invested": rate_text(monthly.surplus_invested),
            "inflation": None if baseline.inflation is None else rate_text(baseline.inflation),
            "points": [
                {
                    "month": p.month,
                    "date": p.date,
                    "cash": _money(p.cash, cur),
                    "investments": _money(p.investments, cur),
                    "other_assets": _money(p.other_assets, cur),
                    "debts": _money(p.debts, cur),
                    "other_liabilities": _money(p.other_liabilities, cur),
                    "net_worth": _money(p.net_worth, cur),
                }
                for p in monthly.points
            ],
        },
        "assumptions": assumptions_dict(baseline.assumptions),
        "placeholders": list(baseline.placeholders),
        "rule_sets": [
            {
                "country": r.country,
                "region": r.region,
                "year": r.year,
                "rule_set_id": r.rule_set_id,
                "version": r.version,
                "content_hash": r.content_hash,
            }
            for r in baseline.rule_sets
        ],
        "fingerprint": baseline.fingerprint,
        "notes": list(dict.fromkeys([*baseline.notes, *cash.notes, *monthly.notes])),
    }


def goal_claims(
    goals: Sequence[Mapping[str, Any]], allocations: Sequence[Mapping[str, Any]], base: str
) -> dict[str, Decimal]:
    """What active goals claim of each account, in the base currency. A claim
    from a goal that is gone or archived holds nothing back."""
    active = {g["id"] for g in goals}
    out: dict[str, Decimal] = {}
    for a in allocations:
        if a["goal_id"] in active:
            amount = from_minor(a["allocated_minor"], base)
            out[a["account_id"]] = out.get(a["account_id"], Decimal(0)) + amount
    return out
