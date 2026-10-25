"""
PortfolioService — investment holdings, their transactions and lots, and the
allocation/rebalancing/ROI summary.

A holding has a currency of its own (a US fund in a euro ledger is in USD)
and a history of transactions: buys, sales, dividends, interest, splits and
transfers in. Its lots, sales and income are worked out from that history by
the pure domain (domain/portfolio/lots.py). Every transaction but a split
carries the rate into the owner's base currency on its date, the one given or
the published one, and is refused when there is neither (application/fx.py),
exactly as a posting in the ledger is.

A holding without transactions keeps the two figures the user declared, cost
basis and current value, in the base currency. Declaring figures for a
holding in another currency would need a rate with no date to take it on, so
such a holding is tracked by its transactions instead.

Every change to a holding's history is checked by replaying the whole of it:
a sale of more than was held, or of a lot that was not, is refused before it
is stored, and so is an edit or deletion that would make a later sale
impossible.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Context, Decimal, InvalidOperation, localcontext
from typing import Any, cast

from salli.application.fx import rate_to_base
from salli.application.market_data import StoredPriceHistory, symbol_key
from salli.application.ownership import require_own_accounts
from salli.application.ports import FxRatePort, FxUnavailableError
from salli.domain.currency import normalize_currency, quantize, quantum
from salli.domain.fi import cma
from salli.domain.money import from_minor, to_minor
from salli.domain.portfolio import engine, performance, risk
from salli.domain.portfolio.lots import (
    COST_METHODS,
    EXACT,
    INCOME,
    ONE,
    PLACES,
    ZERO,
    CostMethod,
    Kind,
    LotPick,
    Transaction,
    TransactionError,
    check_amount,
    check_number,
    ordered,
    plain,
    replay,
    validate,
)
from salli.domain.portfolio.models import Holding
from salli.domain.portfolio.policy import check_allocation
from salli.domain.portfolio.returns import RATE, annualised
from salli.domain.portfolio.valuation import Close, Pricing, Valuation

_STEP = Decimal(1).scaleb(-PLACES)
_NUMBER_LIMIT = Decimal(10) ** 20

# What each kind of transaction needs, and what else it may have. Anything else
# is refused rather than ignored: a price on a dividend is a client's mistake.
_FIELDS: dict[Kind, tuple[frozenset[str], frozenset[str]]] = {
    Kind.BUY: (frozenset({"quantity", "price"}), frozenset({"fees", "fx_rate"})),
    Kind.SELL: (frozenset({"quantity", "price"}), frozenset({"fees", "fx_rate", "lots"})),
    Kind.TRANSFER_IN: (frozenset({"quantity", "amount"}), frozenset({"fx_rate"})),
    Kind.DIVIDEND: (frozenset({"amount"}), frozenset({"withholding_tax", "fx_rate"})),
    Kind.INTEREST: (frozenset({"amount"}), frozenset({"withholding_tax", "fx_rate"})),
    Kind.SPLIT: (frozenset({"ratio"}), frozenset()),
}
_COMMON = frozenset({"kind", "date", "note", "fx_rate_source"})


# ── Reading what a request or the CLI sent ────────────────────────────────────


def _decimal(name: str, value: object) -> Decimal:
    """A number as a request or the CLI gives it: a Decimal, an int, or a
    decimal string. Anything else, NaN and infinity included, is refused."""
    if isinstance(value, bool):
        raise TransactionError(f"{name} must be a decimal number, not {value!r}")
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int | float):
        number = Decimal(str(value))
    elif isinstance(value, str):
        try:
            number = Decimal(value.strip())
        except InvalidOperation:
            raise TransactionError(f"{name} must be a decimal number, not {value!r}") from None
    else:
        raise TransactionError(f"{name} must be a decimal number, not {value!r}")
    if not number.is_finite():
        raise TransactionError(f"{name} must be a decimal number, not {value!r}")
    # Nothing Salli keeps is this large, or this small but not zero; refused
    # here, before arithmetic on it could overflow.
    if number.copy_abs() >= _NUMBER_LIMIT or (number != 0 and number.adjusted() < -60):
        raise TransactionError(f"{name} is out of range: {value!r}")
    return number


def _date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise TransactionError(f"date must be YYYY-MM-DD, not {value!r}")


def _ratio(value: object) -> tuple[Decimal, Decimal]:
    """A split's ratio, "new:old" or just "new" (meaning new:1)."""
    to, _, from_ = str(value).strip().partition(":")
    return _decimal("ratio", to), (_decimal("ratio", from_) if from_ else ONE)


def _fields(data: dict[str, Any]) -> tuple[Kind, dict[str, Any]]:
    """The kind, and the fields given (not None), checked against what it takes."""
    try:
        kind = Kind(str(data.get("kind")))
    except ValueError:
        kinds = ", ".join(k.value for k in Kind)
        raise TransactionError(f"kind must be one of {kinds}, not {data.get('kind')!r}") from None
    given = {k: v for k, v in data.items() if v is not None and k != "kind"}
    if "date" not in given:
        raise TransactionError("A transaction needs a date")
    required, optional = _FIELDS[kind]
    missing = sorted(required - set(given))
    if missing:
        raise TransactionError(f"A {kind.value} needs {' and '.join(missing)}")
    extra = sorted(set(given) - required - optional - _COMMON)
    if extra:
        raise TransactionError(f"A {kind.value} has no {' or '.join(extra)}")
    if "fx_rate_source" in given and "fx_rate" not in given:
        raise TransactionError("fx_rate_source describes an fx_rate given with it")
    return kind, given


