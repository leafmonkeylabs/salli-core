"""
PortfolioService — investment holdings, their transactions and lots, and the
allocation/rebalancing/ROI summary.

A holding has a currency of its own (a US fund in a rupee ledger is in USD)
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

import uuid
from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, cast

from salli.application.fx import rate_to_base
from salli.application.ports import FxRatePort
from salli.domain.currency import normalize_currency, quantize, quantum
from salli.domain.money import from_minor, to_minor
from salli.domain.portfolio import engine
from salli.domain.portfolio.lots import (
    EXACT,
    INCOME,
    ONE,
    PLACES,
    ZERO,
    Kind,
    LotPick,
    Transaction,
    TransactionError,
    ordered,
    plain,
    replay,
    validate,
)
from salli.domain.portfolio.models import Holding

_STEP = Decimal(1).scaleb(-PLACES)

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
        return to_minor(_decimal(name, fields[name]), currency) if name in fields else None

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


def _history(rows: Iterable[dict[str, Any]], currency: str) -> list[Transaction]:
    """Rows in the order they were recorded, as domain transactions; their
    position is the tie-break between transactions of one kind on one date."""
    return [_transaction(row, currency, seq) for seq, row in enumerate(rows)]


def _check(rows: Iterable[dict[str, Any]], currency: str) -> list[Transaction]:
    """Refuse a history with a malformed transaction or one that cannot have
    happened. Returns it, as domain transactions."""
    history = _history(rows, currency)
    for tx in history:
        validate(tx)
    replay(history)
    return history


# ── Views ─────────────────────────────────────────────────────────────────────


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


def _holding_view(h: dict[str, Any], currency: str) -> dict[str, Any]:
    return {
        "id": h["id"],
        "symbol": h["symbol"],
        "name": h["name"],
        "asset_class": h["asset_class"],
        "currency": currency,
        "cost_basis": str(from_minor(h["cost_basis_minor"], currency)),
        "current_value": str(from_minor(h["current_value_minor"], currency)),
        "is_active": h["is_active"],
        "created_at": h.get("created_at"),
        "updated_at": h.get("updated_at"),
    }


class PortfolioService:
    def __init__(self, uow_factory: Callable[[], Any], fx: FxRatePort | None = None) -> None:
        self._uow_factory = uow_factory
        # Rates into the base currency for transactions that arrive without
        # their own (see application/fx.py).
        self._fx = fx

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
            return await uow.holdings.save(user_id, holding)

    async def list_holdings(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            holdings = await uow.holdings.list(user_id, active_only)
        return [_holding_view(h, currency) for h in holdings]

    async def get_holding(self, user_id: str, holding_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            h = await uow.holdings.get(user_id, holding_id)
        return _holding_view(h, currency) if h else None

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
            base = await uow.user_profiles.base_currency(user_id)
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
            rows = await uow.holding_transactions.list(user_id, holding_id)
            _check([*rows, row], currency)
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
            _transaction_view(by_id[tx.id], currency) for tx in ordered(_history(rows, currency))
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
            rows = await uow.holding_transactions.list(user_id, holding_id)
            _check([{**r, **columns} if r["id"] == transaction_id else r for r in rows], currency)
            return await uow.holding_transactions.update(user_id, transaction_id, columns)

    async def delete_transaction(self, user_id: str, holding_id: str, transaction_id: str) -> bool:
        """Delete a transaction, unless the history would not stand without it
        (a later sale needs the units it bought)."""
        async with self._uow_factory() as uow:
            holding = await uow.holdings.get(user_id, holding_id)
            if holding is None:
                return False
            rows = await uow.holding_transactions.list(user_id, holding_id)
            if transaction_id not in {r["id"] for r in rows}:
                return False
            _check([r for r in rows if r["id"] != transaction_id], holding["currency"])
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
        currency = holding["currency"]
        book = replay(_history(rows, currency))
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
                "consumed": [
                    {
                        "lot_id": c.lot_id,
                        "opened_on": c.opened_on.isoformat(),
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
            "quantity": plain(position.quantity),
            "cost": _money(position.cost, currency),
            "cost_base": _money(position.cost_base, base),
            "lots": lots,
            "sales": sales,
        }

    # ── summary ───────────────────────────────────────────────────────────────

    async def get_summary(
        self, user_id: str, target_allocation: dict[str, Decimal] | None = None
    ) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            currency = await uow.user_profiles.base_currency(user_id)
            holdings_data = await uow.holdings.list(user_id, active_only=True)

        holdings = [
            Holding(
                symbol=h["symbol"],
                name=h["name"],
                asset_class=h["asset_class"],
                cost_basis=from_minor(h["cost_basis_minor"], currency),
                current_value=from_minor(h["current_value_minor"], currency),
            )
            for h in holdings_data
        ]
        summary = engine.compute_summary(
            holdings, target_allocation, money_quantum=quantum(currency)
        )

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
