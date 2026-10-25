"""
The user's holdings as of the as-of date, and where they meet the ledger.
Pure.

The ledger is the one source of balances (decision lab 3b, decision 17): the
baseline's investments are its investment-role accounts, and nothing here
changes a figure. A holding may be linked to the investment account that
holds it (`holdings.account_id`); a scenario can then sell it, up to what
that account holds.

Each holding is valued as the portfolio values it (`portfolio.valuation`):
its transactions replayed to the as-of date, at the last price recorded on
or before it (a close, or one of its own trades), adjusted for splits since.
Its base value is at the **as-of rate**, as the ledger's balances are, so the
two can be compared. A holding without transactions keeps the value the user
declared. Nothing here forecasts a price or a rate, and no holding has an
expected return of its own (decision 18): there is one real return, the
person's.

Where a linked account's ledger value and its holdings' value differ, the
baseline's `notes` say by how much, and which counts (the ledger). They are
never reconciled silently.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal, localcontext

from salli.domain.baseline.models import Balance, BaselineHolding, HoldingInputs, Rate
from salli.domain.currency import quantum
from salli.domain.portfolio.lots import EXACT, replay
from salli.domain.portfolio.valuation import Pricing


def _rate(currency: str, base: str, rates: Mapping[str, Rate]) -> Decimal | None:
    if currency == base:
        return Decimal(1)
    rate = rates.get(currency)
    return None if rate is None else rate.rate


def value(
    h: HoldingInputs, as_of: dt.date, base: str, rates: Mapping[str, Rate]
) -> BaselineHolding:
    """One holding as of the as-of date, in its own currency and the base
    one at the as-of rate."""
    transactions = tuple(t for t in h.transactions if t.on <= as_of)
    closes = [c for c in h.closes if c.on <= as_of]
    fx = _rate(h.currency, base, rates)
    if not transactions:
        return BaselineHolding(
            holding_id=h.holding_id,
            symbol=h.symbol,
            name=h.name,
            currency=h.currency,
            account_id=h.account_id,
            transactions=(),
            tracked=False,
            quantity=Decimal(0),
            cost=Decimal(0),
            cost_base=Decimal(0),
            price=None,
            price_date=None,
            price_source=None,
            fx_rate=fx,
            value=None,
            value_base=h.declared_value,
            is_active=h.is_active,
            cost_method=h.cost_method,
        )
    position = replay(transactions, method=h.cost_method).position
    valued = Pricing(transactions, closes).value(as_of, position, {})
    with localcontext(EXACT):
        worth = valued.value if valued.priced else None
        worth_base = worth * fx if worth is not None and fx is not None else None
    return BaselineHolding(
        holding_id=h.holding_id,
        symbol=h.symbol,
        name=h.name,
        currency=h.currency,
        account_id=h.account_id,
        transactions=transactions,
        tracked=True,
        quantity=position.quantity,
        cost=position.cost,
        cost_base=position.cost_base,
        price=valued.price,
        price_date=valued.quote.on.isoformat() if valued.quote else None,
        price_source=valued.quote.source if valued.quote else None,
        fx_rate=fx,
        value=worth,
        value_base=worth_base,
        is_active=h.is_active,
        cost_method=h.cost_method,
    )


def _money(amount: Decimal, currency: str) -> str:
    q = quantum(currency, strict=False)
    return f"{amount.quantize(q, rounding=ROUND_HALF_UP):,}"


def meet_the_ledger(
    holdings: Sequence[BaselineHolding], balances: Sequence[Balance], base: str
) -> list[str]:
    """What the baseline says where a linked account and its holdings
    disagree, or can't be compared: never a figure changed."""
    notes: list[str] = []
    by_id = {b.account_id: b for b in balances}
    linked: dict[str, list[BaselineHolding]] = {}
    for h in holdings:
        if h.account_id is not None:
            linked.setdefault(h.account_id, []).append(h)
    for account_id, mine in linked.items():
        account = by_id.get(account_id)
        names = ", ".join(h.name for h in mine)
        if account is None:
            notes.append(
                f"{names}: linked to an account the baseline doesn't hold (closed and empty); "
                "a scenario can't sell it"
            )
            continue
        if account.role != "investment":
            notes.append(
                f"{account.name} holds {names} but isn't an investment account, so a scenario "
                "can't sell from it: mark it as one, or link the holding to the account that "
                "holds it"
            )
            continue
        if account.value is None:
            continue  # its own note says why it is left out
        unknown = [h for h in mine if h.value_base is None]
        if unknown:
            notes.append(
                f"{account.name}: {', '.join(h.name for h in unknown)} can't be valued in "
                f"{base} on this date (no price recorded, or no rate), so the account's ledger "
                "value and its holdings aren't compared"
            )
            continue
        worth = sum((h.value_base or Decimal(0) for h in mine), Decimal(0))
        q = quantum(base, strict=False)
        gap = (worth - account.value).quantize(q, rounding=ROUND_HALF_UP)
        if gap == 0:
            continue
        notes.append(
            f"{account.name}: your ledger holds {_money(account.value, base)} {base} and the "
            f"holdings linked to it are worth {_money(worth, base)} {base} at their recorded "
            f"prices ({_money(abs(gap), base)} {'more' if gap > 0 else 'less'}). The ledger's "
            "figure is the one counted, and a scenario's sale can't take out more than it "
            "holds: bring the ledger up to date, or record a price"
        )
    return notes


def build(
    inputs: Sequence[HoldingInputs],
    as_of: dt.date,
    base: str,
    rates: Mapping[str, Rate],
    balances: Sequence[Balance],
) -> tuple[tuple[BaselineHolding, ...], list[str]]:
    """Every holding as of the as-of date, and the notes where the linked
    accounts and their holdings disagree."""
    holdings = tuple(value(h, as_of, base, rates) for h in inputs)
    return holdings, meet_the_ledger(holdings, balances, base)


__all__ = ["build", "meet_the_ledger", "value"]
