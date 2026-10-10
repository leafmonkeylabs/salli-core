"""
What a holding is worth on a date: the latest price on or before it (a close
or the holding's own trade), adjusted for splits since, converted at the rate
of the price's day, and carried at cost — saying so — when it cannot be.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from salli.domain.portfolio.lots import Kind, Replay, Transaction, replay
from salli.domain.portfolio.valuation import TRADE, Close, Pricing

D = Decimal


def tx(kind: Kind, on: str, seq: int = 0, **fields) -> Transaction:
    return Transaction(
        id=f"{kind}-{on}-{seq}", kind=kind, on=date.fromisoformat(on), seq=seq, **fields
    )


def close(on: str, price: str) -> Close:
    return Close(date.fromisoformat(on), D(price), "user")


BUYS = [
    tx(Kind.BUY, "2026-01-05", quantity=D(10), price=D(100), fx_rate=D(300)),
    tx(Kind.BUY, "2026-02-05", quantity=D(5), price=D(110), fx_rate=D(310)),
]


def _value(history, closes, on: str, rates=None):
    position = Replay(history).advance(date.fromisoformat(on)).position()
    return Pricing(history, closes).value(date.fromisoformat(on), position, rates or {})


def test_without_any_price_a_holding_is_carried_at_cost():
    history = [tx(Kind.TRANSFER_IN, "2026-01-05", quantity=D(10), amount=D(500), fx_rate=D(2))]
    valuation = _value(history, [], "2026-06-01")
    assert (valuation.value, valuation.value_base) == (D(500), D(1000))
    assert not valuation.priced and not valuation.converted
    assert valuation.unrealised == 0


def test_the_last_trade_is_a_price_and_carries_its_own_rate():
    valuation = _value(BUYS, [], "2026-06-01")
    assert valuation.quote is not None and valuation.quote.source == TRADE
    # 15 units at the last trade's 110, at its rate of 310.
    assert (valuation.price, valuation.fx_rate) == (D(110), D(310))
    assert (valuation.value, valuation.value_base) == (D(1650), D(511500))
    # Cost 1000 + 550 = 1550; in base 300,000 + 170,500.
    assert (valuation.unrealised, valuation.unrealised_base) == (D(100), D(41000))


def test_a_newer_close_wins_and_is_converted_at_its_days_rate():
    valuation = _value(
        BUYS, [close("2026-05-29", "120")], "2026-06-01", {date(2026, 5, 29): D(320)}
    )
    assert (valuation.price, valuation.fx_rate, valuation.value) == (D(120), D(320), D(1800))
    assert valuation.value_base == D(576000)


def test_without_a_rate_for_its_day_a_close_values_only_in_its_own_currency():
    valuation = _value(BUYS, [close("2026-05-29", "120")], "2026-06-01")
    assert valuation.priced and not valuation.converted
    assert valuation.value == D(1800)
    assert valuation.value_base == valuation.cost_base == D(470500)


def test_on_a_day_with_a_trade_and_a_close_the_close_is_the_days_price():
    valuation = _value(BUYS, [close("2026-02-05", "112")], "2026-02-05", {date(2026, 2, 5): D(1)})
    assert valuation.quote is not None and (valuation.quote.source, valuation.price) == (
        "user",
        D(112),
    )


def test_a_price_from_before_a_split_is_adjusted_to_the_units_after_it():
    history = [*BUYS, tx(Kind.SPLIT, "2026-03-01", split_to=D(10), split_from=D(1))]
    valuation = _value(
        history, [close("2026-02-27", "1000")], "2026-03-02", {date(2026, 2, 27): D(1)}
    )
    # 150 units after the split, at 1000 / 10.
    assert (valuation.quantity, valuation.price, valuation.value) == (D(150), D(100), D(15000))
    assert valuation.quote is not None and valuation.quote.price == D(1000)


def test_a_close_on_the_split_date_is_already_split():
    history = [*BUYS, tx(Kind.SPLIT, "2026-03-01", split_to=D(10), split_from=D(1))]
    valuation = _value(
        history, [close("2026-03-01", "101")], "2026-03-02", {date(2026, 3, 1): D(1)}
    )
    assert valuation.price == D(101)


def test_an_inexact_reverse_split_adjusts_to_eighteen_places():
    history = [
        tx(Kind.BUY, "2026-01-05", quantity=D(9), price=D(1), fx_rate=D(1)),
        tx(Kind.SPLIT, "2026-02-01", split_to=D(1), split_from=D(3)),
    ]
    valuation = _value(
        history, [close("2026-01-31", "1.01")], "2026-02-02", {date(2026, 1, 31): D(1)}
    )
    assert valuation.price == D("3.03")
    history[1] = tx(Kind.SPLIT, "2026-02-01", split_to=D(3), split_from=D(1))
    valuation = _value(history, [close("2026-01-31", "1")], "2026-02-02", {date(2026, 1, 31): D(1)})
    assert valuation.price == D("0.333333333333333333")


def test_an_earlier_date_uses_the_price_known_then():
    closes = [close("2026-01-31", "105"), close("2026-05-29", "120")]
    rates = {date(2026, 1, 31): D(305), date(2026, 5, 29): D(320)}
    valuation = _value(BUYS, closes, "2026-02-01", rates)
    assert (valuation.quantity, valuation.price, valuation.fx_rate) == (D(10), D(105), D(305))


def test_a_trade_at_no_price_is_not_a_price():
    history = [*BUYS, tx(Kind.BUY, "2026-03-01", quantity=D(1), price=D(0), fx_rate=D(1))]
    valuation = _value(history, [], "2026-06-01")
    assert valuation.price == D(110)


def test_the_rates_a_valuation_needs_are_its_closes_days():
    pricing = Pricing(BUYS, [close("2026-01-31", "105"), close("2026-05-29", "120")])
    needed = pricing.rate_dates(
        [date(2026, 1, 4), date(2026, 1, 20), date(2026, 2, 1), date(2026, 2, 5), date(2026, 7, 1)]
    )
    assert needed == {date(2026, 1, 31), date(2026, 5, 29)}


def test_the_current_value_is_everything_recorded_at_the_latest_price():
    history = [*BUYS, tx(Kind.SELL, "2026-04-01", quantity=D(5), price=D(130), fx_rate=D(315))]
    book = replay(history)
    valuation = Pricing(history, []).value(date.max, book.position, {})
    assert (valuation.quantity, valuation.price, valuation.fx_rate) == (D(10), D(130), D(315))
