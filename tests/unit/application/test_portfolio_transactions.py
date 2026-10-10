"""
A holding's transactions through PortfolioService: each is checked against the
whole history before it is stored, carries the rate into the base currency of
its own day, and reads back exactly as it was recorded.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.application.ports import FxQuote, FxRatePort, FxUnavailableError
from salli.application.services.portfolio_service import PortfolioService
from salli.domain.portfolio.lots import TransactionError
from tests.fakes import FakeRecordsUoW

USER = "u1"


class Rates(FxRatePort):
    """Published rates by pair, the same on every date; records what it was asked."""

    def __init__(self, table: dict[tuple[str, str], str] | None = None) -> None:
        self.table = table or {}
        self.asked: list[tuple[str, str, str]] = []

    async def rate(self, from_currency: str, to_currency: str, on_date: str) -> FxQuote:
        self.asked.append((from_currency, to_currency, on_date))
        if (from_currency, to_currency) not in self.table:
            raise FxUnavailableError(f"No {from_currency}→{to_currency} rate")
        return FxQuote(Decimal(self.table[from_currency, to_currency]), "ecb", on_date)


def _service(base: str = "LKR", rates: dict[tuple[str, str], str] | None = None):
    uow = FakeRecordsUoW(base)
    fx = Rates(rates)
    return PortfolioService(lambda: uow, fx=fx), uow, fx


async def _holding(svc: PortfolioService, currency: str | None = None) -> str:
    return await svc.add_holding(
        USER,
        {"symbol": "VOO", "name": "S&P 500", "asset_class": "equity", "currency": currency},
    )


async def _add(svc: PortfolioService, holding_id: str, **fields) -> str:
    tx_id = await svc.add_transaction(USER, holding_id, fields)
    assert tx_id is not None
    return tx_id


async def test_a_buy_and_a_sale_make_lots_and_a_realised_gain():
    svc, _, _ = _service()
    h = await _holding(svc)
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="10", price="100", fees="5")
    await _add(svc, h, kind="sell", date="2026-02-01", quantity="4", price="120", fees="2")

    lots = await svc.get_lots(USER, h)
    assert lots is not None
    # The lot cost 10 × 100 + 5 = 1005; 4 units took 402 of it, 6 keep 603.
    assert (lots["quantity"], lots["cost"], lots["currency"]) == ("6", "603.00", "LKR")
    [sale] = lots["sales"]
    # 480 − 2 − 402 = 76.
    assert (sale["proceeds"], sale["fees"], sale["cost"], sale["gain"]) == (
        "480.00",
        "2.00",
        "402.00",
        "76.00",
    )
    assert lots["lots"][0]["cost_per_unit"] == "100.5"


async def test_a_sale_can_name_the_lot_it_sells():
    svc, _, _ = _service()
    h = await _holding(svc)
    first = await _add(svc, h, kind="buy", date="2026-01-05", quantity="5", price="10")
    second = await _add(svc, h, kind="buy", date="2026-01-06", quantity="5", price="20")
    await _add(
        svc,
        h,
        kind="sell",
        date="2026-02-01",
        quantity="2",
        price="25",
        lots=[{"lot_id": second, "quantity": "2"}],
    )
    lots = await svc.get_lots(USER, h)
    assert lots is not None
    assert [(lot["id"], lot["quantity"]) for lot in lots["lots"]] == [(first, "5"), (second, "3")]
    assert lots["sales"][0]["gain"] == "10.00"


async def test_a_holding_in_another_currency_carries_each_days_rate():
    svc, _, fx = _service("LKR", {("USD", "LKR"): "305.5"})
    h = await _holding(svc, "USD")
    given = await _add(
        svc, h, kind="buy", date="2026-01-05", quantity="1", price="100", fx_rate="300"
    )
    published = await _add(svc, h, kind="buy", date="2026-01-06", quantity="1", price="100")

    assert fx.asked == [("USD", "LKR", "2026-01-06")]
    one = await svc.get_transaction(USER, h, given)
    two = await svc.get_transaction(USER, h, published)
    assert one is not None and two is not None
    assert (one["fx_rate"], one["fx_rate_source"], one["currency"]) == ("300", "user", "USD")
    assert (two["fx_rate"], two["fx_rate_source"]) == ("305.5", "ecb")
    lots = await svc.get_lots(USER, h)
    assert lots is not None
    assert (lots["cost"], lots["cost_base"], lots["base_currency"]) == (
        "200.00",
        "60550.00",
        "LKR",
    )


async def test_a_transaction_in_another_currency_with_no_rate_is_refused():
    svc, uow, _ = _service("LKR")
    h = await _holding(svc, "USD")
    with pytest.raises(FxUnavailableError):
        await svc.add_transaction(
            USER, h, {"kind": "buy", "date": "2026-01-05", "quantity": "1", "price": "1"}
        )
    assert uow.holding_transactions.rows == {}


async def test_a_holding_in_the_base_currency_has_a_rate_of_one():
    svc, _, _ = _service("LKR")
    h = await _holding(svc)
    with pytest.raises(ValueError, match="exchange rate of 1"):
        await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="1", fx_rate="2")


async def test_selling_more_than_is_held_is_refused_and_nothing_is_stored():
    svc, uow, _ = _service()
    h = await _holding(svc)
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="1")
    with pytest.raises(TransactionError, match="only 1 are held"):
        await _add(svc, h, kind="sell", date="2026-01-06", quantity="2", price="1")
    assert len(uow.holding_transactions.rows) == 1


async def test_deleting_a_buy_a_later_sale_needs_is_refused():
    svc, _, _ = _service()
    h = await _holding(svc)
    buy = await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="1")
    sale = await _add(svc, h, kind="sell", date="2026-01-06", quantity="1", price="1")
    with pytest.raises(TransactionError, match="only 0 are held"):
        await svc.delete_transaction(USER, h, buy)
    assert await svc.delete_transaction(USER, h, sale) is True
    assert await svc.delete_transaction(USER, h, buy) is True
    assert await svc.list_transactions(USER, h) == []


async def test_an_edit_that_would_break_a_later_sale_is_refused():
    svc, _, _ = _service()
    h = await _holding(svc)
    buy = await _add(svc, h, kind="buy", date="2026-01-05", quantity="10", price="1")
    await _add(svc, h, kind="sell", date="2026-01-06", quantity="8", price="1")
    with pytest.raises(TransactionError, match="only 5 are held"):
        await svc.update_transaction(USER, h, buy, {"quantity": "5"})
    assert await svc.update_transaction(USER, h, buy, {"quantity": "9", "fees": "1.5"}) is True
    [edited, _] = await svc.list_transactions(USER, h) or []
    assert (edited["quantity"], edited["fees"], edited["total"]) == ("9", "1.50", "10.50")


async def test_moving_a_transaction_takes_its_new_days_rate():
    svc, _, fx = _service("LKR", {("USD", "LKR"): "300"})
    h = await _holding(svc, "USD")
    buy = await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="1")
    # A change that leaves the date alone keeps the rate it has.
    await svc.update_transaction(USER, h, buy, {"price": "2"})
    assert fx.asked == [("USD", "LKR", "2026-01-05")]
    await svc.update_transaction(USER, h, buy, {"date": "2026-03-01"})
    assert fx.asked[-1] == ("USD", "LKR", "2026-03-01")
    # One given with the change wins.
    await svc.update_transaction(USER, h, buy, {"fx_rate": "310", "fx_rate_source": "broker"})
    tx = await svc.get_transaction(USER, h, buy)
    assert tx is not None and (tx["fx_rate"], tx["fx_rate_source"]) == ("310", "broker")


async def test_a_transactions_kind_cannot_change():
    svc, _, _ = _service()
    h = await _holding(svc)
    buy = await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="1")
    with pytest.raises(TransactionError, match="kind cannot change"):
        await svc.update_transaction(USER, h, buy, {"kind": "sell"})


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"kind": "dividend", "date": "2026-01-05", "amount": "1", "price": "1"}, "has no price"),
        ({"kind": "buy", "date": "2026-01-05", "quantity": "1"}, "needs price"),
        ({"kind": "split", "date": "2026-01-05", "ratio": "a:b"}, "ratio must be"),
        ({"kind": "buy", "date": "2026-13-01", "quantity": "1", "price": "1"}, "YYYY-MM-DD"),
        ({"kind": "buy", "date": "2026-01-05", "quantity": "abc", "price": "1"}, "quantity"),
        ({"kind": "gift", "date": "2026-01-05"}, "kind must be one of"),
        ({"kind": "buy", "quantity": "1", "price": "1"}, "needs a date"),
        (
            {"kind": "buy", "date": "2026-01-05", "quantity": "1", "price": "1", "lots": []},
            "has no lots",
        ),
        (
            {
                "kind": "buy",
                "date": "2026-01-05",
                "quantity": "1",
                "price": "1",
                "fx_rate_source": "x",
            },
            "describes an fx_rate",
        ),
    ],
)
async def test_each_kind_takes_its_own_fields_and_only_those(fields: dict, message: str):
    svc, uow, _ = _service()
    h = await _holding(svc)
    with pytest.raises(TransactionError, match=message):
        await svc.add_transaction(USER, h, fields)
    assert uow.holding_transactions.rows == {}


async def test_transactions_list_in_the_order_they_take_effect():
    svc, _, _ = _service()
    h = await _holding(svc)
    later = await _add(svc, h, kind="buy", date="2026-02-01", quantity="1", price="1")
    split = await _add(svc, h, kind="split", date="2026-02-01", ratio="2")
    earlier = await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="1")
    listed = await svc.list_transactions(USER, h) or []
    assert [t["id"] for t in listed] == [earlier, split, later]


async def test_transactions_read_back_as_recorded():
    svc, _, _ = _service()
    h = await _holding(svc)
    dividend = await _add(
        svc,
        h,
        kind="dividend",
        date="2026-03-01",
        amount="25",
        withholding_tax="3.75",
        note="Q1",
    )
    split = await _add(svc, h, kind="split", date="2026-04-01", ratio="1:10")
    tx = await svc.get_transaction(USER, h, dividend)
    assert tx is not None
    assert {k: tx[k] for k in ("kind", "date", "amount", "withholding_tax", "total", "note")} == {
        "kind": "dividend",
        "date": "2026-03-01",
        "amount": "25.00",
        "withholding_tax": "3.75",
        "total": "21.25",
        "note": "Q1",
    }
    assert (tx["quantity"], tx["price"], tx["ratio"], tx["fx_rate"]) == (None, None, None, "1")
    tx = await svc.get_transaction(USER, h, split)
    assert tx is not None
    assert (tx["ratio"], tx["fx_rate"], tx["total"], tx["amount"]) == ("1:10", None, None, None)


async def test_money_is_kept_in_the_currencys_own_minor_units():
    svc, uow, _ = _service("JPY")
    h = await _holding(svc)
    tx_id = await _add(
        svc, h, kind="buy", date="2026-01-05", quantity="3", price="1234.5", fees="99.5"
    )
    # ¥99.5 rounds half-up to ¥100: a yen has no smaller unit.
    assert uow.holding_transactions.rows[tx_id]["fees_minor"] == 100
    tx = await svc.get_transaction(USER, h, tx_id)
    assert tx is not None and (tx["fees"], tx["total"], tx["price"]) == ("100", "3804", "1234.5")


async def test_a_holding_in_another_currency_is_not_declared_by_value():
    svc, _, _ = _service("LKR")
    with pytest.raises(ValueError, match="record this USD holding's transactions"):
        await svc.add_holding(
            USER,
            {
                "symbol": "VOO",
                "name": "S&P 500",
                "asset_class": "equity",
                "currency": "USD",
                "cost_basis": "100",
                "current_value": "110",
            },
        )
    # Declared the old way, it is in the base currency, as before.
    old_way = await svc.add_holding(
        USER,
        {
            "symbol": "VOO",
            "name": "S&P 500",
            "asset_class": "equity",
            "cost_basis": "100",
            "current_value": "110",
        },
    )
    holding = await svc.get_holding(USER, old_way)
    assert holding is not None and holding["current_value"] == "110.00"


async def test_a_holdings_currency_is_fixed_once_it_has_transactions():
    svc, uow, _ = _service("LKR", {("USD", "LKR"): "300"})
    h = await _holding(svc)
    await svc.update_holding(USER, h, {"currency": "usd"})
    assert uow.holdings.rows[h]["currency"] == "USD"
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="1")
    with pytest.raises(ValueError, match="cannot change once it has transactions"):
        await svc.update_holding(USER, h, {"currency": "EUR"})


async def test_deleting_a_holding_deletes_its_transactions():
    svc, uow, _ = _service()
    h = await _holding(svc)
    await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="1")
    await svc.delete_holding(USER, h)
    assert uow.holding_transactions.rows == {}


async def test_another_users_holding_and_transactions_are_not_found():
    svc, _, _ = _service()
    h = await _holding(svc)
    tx_id = await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="1")
    fields = {"kind": "buy", "date": "2026-01-05", "quantity": "1", "price": "1"}
    assert await svc.add_transaction("someone-else", h, fields) is None
    assert await svc.list_transactions("someone-else", h) is None
    assert await svc.get_transaction("someone-else", h, tx_id) is None
    assert await svc.get_lots("someone-else", h) is None
    assert await svc.update_transaction("someone-else", h, tx_id, {"price": "2"}) is False
    assert await svc.delete_transaction("someone-else", h, tx_id) is False
    other = await _holding(svc)
    assert await svc.get_transaction(USER, other, tx_id) is None


async def test_the_export_has_every_holdings_transactions():
    svc, _, _ = _service("LKR", {("USD", "LKR"): "300"})
    usd = await _holding(svc, "USD")
    lkr = await _holding(svc)
    await svc.update_holding(USER, lkr, {"is_active": False})
    one = await _add(svc, h := usd, kind="buy", date="2026-01-05", quantity="1", price="1.5")
    two = await _add(svc, lkr, kind="dividend", date="2026-01-06", amount="10")
    exported = await svc.export_transactions(USER)
    assert [(t["id"], t["holding_id"], t["currency"]) for t in exported] == [
        (one, h, "USD"),
        (two, lkr, "LKR"),
    ]


async def test_every_change_to_a_history_holds_the_holding_first():
    svc, uow, _ = _service()
    h = await _holding(svc)
    tx_id = await _add(svc, h, kind="buy", date="2026-01-05", quantity="1", price="1")
    await svc.update_transaction(USER, h, tx_id, {"price": "2"})
    await svc.delete_transaction(USER, h, tx_id)
    assert uow.holdings.locked == [h, h, h]