def _picks(value: object) -> list[dict[str, Any]]:
    """A sale's named lots, each {"lot_id", "quantity"}; none for anything else."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise TransactionError("lots must be a list of {lot_id, quantity}")
    picks: list[dict[str, Any]] = []
    for pick in cast(list[object], value):
        if not isinstance(pick, dict) or not {"lot_id", "quantity"} <= set(
            cast(dict[str, Any], pick)
        ):
            raise TransactionError("Each lot named is {lot_id, quantity}")
        picks.append(cast(dict[str, Any], pick))
    return picks


def _columns(
    kind: Kind, fields: dict[str, Any], currency: str, rate: Decimal, source: str | None
) -> dict[str, Any]:
    """The stored columns: money in minor units of the holding's currency
    (rounded HALF-UP, the money path's one rule), the rest exact."""

    def money(name: str) -> int | None:
        if name not in fields:
            return None
        amount = _decimal(name, fields[name])
        check_amount(name, amount.copy_abs())
        return to_minor(amount, currency)

    split_to, split_from = _ratio(fields["ratio"]) if kind is Kind.SPLIT else (None, None)
    return {
        "kind": kind.value,
        "transaction_date": _date(fields["date"]).isoformat(),
        "quantity": _decimal("quantity", fields["quantity"]) if "quantity" in fields else None,
        "price": _decimal("price", fields["price"]) if "price" in fields else None,
        "fees_minor": money("fees") or 0,
        "amount_minor": money("amount"),
        "withholding_tax_minor": money("withholding_tax") or 0,
        "split_to": split_to,
        "split_from": split_from,
        "lots": [
            {
                "lot_id": str(pick["lot_id"]),
                "quantity": plain(_decimal("a lot's quantity", pick["quantity"])),
            }
            for pick in _picks(fields.get("lots"))
        ],
        "fx_rate": rate,
        "fx_rate_source": source,
        "note": fields.get("note"),
    }


def _given(row: dict[str, Any], currency: str) -> dict[str, Any]:
    """A stored transaction as the fields a request would give for it (less
    its rate, which an update handles on its own)."""
    kind = Kind(row["kind"])
    fields: dict[str, Any] = {"date": row["transaction_date"], "note": row.get("note")}
    if kind in (Kind.BUY, Kind.SELL, Kind.TRANSFER_IN):
        fields["quantity"] = row["quantity"]
    if kind in (Kind.BUY, Kind.SELL):
        fields["price"] = row["price"]
        fields["fees"] = from_minor(row["fees_minor"], currency)
    if kind in INCOME or kind is Kind.TRANSFER_IN:
        fields["amount"] = from_minor(row["amount_minor"], currency)
    if kind in INCOME:
        fields["withholding_tax"] = from_minor(row["withholding_tax_minor"], currency)
    if kind is Kind.SELL and row.get("lots"):
        fields["lots"] = row["lots"]
    if kind is Kind.SPLIT:
        fields["ratio"] = f"{plain(row['split_to'])}:{plain(row['split_from'])}"
    return fields


# ── Stored rows ↔ the domain ──────────────────────────────────────────────────


def _transaction(row: dict[str, Any], currency: str, seq: int) -> Transaction:
    def money(column: str) -> Decimal:
        minor = row.get(column)
        return from_minor(minor, currency) if minor is not None else ZERO

    def number(column: str, default: Decimal = ZERO) -> Decimal:
        value = row.get(column)
        return Decimal(value) if value is not None else default

    return Transaction(
        id=row["id"],
        kind=Kind(row["kind"]),
        on=_date(row["transaction_date"]),
        quantity=number("quantity"),
        price=number("price"),
        fees=money("fees_minor"),
        amount=money("amount_minor"),
        withholding_tax=money("withholding_tax_minor"),
        split_to=number("split_to", ONE),
        split_from=number("split_from", ONE),
        lots=tuple(
            LotPick(str(pick["lot_id"]), Decimal(str(pick["quantity"])))
            for pick in _picks(row.get("lots"))
        ),
        fx_rate=number("fx_rate", ONE),
        seq=seq,
    )


def history(rows: Iterable[dict[str, Any]], currency: str) -> list[Transaction]:
    """Rows in the order they were recorded, as domain transactions; their
    position is the tie-break between transactions of one kind on one date."""
    return [_transaction(row, currency, seq) for seq, row in enumerate(rows)]


async def realised_gains(
    uow: Any, user_id: str, start: date, end: date
) -> list[tuple[str, Decimal]]:
    """Each sale of the user's holdings dated `start` to `end` (both
    included), and the gain it realised in the base currency (proceeds less
    fees less the consumed lots' cost, each at its day's rate): (date, gain),
    in date order, each holding replayed by its cost method (its own, else its
    rules', else fifo). What a rule set's `realised_gain` role is filled from."""
    rules = await rule_set_method(uow, user_id, end)
    holdings = await uow.holdings.list(user_id, active_only=False)
    rows = await uow.holding_transactions.list(user_id)
    gains: list[tuple[str, Decimal]] = []
    for holding in holdings:
        mine = [r for r in rows if r["holding_id"] == holding["id"]]
        if not mine:
            continue
        method = _cost_method(holding.get("cost_method")) or rules or "fifo"
        for sale in replay(history(mine, holding["currency"]), method=method).sales:
            if start <= sale.on <= end:
                gains.append((sale.on.isoformat(), sale.gain_base))
    return sorted(gains)


def _check(
    rows: Iterable[dict[str, Any]], currency: str, method: CostMethod = "fifo"
) -> list[Transaction]:
    """Refuse a history with a malformed transaction or one that cannot have
    happened. Returns it, as domain transactions."""
    transactions = history(rows, currency)
    for tx in transactions:
        validate(tx)
    replay(transactions, method=method)
    return transactions


async def rule_set_method(uow: Any, user_id: str, today: date) -> CostMethod | None:
    """The `cost_basis` of the active tax rule set in the user's residency
    whose year covers `today`, if it says one."""
    profile: dict[str, Any] = await uow.user_profiles.get(user_id) or {}
    residency = profile.get("tax_residency")
    if not residency:
        return None
    rows: list[dict[str, Any]] = await uow.tax_rule_sets.active_versions(user_id)
    for row in rows:
        version: dict[str, Any] = row.get("version") or {}
        content: dict[str, Any] = version.get("content") or {}
        year: dict[str, Any] = content.get("year") or {}
        if row.get("country") != residency or content.get("cost_basis") not in COST_METHODS:
            continue
        if str(year.get("start", "")) <= today.isoformat() <= str(year.get("end", "")):
            return cast(CostMethod, content["cost_basis"])
    return None


async def rule_set_terms(uow: Any, user_id: str, today: date) -> tuple[int | None, int | None]:
    """The active tax rules' `long_term_after_months` and `wash_sale_days`
    (the rule set in the user's residency whose year covers `today`), each
    None when they declare none."""
    profile: dict[str, Any] = await uow.user_profiles.get(user_id) or {}
    residency = profile.get("tax_residency")
    if not residency:
        return None, None
    for row in await uow.tax_rule_sets.active_versions(user_id):
        version: dict[str, Any] = row.get("version") or {}
        content: dict[str, Any] = version.get("content") or {}
        year: dict[str, Any] = content.get("year") or {}
        if row.get("country") != residency:
            continue
        if str(year.get("start", "")) <= today.isoformat() <= str(year.get("end", "")):
            return content.get("long_term_after_months"), content.get("wash_sale_days")
    return None, None


def _held(opened: date, until: date, months: int | None) -> str | None:
    """`long` when held more than `months` months to `until`, else `short`;
    None without a line."""
    if months is None:
        return None
    held = (until.year - opened.year) * 12 + until.month - opened.month
    if until.day < opened.day:
        held -= 1
    return "long" if held >= months and until > opened else "short"


def _cost_method(value: object) -> CostMethod | None:
    if value is None:
        return None
    if value not in COST_METHODS:
        raise ValueError(f"cost_method is one of {', '.join(COST_METHODS)}, not {value!r}")
    return value


def _expense_ratio(value: object) -> Decimal | None:
    if value is None:
        return None
    ratio = _decimal("expense_ratio", value)
    if not 0 <= ratio < 1:
        raise ValueError("expense_ratio is a yearly fraction of the value, 0 or more and under 1")
    return ratio


# ── Views ─────────────────────────────────────────────────────────────────────


def _allocation(value: object) -> dict[str, str] | None:
    """A look-through allocation as stored: class → share as a string."""
    checked = check_allocation(value)
    return None if checked is None else {k: plain(v) for k, v in checked.items()}


def _money(value: Decimal, currency: str) -> str:
    """An amount as a decimal string in `currency`'s own precision."""
    with localcontext(EXACT):
        return str(quantize(value, currency))


def _per_unit(value: Decimal) -> str:
    with localcontext(EXACT):
        return plain(value.quantize(_STEP))


def _transaction_view(row: dict[str, Any], currency: str) -> dict[str, Any]:
    tx = _transaction(row, currency, 0)
    with localcontext(EXACT):
        if tx.kind is Kind.BUY:
            total: Decimal | None = tx.quantity * tx.price + tx.fees
        elif tx.kind is Kind.SELL:
            total = tx.quantity * tx.price - tx.fees
        elif tx.kind in INCOME:
            total = tx.amount - tx.withholding_tax
        elif tx.kind is Kind.TRANSFER_IN:
            total = tx.amount
        else:
            total = None
    is_split = tx.kind is Kind.SPLIT
    return {
        "id": row["id"],
        "holding_id": row["holding_id"],
        "kind": tx.kind.value,
        "date": tx.on.isoformat(),
        "currency": currency,
        "quantity": plain(tx.quantity) if row.get("quantity") is not None else None,
        "price": plain(tx.price) if row.get("price") is not None else None,
        "fees": str(from_minor(row["fees_minor"], currency)),
        "amount": (
            str(from_minor(row["amount_minor"], currency))
            if row.get("amount_minor") is not None
            else None
        ),
        "withholding_tax": str(from_minor(row["withholding_tax_minor"], currency)),
        "ratio": f"{plain(tx.split_to)}:{plain(tx.split_from)}" if is_split else None,
        "lots": [{"lot_id": p.lot_id, "quantity": plain(p.quantity)} for p in tx.lots],
        "fx_rate": None if is_split else plain(tx.fx_rate),
        "fx_rate_source": row.get("fx_rate_source"),
        "total": _money(total, currency) if total is not None else None,
        "note": row.get("note"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _price_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "date": row["price_date"],
        "close": plain(Decimal(row["close"])),
        "currency": row["currency"],
        "source": row["source"],
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@dataclass
class _Tracked:
    """A holding with what valuing it takes: its history and its prices."""

    holding: dict[str, Any]
    transactions: list[Transaction]
    pricing: Pricing
    #: Closes recorded for its symbol in another currency: not its prices.
    foreign_closes: int
    #: The rates every one of the user's transactions carries, by currency
    #: and day (shared by all of the user's holdings).
    recorded: dict[tuple[str, date], Decimal]
    #: How its sales pick their lots: its own method, else its rules'.
    method: CostMethod = "fifo"
    #: Where the method comes from: "holding", "rule_set" or "default".
    method_source: str = "default"

    @property
    def currency(self) -> str:
        return str(self.holding["currency"])

    @property
    def tracked(self) -> bool:
        """Whether its figures come from transactions (else, as declared)."""
        return bool(self.transactions)


def _recorded_rates(
    rows: Iterable[dict[str, Any]], currencies: dict[str, str]
) -> dict[tuple[str, date], Decimal]:
    """The rates the user's own transactions carry, by currency and day: real
    rates for those days, so no source has to be asked for them again. From
    every holding's, so a holding is valued the same whichever are asked for."""
    rates: dict[tuple[str, date], Decimal] = {}
    for row in rows:
        currency = currencies.get(row["holding_id"])
        if currency is not None and row["kind"] != Kind.SPLIT.value:
            rates[currency, _date(row["transaction_date"])] = Decimal(row["fx_rate"])
    return rates


def _valuation_view(t: _Tracked, v: Valuation | None, base: str) -> dict[str, Any]:
    """What a holding is worth now, in its own currency and the base one, and
    what that rests on. `v` is None for a holding declared by value."""
    holding, currency = t.holding, t.currency
    symbol = symbol_key(holding["symbol"])
    notes: list[str] = []
    if v is None:
        cost_base = from_minor(holding["cost_basis_minor"], base)
        value_base = from_minor(holding["current_value_minor"], base)
        # Declared figures are in the base currency; one in another currency
        # cannot have any (see _check_declared).
        cost, value = (cost_base, value_base) if currency == base else (ZERO, ZERO)
        figures: dict[str, Any] = {
            "quantity": None,
            "price": None,
            "fx_rate": None,
            "priced": None,
            "converted": None,
        }
    else:
        cost, cost_base, value, value_base = v.cost, v.cost_base, v.value, v.value_base
        if v.quantity > 0 and v.quote is None:
            notes.append(f"No price for {symbol}: valued at what it cost")
        if v.quote is not None and v.fx_rate is None:
            notes.append(
                f"No {currency}→{base} rate for {v.quote.on.isoformat()}: "
                f"{symbol}'s value in {base} is carried at what it cost"
            )
        figures = {
            "quantity": plain(v.quantity),
            "price": (
                {
                    "date": v.quote.on.isoformat(),
                    "close": plain(v.quote.price),
                    "per_unit": plain(v.price) if v.price is not None else plain(v.quote.price),
                    "source": v.quote.source,
                }
                if v.quote is not None
                else None
            ),
            "fx_rate": plain(v.fx_rate) if v.fx_rate is not None else None,
            "priced": v.priced,
            "converted": v.converted,
        }
    if t.foreign_closes:
        notes.append(
            f"{t.foreign_closes} recorded price(s) for {symbol} are not in {currency}, "
            "so are not this holding's"
        )
    with localcontext(EXACT):
        return {
            "holding_id": holding["id"],
            "tracking": "transactions" if v is not None else "declared",
            "currency": currency,
            "base_currency": base,
            **figures,
            "value": _money(value, currency),
            "cost": _money(cost, currency),
            "unrealised_gain": _money(value - cost, currency),
            "value_base": _money(value_base, base),
            "cost_base": _money(cost_base, base),
            "unrealised_gain_base": _money(value_base - cost_base, base),
            "notes": notes,
        }


_RATE_STEP = Decimal("0.000001")
#: Exchange rates looked up at once while valuing (see PortfolioService._rates).
_RATE_LOOKUPS = 8


def _rate_view(rate: Decimal | None) -> str | None:
    """A rate of return as a fraction of one, to six places ("0.073512")."""
    if rate is None:
        return None
    # Enough digits for any rate, however large a return compounds to.
    with localcontext(Context(prec=max(RATE.prec, rate.adjusted() + 10))):
        return str(rate.quantize(_RATE_STEP))


def _figures_view(f: performance.Figures, currency: str, days: int) -> dict[str, Any]:
    with localcontext(EXACT):
        return {
            "currency": currency,
            "opening_value": _money(f.opening_value, currency),
            "closing_value": _money(f.closing_value, currency),
            "opening_cost": _money(f.opening_cost, currency),
            "closing_cost": _money(f.closing_cost, currency),
            "opening_unrealised_gain": _money(f.opening_unrealised, currency),
            "unrealised_gain": _money(f.closing_unrealised, currency),
            "realised_gain": _money(f.realised, currency),
            "dividends": _money(f.dividends, currency),
            "interest": _money(f.interest, currency),
            "withholding_tax": _money(f.withholding_tax, currency),
            "net_income": _money(f.net_income, currency),
            "paid_in": _money(f.paid_in, currency),
            "taken_out": _money(f.taken_out, currency),
            "total_return": _money(f.total_return, currency),
            "twr": _rate_view(f.twr),
            "twr_annualised": _rate_view(annualised(f.twr, days) if f.twr is not None else None),
            "xirr": _rate_view(f.xirr),
        }


def _at_cost_notes(
    figures: performance.HoldingFigures, symbol: str, currency: str, base: str
) -> list[str]:
    """What a holding's valuations in the period had to carry at cost."""
    notes: list[str] = []
    unpriced = sorted({a.on for a in figures.at_cost if a.missing == "price"})
    if unpriced:
        others = f" and {len(unpriced) - 1} other day(s)" if len(unpriced) > 1 else ""
        notes.append(
            f"No price for {symbol} on {unpriced[0].isoformat()}{others}: valued at what it cost"
        )
    for price_on in sorted(
        {a.price_on for a in figures.at_cost if a.missing == "rate" and a.price_on}
    ):
        notes.append(
            f"No {currency}→{base} rate for {price_on.isoformat()}: "
            f"{symbol}'s value in {base} is carried at what it cost"
        )
    return notes


def _holding_view(t: _Tracked, v: Valuation | None, base: str) -> dict[str, Any]:
    """A holding as `holdings.list` has always returned it, its figures in the
    base currency — from its transactions and prices when it has
    transactions, else as declared — and, alongside, the same in its own
    currency and what they rest on."""
    holding = t.holding
    valued = _valuation_view(t, v, base)
    return {
        "id": holding["id"],
        "symbol": holding["symbol"],
        "name": holding["name"],
        "asset_class": holding["asset_class"],
        "currency": base,
        "cost_basis": valued["cost_base"],
        "current_value": valued["value_base"],
        "is_active": holding["is_active"],
        "account_id": holding.get("account_id"),
        "cost_method": t.method,
        "cost_method_source": t.method_source,
        "expense_ratio": (
            plain(Decimal(holding["expense_ratio"]))
            if holding.get("expense_ratio") is not None
            else None
        ),
        "allocation": holding.get("allocation"),
        "created_at": holding.get("created_at"),
        "updated_at": holding.get("updated_at"),
        "tracking": valued["tracking"],
        "unrealised_gain": valued["unrealised_gain_base"],
        "native": {
            "currency": t.currency,
            "cost_basis": valued["cost"],
            "current_value": valued["value"],
            "unrealised_gain": valued["unrealised_gain"],
        },
        "quantity": valued["quantity"],
        "price": valued["price"],
        "fx_rate": valued["fx_rate"],
        "priced": valued["priced"],
        "converted": valued["converted"],
        "notes": valued["notes"],
    }


async def check_holding_account(uow: Any, user_id: str, account_id: str) -> None:
    """Refuse to link a holding to `account_id` unless it is one of the
    user's own asset accounts with the `investment` role (AccountNotFound
    when it isn't theirs, which reads the same as one that doesn't exist;
    ValueError otherwise). The ledger stays the one source of balances: the
    link says which investment account a holding sits in, so a scenario can
    sell it from what that account holds."""
    await require_own_accounts(uow, user_id, [account_id])
    account = await uow.ledger.get_account(user_id, account_id)
    if account.type != "asset" or account.asset_role != "investment":
        kind = (
            f"an {account.type} account"
            if account.type != "asset"
            else f"an asset account with the role {account.asset_role or 'cash'}"
        )
        raise ValueError(
            f"A holding links to the investment account that holds it, such as a "
            f"brokerage; {account.name} is {kind} (`salli accounts update "
            f"{account.code} --asset-role investment` marks an account as one)"
        )


class PortfolioService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        fx: FxRatePort | None = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._uow_factory = uow_factory
        # Rates into the base currency: for transactions that arrive without
        # their own (see application/fx.py), and for valuing a holding at a
        # close on a day none of its transactions has a rate for.
        self._fx = fx
        self._today = today

    # ── holdings ──────────────────────────────────────────────────────────────

    async def add_holding(self, user_id: str, data: dict[str, Any]) -> str:
        async with self._uow_factory() as uow:
            base = await uow.user_profiles.base_currency(user_id)
            currency = normalize_currency(data.get("currency") or base)
            cost_basis = Decimal(str(data.get("cost_basis") or 0))
            current_value = Decimal(str(data.get("current_value") or 0))
            _check_declared(currency, base, cost_basis, current_value)
            holding = {
                "symbol": data["symbol"],
                "name": data["name"],
                "asset_class": data["asset_class"],
                "currency": currency,
                # Declared figures are in the base currency.
                "cost_basis_minor": to_minor(cost_basis, base),
                "current_value_minor": to_minor(current_value, base),
            }
            if data.get("account_id"):
                await check_holding_account(uow, user_id, data["account_id"])
                holding["account_id"] = data["account_id"]
            holding["cost_method"] = _cost_method(data.get("cost_method"))
            holding["expense_ratio"] = _expense_ratio(data.get("expense_ratio"))
            holding["allocation"] = _allocation(data.get("allocation"))
            return await uow.holdings.save(user_id, holding)

    async def list_holdings(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            base = await uow.user_profiles.base_currency(user_id)
            holdings = await uow.holdings.list(user_id, active_only)
            tracked = await self._tracked(uow, user_id, holdings)
        valuations = await self._value_now(base, tracked)
        return [_holding_view(t, v, base) for t, v in zip(tracked, valuations, strict=True)]

    async def holding_refs(self, user_id: str) -> list[dict[str, Any]]:
        """Every holding's id, symbol and name, active or not, without valuing
        any: enough to find one by a short id."""
        async with self._uow_factory() as uow:
            holdings = await uow.holdings.list(user_id, active_only=False)
        return [{"id": h["id"], "symbol": h["symbol"], "name": h["name"]} for h in holdings]

    async def get_holding(self, user_id: str, holding_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            holding = await uow.holdings.get(user_id, holding_id)
            if holding is None:
                return None
            base = await uow.user_profiles.base_currency(user_id)
            tracked = await self._tracked(uow, user_id, [holding])
        [valuation] = await self._value_now(base, tracked)
        return _holding_view(tracked[0], valuation, base)

    async def update_holding(self, user_id: str, holding_id: str, data: dict[str, Any]) -> None:
        updates: dict[str, Any] = {}
        if "symbol" in data:
            updates["symbol"] = data["symbol"]
        if "name" in data:
            updates["name"] = data["name"]
        if "asset_class" in data:
            updates["asset_class"] = data["asset_class"]
        if "is_active" in data:
            updates["is_active"] = data["is_active"]
        async with self._uow_factory() as uow:
            holding = await uow.holdings.get(user_id, holding_id)
            if holding is None:
                return
            if "account_id" in data:
                # None unlinks it; another id links it (`check_holding_account`).
                if data["account_id"]:
                    await check_holding_account(uow, user_id, data["account_id"])
                updates["account_id"] = data["account_id"] or None
            if "expense_ratio" in data:
                updates["expense_ratio"] = _expense_ratio(data["expense_ratio"])
            if "allocation" in data:
                updates["allocation"] = _allocation(data["allocation"])
            if "cost_method" in data:
                # None returns it to its rules' method, else first in, first out.
                method = _cost_method(data["cost_method"])
                updates["cost_method"] = method
                rows = await uow.holding_transactions.list(user_id, holding_id)
                _check(
                    rows,
                    holding["currency"],
                    method or await rule_set_method(uow, user_id, self._today()) or "fifo",
                )
            base = await uow.user_profiles.base_currency(user_id)
            if ("cost_basis" in data or "current_value" in data) and (
                await uow.holding_transactions.list(user_id, holding_id)
            ):
                raise ValueError(
                    "This holding's cost basis and value come from its transactions and "
                    "prices: record a transaction or a price instead"
                )
            if "cost_basis" in data:
                updates["cost_basis_minor"] = to_minor(Decimal(str(data["cost_basis"])), base)
            if "current_value" in data:
                updates["current_value_minor"] = to_minor(Decimal(str(data["current_value"])), base)
            if data.get("currency"):
                currency = normalize_currency(data["currency"])
                if currency != holding["currency"]:
                    if await uow.holding_transactions.list(user_id, holding_id):
                        raise ValueError(
                            "A holding's currency cannot change once it has transactions: "
                            "they are in it"
                        )
                    updates["currency"] = currency
            _check_declared(
                updates.get("currency", holding["currency"]),
                base,
                from_minor(updates.get("cost_basis_minor", holding["cost_basis_minor"]), base),
                from_minor(
                    updates.get("current_value_minor", holding["current_value_minor"]), base
                ),
            )
            await uow.holdings.update(user_id, holding_id, updates)

    async def delete_holding(self, user_id: str, holding_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.holdings.delete(user_id, holding_id)

    # ── transactions ──────────────────────────────────────────────────────────

    async def _method_of(self, uow: Any, user_id: str, holding: dict[str, Any]) -> CostMethod:
        """The holding's own cost method, else its rules', else fifo."""
        own = _cost_method(holding.get("cost_method"))
        return own or await rule_set_method(uow, user_id, self._today()) or "fifo"

    async def _holding_and_base(
        self, user_id: str, holding_id: str
    ) -> tuple[dict[str, Any] | None, str]:
        async with self._uow_factory() as uow:
            base = await uow.user_profiles.base_currency(user_id)
            return await uow.holdings.get(user_id, holding_id), base

    async def _rate(
        self, kind: Kind, fields: dict[str, Any], currency: str, base: str
    ) -> tuple[Decimal, str | None]:
        """The rate into the base currency on the transaction's date: the one
        given, else the published one, else FxUnavailableError. A split moves
        no money, so has none."""
        if kind is Kind.SPLIT:
            return ONE, None
        given = _decimal("fx_rate", fields["fx_rate"]) if "fx_rate" in fields else None
        on = _date(fields["date"]).isoformat()
        rate, source = await rate_to_base(self._fx, currency, base, on, given)
        if given is not None:
            return rate, fields.get("fx_rate_source") or source
        # A published rate with more places than the column keeps is rounded
        # here, so what is checked is what is stored.
        with localcontext(EXACT):
            return (rate.quantize(_STEP) if _places(rate) > PLACES else rate), source

    async def add_transaction(
        self, user_id: str, holding_id: str, data: dict[str, Any]
    ) -> str | None:
        """Record a transaction; None if there is no such holding. Raises
        TransactionError for one that is malformed or impossible, and
        FxUnavailableError for one in another currency with no rate."""
        kind, fields = _fields(data)
        holding, base = await self._holding_and_base(user_id, holding_id)
        if holding is None:
            return None
        currency = holding["currency"]
        rate, source = await self._rate(kind, fields, currency, base)
        row = {
            "id": str(uuid.uuid4()),
            "holding_id": holding_id,
            **_columns(kind, fields, currency, rate, source),
        }
        async with self._uow_factory() as uow:
            # Hold the holding while its history is checked and changed, so
            # two sales of the same units cannot both pass the check.
            await uow.holdings.lock(user_id, holding_id)
            rows = await uow.holding_transactions.list(user_id, holding_id)
            _check([*rows, row], currency, await self._method_of(uow, user_id, holding))
            return await uow.holding_transactions.save(user_id, row)

    async def list_transactions(self, user_id: str, holding_id: str) -> list[dict[str, Any]] | None:
        """A holding's transactions in the order they take effect; None if
        there is no such holding."""
        async with self._uow_factory() as uow:
            holding = await uow.holdings.get(user_id, holding_id)
            if holding is None:
                return None
            rows = await uow.holding_transactions.list(user_id, holding_id)
        currency = holding["currency"]
        by_id = {row["id"]: row for row in rows}
        return [
            _transaction_view(by_id[tx.id], currency) for tx in ordered(history(rows, currency))
        ]

    async def get_transaction(
        self, user_id: str, holding_id: str, transaction_id: str
    ) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            holding = await uow.holdings.get(user_id, holding_id)
            row = await uow.holding_transactions.get(user_id, transaction_id)
        if holding is None or row is None or row["holding_id"] != holding_id:
            return None
        return _transaction_view(row, holding["currency"])

    async def update_transaction(
        self, user_id: str, holding_id: str, transaction_id: str, data: dict[str, Any]
    ) -> bool:
        """Change a transaction; False if there is no such transaction. Its
        kind cannot change. Its rate is the one given; else the stored one
        while its date stands; else the published one for the new date."""
        holding, base = await self._holding_and_base(user_id, holding_id)
        if holding is None:
            return False
        currency = holding["currency"]
        async with self._uow_factory() as uow:
            current = await uow.holding_transactions.get(user_id, transaction_id)
        if current is None or current["holding_id"] != holding_id:
            return False
        if data.get("kind") not in (None, current["kind"]):
            raise TransactionError(
                "A transaction's kind cannot change: delete it and record another"
            )
        patch = {k: v for k, v in data.items() if v is not None and k != "kind"}
        kind, fields = _fields({**_given(current, currency), **patch, "kind": current["kind"]})
        if "fx_rate" in fields or _date(fields["date"]).isoformat() != current["transaction_date"]:
            rate, source = await self._rate(kind, fields, currency, base)
        else:
            rate, source = Decimal(current["fx_rate"]), current.get("fx_rate_source")
        columns = _columns(kind, fields, currency, rate, source)
        async with self._uow_factory() as uow:
            await uow.holdings.lock(user_id, holding_id)
            rows = await uow.holding_transactions.list(user_id, holding_id)
            _check(
                [{**r, **columns} if r["id"] == transaction_id else r for r in rows],
                currency,
                await self._method_of(uow, user_id, holding),
            )
            return await uow.holding_transactions.update(user_id, transaction_id, columns)

    async def delete_transaction(self, user_id: str, holding_id: str, transaction_id: str) -> bool:
        """Delete a transaction, unless the history would not stand without it
        (a later sale needs the units it bought)."""
        async with self._uow_factory() as uow:
            holding = await uow.holdings.get(user_id, holding_id)
            if holding is None:
                return False
            await uow.holdings.lock(user_id, holding_id)
            rows = await uow.holding_transactions.list(user_id, holding_id)
            if transaction_id not in {r["id"] for r in rows}:
                return False
            _check(
                [r for r in rows if r["id"] != transaction_id],
                holding["currency"],
                await self._method_of(uow, user_id, holding),
            )
            return await uow.holding_transactions.delete(user_id, transaction_id)

    async def export_transactions(self, user_id: str) -> list[dict[str, Any]]:
        """Every transaction of every holding, inactive ones' included, for the
        user's data export."""
        async with self._uow_factory() as uow:
            holdings = await uow.holdings.list(user_id, active_only=False)
            rows = await uow.holding_transactions.list(user_id)
        currency = {h["id"]: h["currency"] for h in holdings}
        return [_transaction_view(row, currency[row["holding_id"]]) for row in rows]

    # ── lots ──────────────────────────────────────────────────────────────────

    async def get_lots(self, user_id: str, holding_id: str) -> dict[str, Any] | None:
        """A holding's lots, open and closed, and each sale with the lots it
        consumed. Native figures are in the holding's currency; `*_base` ones
        in the owner's base currency, at the rates of the days they happened."""
        async with self._uow_factory() as uow:
            holding = await uow.holdings.get(user_id, holding_id)
            if holding is None:
                return None
            base = await uow.user_profiles.base_currency(user_id)
            rows = await uow.holding_transactions.list(user_id, holding_id)
            method = await self._method_of(uow, user_id, holding)
            today = self._today()
            long_after, wash_days = await rule_set_terms(uow, user_id, today)
        currency = holding["currency"]
        transactions = history(rows, currency)
        book = replay(transactions, method=method)
        buys = [tx.on for tx in transactions if tx.kind is Kind.BUY]

        def washed(sale_on: date, gain: Decimal) -> bool | None:
            if wash_days is None:
                return None
            return gain < 0 and any(
                abs((on - sale_on).days) <= wash_days and on != sale_on for on in buys
            )

        position = book.position
        with localcontext(EXACT):
            lots = [
                {
                    "id": lot.id,
                    "kind": lot.kind.value,
                    "opened_on": lot.opened_on.isoformat(),
                    "opened_quantity": plain(lot.opened_quantity),
                    "quantity": plain(lot.quantity),
                    "cost": _money(lot.cost, currency),
                    "cost_base": _money(lot.cost_base, base),
                    "cost_per_unit": (
                        _per_unit(lot.cost / lot.quantity) if lot.quantity > 0 else None
                    ),
                    "is_open": lot.is_open,
                    "holding_period": _held(lot.opened_on, today, long_after)
                    if lot.is_open
                    else None,
                }
                for lot in book.lots
            ]
        sales = [
            {
                "transaction_id": sale.transaction_id,
                "date": sale.on.isoformat(),
                "quantity": plain(sale.quantity),
                "proceeds": _money(sale.proceeds, currency),
                "fees": _money(sale.fees, currency),
                "cost": _money(sale.cost, currency),
                "gain": _money(sale.gain, currency),
                "fx_rate": plain(sale.fx_rate),
                "proceeds_base": _money(sale.proceeds_base, base),
                "fees_base": _money(sale.fees_base, base),
                "cost_base": _money(sale.cost_base, base),
                "gain_base": _money(sale.gain_base, base),
                "wash_sale": washed(sale.on, sale.gain_base),
                "consumed": [
                    {
                        "lot_id": c.lot_id,
                        "opened_on": c.opened_on.isoformat(),
                        "holding_period": _held(c.opened_on, sale.on, long_after),
                        "quantity": plain(c.quantity),
                        "cost": _money(c.cost, currency),
                        "cost_base": _money(c.cost_base, base),
                    }
                    for c in sale.consumed
                ],
            }
            for sale in book.sales
        ]
        return {
            "holding_id": holding_id,
            "currency": currency,
            "base_currency": base,
            "cost_method": method,
            "long_term_after_months": long_after,
            "wash_sale_days": wash_days,
            "quantity": plain(position.quantity),
            "cost": _money(position.cost, currency),
            "cost_base": _money(position.cost_base, base),
            "lots": lots,
            "sales": sales,
        }

    # ── prices ────────────────────────────────────────────────────────────────

    async def set_price(self, user_id: str, data: dict[str, Any]) -> str:
        """Record a closing price: `symbol`, `close`, `date` (default today),
        `currency` (default: that of the user's holdings with the symbol).
        One already recorded for that symbol, currency and day is replaced."""
        symbol = symbol_key(str(data.get("symbol") or ""))
        if not symbol or len(symbol) > 20:
            raise ValueError("A price needs the symbol it is for, of at most 20 characters")
        close = _decimal("close", data.get("close"))
        check_number("close", close, positive=True)
        on = _date(data["date"]) if data.get("date") else self._today()
        async with self._uow_factory() as uow:
            if data.get("currency"):
                currency = normalize_currency(data["currency"])
            else:
                holdings = await uow.holdings.list(user_id, active_only=False)
                currencies = {h["currency"] for h in holdings if symbol_key(h["symbol"]) == symbol}
                if len(currencies) != 1:
                    held = f"in {', '.join(sorted(currencies))}" if currencies else "none"
                    raise ValueError(
                        f"Say which currency the price is in: of your holdings of {symbol}, {held}"
                    )
                currency = currencies.pop()
            return await uow.holding_prices.upsert(
                user_id,
                {
                    "symbol": symbol,
                    "price_date": on.isoformat(),
                    "close": close,
                    "currency": currency,
                    "source": "user",
                },
            )

    async def list_prices(
        self,
        user_id: str,
        symbol: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recorded closes, newest first: one symbol's, or every one."""
        key = symbol_key(symbol) if symbol else None
        async with self._uow_factory() as uow:
            rows = await uow.holding_prices.list(
                user_id,
                key,
                _date(start).isoformat() if start else None,
                _date(end).isoformat() if end else None,
            )
        return [_price_view(row) for row in reversed(rows)]

    async def delete_price(self, user_id: str, quote_id: str) -> bool:
        async with self._uow_factory() as uow:
            return await uow.holding_prices.delete(user_id, quote_id)

    # ── valuation ─────────────────────────────────────────────────────────────

    async def _tracked(
        self, uow: Any, user_id: str, holdings: list[dict[str, Any]]
    ) -> list[_Tracked]:
        """Each holding with its transactions and its recorded closes."""
        by_holding: dict[str, list[dict[str, Any]]] = {}
        rows = await uow.holding_transactions.list(user_id)
        for row in rows:
            by_holding.setdefault(row["holding_id"], []).append(row)
        everything = await uow.holdings.list(user_id, active_only=False)
        recorded = _recorded_rates(rows, {h["id"]: h["currency"] for h in everything})
        market = StoredPriceHistory(uow.holding_prices, user_id)
        rules_method = await rule_set_method(uow, user_id, self._today())
        quotes: dict[str, list[Any]] = {}
        tracked: list[_Tracked] = []
        for h in holdings:
            key = symbol_key(h["symbol"])
            if key not in quotes:
                quotes[key] = await market.history(key, date.min, date.max)
            closes = [
                Close(q.on, q.close, q.source) for q in quotes[key] if q.currency == h["currency"]
            ]
            transactions = history(by_holding.get(h["id"], []), h["currency"])
            tracked.append(
                _Tracked(
                    h,
                    transactions,
                    Pricing(transactions, closes),
                    len(quotes[key]) - len(closes),
                    recorded,
                    _cost_method(h.get("cost_method")) or rules_method or "fifo",
                    "holding"
                    if h.get("cost_method")
                    else "rule_set"
                    if rules_method
                    else "default",
                )
            )
        return tracked

    async def _rate_on(
        self, currency: str, base: str, on: date, recorded: dict[tuple[str, date], Decimal]
    ) -> Decimal | None:
        """The rate into the base currency on `on`: 1 for the base itself; one
        the user's own transactions carry for that day; else the published
        one. None when there is none — never a guess."""
        if currency == base:
            return ONE
        if (currency, on) in recorded:
            return recorded[currency, on]
        if self._fx is None:
            return None
        try:
            quote = await self._fx.rate(currency, base, on.isoformat())
        except FxUnavailableError:
            return None
        with localcontext(EXACT):
            return quote.rate.quantize(_STEP) if _places(quote.rate) > PLACES else quote.rate

    async def _rates(
        self, base: str, tracked: list[_Tracked], dates: Iterable[date]
    ) -> dict[str, dict[date, Decimal]]:
        """For each currency, the rates valuing `tracked` on `dates` needs."""
        dates = list(dates)
        needed: dict[str, set[date]] = {}
        for t in tracked:
            if t.tracked:
                needed.setdefault(t.currency, set()).update(t.pricing.rate_dates(dates))
        recorded = tracked[0].recorded if tracked else {}
        wanted = [(currency, on) for currency in sorted(needed) for on in sorted(needed[currency])]
        # A rate source can be slow, or down; ask for several at once rather
        # than one after another, but not for all of them at once.
        limit = asyncio.Semaphore(_RATE_LOOKUPS)

        async def look_up(currency: str, on: date) -> Decimal | None:
            async with limit:
                return await self._rate_on(currency, base, on, recorded)

        rates = await asyncio.gather(*(look_up(currency, on) for currency, on in wanted))
        found: dict[str, dict[date, Decimal]] = {}
        for (currency, on), rate in zip(wanted, rates, strict=True):
            if rate is not None:
                found.setdefault(currency, {})[on] = rate
        return found

    async def _value_now(self, base: str, tracked: list[_Tracked]) -> list[Valuation | None]:
        """Each holding as everything recorded says it is now, at its latest
        price; None for one declared by value."""
        rates = await self._rates(base, tracked, [date.max])
        return [
            t.pricing.value(
                date.max,
                replay(t.transactions, method=t.method).position,
                rates.get(t.currency, {}),
            )
            if t.tracked
            else None
            for t in tracked
        ]

    async def get_valuation(self, user_id: str, holding_id: str) -> dict[str, Any] | None:
        """What a holding is worth now: quantity × its latest price, in its
        own currency and in the base one (at the rate of the price's day), and
        what that rests on. Reads only what is stored: no price is fetched."""
        async with self._uow_factory() as uow:
            holding = await uow.holdings.get(user_id, holding_id)
            if holding is None:
                return None
            base = await uow.user_profiles.base_currency(user_id)
            tracked = await self._tracked(uow, user_id, [holding])
        [valuation] = await self._value_now(base, tracked)
        return _valuation_view(tracked[0], valuation, base)

    # ── performance ───────────────────────────────────────────────────────────

    async def get_performance(
        self,
        user_id: str,
        start: str | date | None = None,
        end: str | date | None = None,
        holding_id: str | None = None,
        benchmark: str | None = None,
        cash_yield: Decimal | None = None,
        blend: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        """Gains, income and returns from `start` to `end` inclusive (a tax
        year, say): per holding in its own currency and the base one, and for
        the portfolio (or just `holding_id`; None if there is no such holding)
        in the base one. With no `start`, since the first transaction; `end`
        defaults to today (or the latest transaction or price, if later).
        `risk` holds the risk figures (domain/portfolio/risk.py), from
        monthly returns, the Sharpe ratio against `cash_yield` (nominal) or the
        active CMA pack's cash yield put on a nominal basis with its inflation
        (none without one), and the closes recorded for the `benchmark` symbol.

        Every holding counts, inactive ones too: a sale's gain belongs to its
        tax year however the holding is filed now. A holding declared by
        value has no history to measure, so it is listed apart."""
        async with self._uow_factory() as uow:
            if holding_id is not None:
                holding = await uow.holdings.get(user_id, holding_id)
                if holding is None:
                    return None
                holdings = [holding]
            else:
                holdings = await uow.holdings.list(user_id, active_only=False)
            base = await uow.user_profiles.base_currency(user_id)
            tracked = await self._tracked(uow, user_id, holdings)
            bench_rows: list[dict[str, Any]] = (
                await uow.holding_prices.list(user_id, symbol_key(benchmark), None, None)
                if benchmark
                else []
            )
            pack = await uow.cma_packs.active(user_id) if cash_yield is None else None
            blend_rows: dict[str, list[dict[str, Any]]] = {}
            weights: dict[str, Decimal] = {}
            if blend:
                versions = await uow.investment_policies.list(user_id)
                if not versions:
                    raise ValueError(
                        "A blended benchmark takes its weights from your investment policy: adopt one first"
                    )
                targets = {
                    t["asset_class"]: Decimal(t["target"])
                    for t in versions[-1]["content"]["targets"]
                }
                unknown = sorted(set(blend) - set(targets))
                if unknown:
                    raise ValueError(f"Not classes of your investment policy: {', '.join(unknown)}")
                weights = {c: targets[c] for c in blend}
                for asset_class, symbol in blend.items():
                    blend_rows[asset_class] = await uow.holding_prices.list(
                        user_id, symbol_key(symbol), None, None
                    )

        measured = [t for t in tracked if t.tracked]
        notes: list[str] = []
        first = _date(start) if start else None
        if first == date.min:
            # Nothing can precede the first day there is: from the start.
            first = None
        last = (
            _date(end)
            if end
            else max(
                [self._today()]
                + [tx.on for t in measured for tx in t.transactions]
                + [day for t in measured if (day := t.pricing.last_day) is not None]
            )
        )
        if first is not None and first > last:
            raise ValueError(f"The period starts ({first}) after it ends ({last})")

        histories = [
            performance.History(t.holding["id"], t.transactions, t.pricing, {}, t.method)
            for t in measured
        ]
        flows = performance.flow_days(histories, first, last)
        opening = first or (flows[0] if flows else last)
        windows = risk.month_windows(opening, last)
        days = sorted(
            {
                *performance.valuation_days(histories, first, last),
                *(d for w in windows for d in performance.valuation_days(histories, *w)),
            }
        )
        rates = await self._rates(base, measured, days)
        histories = [
            performance.History(
                h.key, h.transactions, h.pricing, rates.get(t.currency, {}), t.method
            )
            for h, t in zip(histories, measured, strict=True)
        ]
        result = performance.report(histories, first, last)
        monthly = [
            twr
            for w in windows
            if (twr := performance.report(histories, *w).portfolio.twr) is not None
        ]
        bench = (
            risk.series_returns(
                [(_date(r["price_date"]), Decimal(r["close"])) for r in bench_rows], windows
            )
            if benchmark
            else None
        )
        bench_figures = risk.figures(bench, None) if bench else None
        # The returns measured here are nominal (time-weighted, from
        # prices), so the hurdle must be too: a CMA pack's cash yield is real,
        # put back on a nominal basis with the pack's inflation.
        hurdle_basis: str | None = None
        no_sharpe = "No Sharpe ratio: give a cash yield or activate a CMA pack as the hurdle"
        if cash_yield is not None:
            hurdle, hurdle_source, hurdle_basis = cash_yield, "cash_yield", "nominal"
        elif pack is not None:
            assumed = cma.stored(pack["content"], pack["id"], pack["content_hash"])
            if assumed.inflation is None:
                hurdle, hurdle_source = None, None
                no_sharpe = (
                    "No Sharpe ratio: the CMA pack's cash yield is after inflation and the "
                    "pack gives no inflation to set it against these nominal returns"
                )
            else:
                with localcontext(RATE):
                    hurdle = (1 + assumed.cash_yield.value) * (1 + assumed.inflation.value) - 1
                hurdle_source, hurdle_basis = "cma_pack", "nominal"
        else:
            hurdle, hurdle_source = None, None
        assert hurdle is None or hurdle_basis == "nominal", "Sharpe needs a nominal hurdle"
        own = risk.figures(monthly, hurdle)
        if hurdle is None and own.volatility:
            notes.append(no_sharpe)
        blended: list[Decimal] | None = None
        if blend:
            parts = [
                (
                    weights[c],
                    risk.series_returns(
                        [(_date(r["price_date"]), Decimal(r["close"])) for r in rows], windows
                    ),
                )
                for c, rows in blend_rows.items()
            ]
            covered = sum((w for w, _ in parts), Decimal(0))
            if any(r is None for _, r in parts) or covered <= 0:
                notes.append(
                    "No blended benchmark: each series needs a recorded close on or before "
                    "the start of every month in the period"
                )
            else:
                blended = risk.blend([(w / covered, cast(list[Decimal], r)) for w, r in parts])
                if covered != 1:
                    notes.append(
                        "The blended benchmark's weights are your policy's targets for the "
                        f"classes named, scaled to add up to 1 (they cover {plain(covered)})"
                    )
        blend_figures = risk.figures(blended, None) if blended else None
        against = blended if blended is not None else bench
        own_months = monthly[-len(against) :] if against else monthly
        tracking = risk.tracking_error(own_months, against) if against else None
        # Valued only when a holding has a ratio: nothing to weigh otherwise.
        costed = [t for t in tracked if t.holding["is_active"] and t.holding.get("expense_ratio")]
        weighted: str | None = None
        if costed:
            valuations_now = await self._value_now(base, costed)
            weighted = cast(
                str | None,
                engine.running_costs(
                    [
                        (
                            t.holding["symbol"],
                            v.value_base if v is not None else Decimal(0),
                            _expense_ratio(t.holding.get("expense_ratio")),
                        )
                        for t, v in zip(costed, valuations_now, strict=True)
                    ],
                    quantum(base),
                )["weighted_expense_ratio"],
            )

        declared = [t for t in tracked if not t.tracked]
        if benchmark and bench is None:
            notes.append(
                f"No benchmark figures: {symbol_key(benchmark)} needs a recorded close on or "
                "before the start of every month in the period"
            )
        if declared:
            symbols = ", ".join(symbol_key(t.holding["symbol"]) for t in declared)
            notes.append(
                f"Declared by value, with no transactions to measure, so not in these "
                f"figures: {symbols}"
            )
        holdings_view: list[dict[str, Any]] = []
        for t, figures in zip(measured, result.holdings, strict=True):
            symbol = symbol_key(t.holding["symbol"])
            # A holding's own period: from its first money, without a start.
            own_start = first or min(
                (tx.on for tx in t.transactions if tx.kind is not Kind.SPLIT), default=last
            )
            own_days = max((last - own_start).days + 1, 1)
            holdings_view.append(
                {
                    "holding_id": t.holding["id"],
                    "symbol": t.holding["symbol"],
                    "name": t.holding["name"],
                    "asset_class": t.holding["asset_class"],
                    "is_active": t.holding["is_active"],
                    "native": _figures_view(figures.native, t.currency, own_days),
                    "base": _figures_view(figures.base, base, own_days),
                    "notes": _at_cost_notes(figures, symbol, t.currency, base),
                }
            )
        return {
            "start": result.start.isoformat(),
            "end": result.end.isoformat(),
            "days": result.days,
            "base_currency": base,
            "portfolio": _figures_view(result.portfolio, base, result.days),
            "holdings": holdings_view,
            "risk": {
                "months": own.months,
                "yearly_return": _rate_view(own.yearly_return),
                "volatility": _rate_view(own.volatility),
                "max_drawdown": _rate_view(own.max_drawdown),
                "sharpe": _rate_view(own.sharpe),
                "hurdle": _rate_view(hurdle),
                "hurdle_source": hurdle_source,
                "benchmark": (
                    {
                        "symbol": symbol_key(benchmark),
                        "yearly_return": _rate_view(bench_figures.yearly_return),
                        "volatility": _rate_view(bench_figures.volatility),
                        "max_drawdown": _rate_view(bench_figures.max_drawdown),
                    }
                    if benchmark and bench_figures
                    else None
                ),
                "blended_benchmark": (
                    {
                        "weights": {c: plain(w) for c, w in weights.items()},
                        "series": {c: symbol_key(sym) for c, sym in (blend or {}).items()},
                        "yearly_return": _rate_view(blend_figures.yearly_return),
                        "volatility": _rate_view(blend_figures.volatility),
                        "max_drawdown": _rate_view(blend_figures.max_drawdown),
                    }
                    if blend_figures
                    else None
                ),
                "tracking_error": _rate_view(tracking),
                "tracking_against": None
                if tracking is None
                else ("blended_benchmark" if blended is not None else "benchmark"),
                "net_of_fees": {
                    "expense_ratio": weighted,
                    "yearly_return": None
                    if own.yearly_return is None or weighted is None
                    else _rate_view(own.yearly_return - Decimal(weighted)),
                    "says": "The yearly return less your holdings' weighted expense ratio, "
                    "your own figures; a fund whose prices already net its costs is then "
                    "counted twice.",
                },
            },
            "notes": notes,
        }

    # ── summary ───────────────────────────────────────────────────────────────

    async def get_summary(
        self, user_id: str, target_allocation: dict[str, Decimal] | None = None
    ) -> dict[str, Any]:
        """Allocation, gain and costs. Without `target_allocation`, the
        investment policy in force (if any) gives the targets and each class's
        band; `target_source` says which."""
        bands: dict[str, Decimal] | None = None
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            holdings_data = await uow.holdings.list(user_id, active_only=True)
            tracked = await self._tracked(uow, user_id, holdings_data)
            target_source = "given" if target_allocation else None
            if target_allocation is None:
                versions = await uow.investment_policies.list(user_id)
                if versions:
                    targets = versions[-1]["content"]["targets"]
                    target_allocation = {t["asset_class"]: Decimal(t["target"]) for t in targets}
                    bands = {t["asset_class"]: Decimal(t["band"]) for t in targets}
                    target_source = "policy"
        valuations = await self._value_now(currency, tracked)

        # In the base currency: from transactions and prices where a holding
        # has transactions, else as declared.
        holdings = [
            Holding(
                symbol=t.holding["symbol"],
                name=t.holding["name"],
                asset_class=t.holding["asset_class"],
                cost_basis=(
                    v.cost_base
                    if v is not None
                    else from_minor(t.holding["cost_basis_minor"], currency)
                ),
                current_value=(
                    v.value_base
                    if v is not None
                    else from_minor(t.holding["current_value_minor"], currency)
                ),
            )
            for t, v in zip(tracked, valuations, strict=True)
        ]
        with localcontext(EXACT):
            summary = engine.compute_summary(
                holdings, target_allocation, money_quantum=quantum(currency), bands=bands
            )
            costs = engine.running_costs(
                [
                    (h.symbol, h.current_value, _expense_ratio(t.holding.get("expense_ratio")))
                    for h, t in zip(holdings, tracked, strict=True)
                ],
                quantum(currency),
            )
        notes = [
            note
            for t, v in zip(tracked, valuations, strict=True)
            for note in _valuation_view(t, v, currency)["notes"]
        ]

        return {
            "currency": currency,
            "total_value": str(summary.total_value),
            "total_cost_basis": str(summary.total_cost_basis),
            "total_gain": str(summary.total_gain),
            "total_gain_pct": str(summary.total_gain_pct),
            "allocation": [
                {
                    "asset_class": a.asset_class,
                    "current_value": str(a.current_value),
                    "pct_of_portfolio": str(a.pct_of_portfolio),
                }
                for a in summary.allocation
            ],
            "alerts": [
                {
                    "asset_class": alert.asset_class,
                    "current_pct": str(alert.current_pct),
                    "target_pct": str(alert.target_pct),
                    "drift_pct": str(alert.drift_pct),
                }
                for alert in summary.alerts
            ],
            "target_source": target_source,
            "costs": costs,
            "notes": notes,
        }


def _places(value: Decimal) -> int:
    exponent = value.normalize(EXACT).as_tuple().exponent
    return -exponent if isinstance(exponent, int) and exponent < 0 else 0


def _check_declared(currency: str, base: str, cost_basis: Decimal, current_value: Decimal) -> None:
    """Declared figures are in the base currency; a holding in another one is
    tracked by its transactions instead."""
    if currency != base and (cost_basis != 0 or current_value != 0):
        raise ValueError(
            f"Declared figures are in your base currency ({base}); "
            f"record this {currency} holding's transactions instead"
        )
